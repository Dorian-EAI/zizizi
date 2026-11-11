"""自家人 AI 下单 Agent 编排

能力边界：
- 维护多轮槽位：服务类型、问题描述、照片、服务地址、上门时间、加急
- 信息齐全后生成「订单草稿」，只有用户显式确认才真正创建订单
- 真实大模型走 OpenAI 兼容的 function calling；provider=mock 或开发环境
  大模型不可用时回退到确定性规则引擎，保证本地可完整走通下单闭环

安全约束：
- 模型没有任何直接写订单的能力，create_order 工具必须同时满足
  「会话已进入待确认状态」+「用户最新一句话是明确确认」
- 地址只允许从用户名下的地址簿选择，坐标由服务端读取
- 照片 base64 由服务端校验魔数与大小后重新落库，不信任客户端图片地址
"""

import base64
import copy
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.models.agent import AgentSession
from app.models.order import Order
from app.models.service import ServiceType
from app.models.user import Address, User
from app.schemas.order import CreateOrderRequest
from app.services import ai_service, auth_service, order_service, pricing_engine, upload_service
from app.utils.logger import get_logger


logger = get_logger(__name__)

SESSION_TTL_HOURS = 24
MAX_IMAGES = 9
MAX_MESSAGE_HISTORY = 12
MAX_DESCRIPTION = 500
MAX_IMAGE_BYTES = 3 * 1024 * 1024
IN_PROGRESS_TIMEOUT_SECONDS = 120

_BOUND_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
_CN_TZ = timezone(timedelta(hours=8))
_TIME_RE = re.compile(r"(\d{1,2})\s*(?:点|时|:|：)\s*(半|\d{1,2})?")

SERVICE_NAMES: Dict[str, str] = {
    "electric": "水电维修",
    "air_condition": "空调维修",
    "appliance": "家电维修",
    "plumbing": "管道疏通",
    "door_window": "门窗维修",
    "circuit": "电路检修",
    "furniture": "家具安装",
    "wall_repair": "墙面修补",
}

# 规则定价引擎的服务类型与数据库服务 key 不同，此处做稳定映射。
PRICING_SERVICE_MAP: Dict[str, str] = {
    "electric": "water_electric",
    "air_condition": "air_conditioner",
    "aircon": "air_conditioner",
    "appliance": "appliance",
    "plumbing": "pipeline",
    "door_window": "door_window",
    "circuit": "circuit",
    "furniture": "furniture",
    "wall_repair": "wall",
    "wall": "wall",
}

# 历史库使用 aircon/wall，新库使用 air_condition/wall_repair；两者互为别名。
SERVICE_KEY_ALIASES: Dict[str, Tuple[str, ...]] = {
    "air_condition": ("aircon",),
    "aircon": ("air_condition",),
    "wall_repair": ("wall",),
    "wall": ("wall_repair",),
}

# 顺序即优先级：先命中者生效
SERVICE_KEYWORDS: List[Tuple[Tuple[str, ...], str]] = [
    (("空调", "制冷", "不冷", "不凉", "加氟", "外机", "制热"), "air_condition"),
    (("跳闸", "断电", "电路", "短路", "插座", "开关", "电线", "漏电"), "circuit"),
    (("管道", "堵塞", "下水道", "地漏", "马桶", "返水", "下水慢"), "plumbing"),
    (("墙面", "墙皮", "裂缝", "掉皮", "刷漆", "发霉", "墙砖"), "wall_repair"),
    (("水管", "龙头", "水压", "软管", "角阀", "水电", "漏水", "渗水"), "electric"),
    (("洗衣机", "冰箱", "热水器", "电视", "油烟机", "微波炉", "燃气灶", "家电"), "appliance"),
    (("门锁", "门窗", "玻璃", "合页", "纱窗", "漏风", "木门", "防盗门"), "door_window"),
    (("家具", "柜子", "床", "桌子", "组装", "安装", "拆装"), "furniture"),
]

_CONFIRM_DENY = ("不确认", "先不", "别下", "不要下", "取消", "再等等", "先别")

_CANCEL_WORDS = ("取消", "算了", "不下单了", "不下了", "先不下", "重新描述")

_ORDER_STATUS_TEXT = {
    "pending": "待师傅接单",
    "accepted": "师傅已接单",
    "departing": "师傅正在路上",
    "arrived": "师傅已到达",
    "serving": "服务中",
    "completed": "服务已完成，待支付",
    "paid": "已支付",
    "cancelled": "已取消",
    "reviewed": "已完成并评价",
}

_DAY_OFFSETS = {"今天": 0, "明天": 1, "后天": 2, "大后天": 3}
_PERIOD_HOURS = {"早上": 8, "上午": 9, "中午": 12, "下午": 14, "晚上": 18, "晚间": 19}

_TIME_OPTION_DEFS = ((0, 15), (1, 9), (1, 14), (2, 9))


class AgentError(RuntimeError):
    """Agent 业务异常基类。"""


class AgentInputError(AgentError):
    """输入不合法（照片格式、URL 等），映射 400。"""


class AgentConflict(AgentError):
    """当前会话状态不允许该操作，映射 409。"""


# ===== 会话状态 =====

def _new_state() -> dict:
    return {
        "status": "collecting",
        "messages": [],
        "slots": {
            "service_type": None,
            "service_name": None,
            "description": None,
            "images": [],
            "address_id": None,
            "address_text": None,
            "address_label": None,
            "latitude": None,
            "longitude": None,
            "appoint_time": None,
            "appoint_text": None,
            "urgent": False,
            "urgent_amount": 0.0,
        },
        "estimate": None,
        "draft": None,
        "confirm_token": None,
        "order_id": None,
        "order_no": None,
    }


def _decode_state(raw: str) -> dict:
    state = _new_state()
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, ValueError):
        parsed = {}
    if not isinstance(parsed, dict):
        return state
    if isinstance(parsed.get("slots"), dict):
        state["slots"].update(
            {key: value for key, value in parsed["slots"].items() if key in state["slots"]}
        )
    for key in ("status", "messages", "estimate", "draft", "confirm_token", "order_id", "order_no"):
        if key in parsed:
            state[key] = parsed[key]
    if state["status"] not in {"collecting", "awaiting_confirm", "creating", "created"}:
        state["status"] = "collecting"
    if not isinstance(state["messages"], list):
        state["messages"] = []
    return state


def _new_session_no() -> str:
    return "ag_" + secrets.token_urlsafe(18)


def _new_confirm_token() -> str:
    return secrets.token_urlsafe(16)


def _load_session(db: Session, user: User, session_id: Optional[str]) -> Tuple[AgentSession, dict]:
    session = None
    if session_id:
        session = (
            db.query(AgentSession)
            .filter(AgentSession.session_no == session_id, AgentSession.user_id == user.id)
            .first()
        )
    if not session:
        session = AgentSession(
            session_no=_new_session_no(),
            user_id=user.id,
            status="collecting",
            state_json="{}",
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    state = _decode_state(session.state_json)
    expires_at = (session.updated_at or session.created_at or datetime.utcnow()) + timedelta(
        hours=SESSION_TTL_HOURS
    )
    if expires_at < datetime.utcnow():
        state = _new_state()
    elif state["status"] == "creating":
        stuck = (session.updated_at or datetime.utcnow()) + timedelta(
            seconds=IN_PROGRESS_TIMEOUT_SECONDS
        ) < datetime.utcnow()
        if stuck:
            state["status"] = "awaiting_confirm" if state.get("draft") else "collecting"
    return session, state


def _save_session(db: Session, session: AgentSession, state: dict) -> None:
    session.status = state.get("status") or "collecting"
    session.state_json = json.dumps(state, ensure_ascii=False)
    session.updated_at = datetime.utcnow()
    db.add(session)
    db.commit()


def _append_message(state: dict, role: str, content: str) -> None:
    messages = state.get("messages") or []
    messages.append({"role": role, "content": (content or "").strip()[:600]})
    state["messages"] = messages[-MAX_MESSAGE_HISTORY:]


# ===== 槽位辅助 =====

def _phone_ready(user: User) -> bool:
    return bool(_BOUND_PHONE_RE.fullmatch(str(user.phone or "").strip()))


def _now_local() -> datetime:
    return datetime.now(_CN_TZ).replace(tzinfo=None)


def _to_utc_iso(local_dt: datetime) -> str:
    return (
        local_dt.replace(tzinfo=_CN_TZ)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
        .isoformat()
    )


def _detect_service(text: str) -> Optional[str]:
    for keywords, service_type in SERVICE_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return service_type
    return None


def _is_urgent(text: str) -> bool:
    return any(word in text for word in ("加急", "紧急", "着急", "赶快", "赶紧", "马上", "尽快", "立刻"))


def _is_cancel(text: str) -> bool:
    return any(word in text for word in _CANCEL_WORDS)


def _is_order_query(text: str) -> bool:
    value = text or ""
    if any(word in value for word in ("我的订单", "我的单", "订单进度", "订单状态", "订单情况")):
        return True
    # 描述故障或进入具体服务时，优先按新需求处理，避免“还要多久修好”被误判成查订单。
    if _detect_service(value) or _looks_like_problem(value):
        return False
    return any(
        word in value
        for word in ("到哪了", "到哪儿了", "师傅到", "什么时候到", "多久到", "还要多久")
    )


def _format_appoint_time(value) -> str:
    if not value:
        return ""
    try:
        local = value.replace(tzinfo=timezone.utc).astimezone(_CN_TZ)
    except (TypeError, ValueError):
        return ""
    return local.strftime("%m月%d日 %H:%M")


def _is_explicit_confirmation(text: str) -> bool:
    value = (text or "").strip()
    if not value or any(word in value for word in _CONFIRM_DENY):
        return False
    # 「确认下单/确认订单」是唯一可以夹带其他内容的明确指令
    if "确认下单" in value or "确认订单" in value:
        return True
    if "？" in value or "?" in value:
        return False
    # “确认一下价格/确认地址/确认时间”是核对信息，不是下单
    if any(
        word in value
        for word in ("价格", "多少钱", "费用", "地址", "时间", "师傅", "看看", "核对", "改", "换")
    ):
        return False
    compact = re.sub(r"[\s，,。.!！~～]+", "", value)
    if len(compact) > 8:
        return False
    return compact in {
        "确认",
        "就这个",
        "下单吧",
        "可以下单",
        "帮我下单",
        "预约吧",
        "安排吧",
        "没问题",
    }


def _clean_description(text: str) -> str:
    """从一句话里剔除时间、地址、客套词，保留故障描述。"""
    value = text or ""
    value = _TIME_RE.sub(" ", value)
    value = re.sub(r"(今天|明天|后天|大后天|早上|上午|中午|下午|晚上|晚间)", " ", value)
    for phrase in (
        "尽快", "马上", "立刻", "越快越好", "随时", "加急", "紧急", "帮我", "麻烦",
        "确认下单", "确认订单", "确认", "下单", "预约", "安排", "就这个", "可以下单",
        "没问题", "好的", "用我家", "我家", "家里", "默认地址", "家庭地址", "公司地址", "公司", "单位", "地址",
    ):
        value = value.replace(phrase, " ")
    value = re.sub(r"[，,。.!！?？、;；:：\s]+", " ", value).strip()
    return value[:MAX_DESCRIPTION]


_PROBLEM_HINTS = (
    "坏", "漏", "堵", "响", "裂", "掉", "跳闸", "断", "松", "脱", "渗", "臭",
    "热", "冷", "慢", "卡", "安装", "维修", "修", "故障",
    "不制冷", "不制热", "不启动", "不亮", "不通电", "不出水", "不打火",
    "打不开", "关不上", "不加热", "不工作", "不转", "不出风",
)


def _looks_like_problem(text: str) -> bool:
    return any(word in (text or "") for word in _PROBLEM_HINTS)


def _parse_appointment(text: str) -> Optional[Tuple[str, str]]:
    """把中文时间表达解析为 (UTC ISO, 展示文案)。"""
    value = (text or "").strip()
    if not value:
        return None

    if any(word in value for word in ("尽快", "马上", "立刻", "越快越好")):
        target = (_now_local() + timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
        target += timedelta(hours=1)
        return _to_utc_iso(target), "尽快（约 2 小时内）"

    day_offset: Optional[int] = None
    day_word = ""
    for word, offset in _DAY_OFFSETS.items():
        if word in value:
            day_offset, day_word = offset, word
            break

    period_hour: Optional[int] = None
    for word, hour in _PERIOD_HOURS.items():
        if word in value:
            period_hour = hour
            break

    hour: Optional[int] = None
    minute = 0
    match = _TIME_RE.search(value)
    if match:
        hour = int(match.group(1))
        suffix = match.group(2)
        if suffix == "半":
            minute = 30
        elif suffix:
            minute = min(int(suffix), 59)
        if ("下午" in value or "晚上" in value or "晚间" in value) and hour < 12:
            hour += 12
        elif "中午" in value and hour < 11:
            hour += 12

    if hour is None:
        if period_hour is None and day_offset is None:
            return None
        hour = period_hour if period_hour is not None else 9
    if hour > 23:
        return None

    offset = day_offset or 0
    now = _now_local()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=offset)
    if target <= now + timedelta(minutes=10):
        target += timedelta(days=1)
        offset += 1

    label = f"{_day_word(offset)} {hour:02d}:{minute:02d}"
    return _to_utc_iso(target), label


def _day_word(offset: int) -> str:
    return {0: "今天", 1: "明天", 2: "后天", 3: "大后天"}.get(offset, "稍后")


def _time_options() -> List[dict]:
    now = _now_local()
    items: List[dict] = []
    for day_offset, hour in _TIME_OPTION_DEFS:
        target = now.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(
            days=day_offset
        )
        if target <= now + timedelta(minutes=30):
            continue
        label = f"{_day_word(day_offset)} {hour:02d}:00"
        items.append({"type": "set_time", "text": label, "value": label})
    return items


def _address_text(address: Address) -> str:
    return "".join(
        part for part in (address.province, address.city, address.district, address.detail) if part
    ).strip()


def _has_location(address: Address) -> bool:
    return address.location_lat is not None and address.location_lng is not None


def _saved_addresses(db: Session, user: User) -> List[Address]:
    return list(auth_service.get_addresses(db, user) or [])


def _address_options(db: Session, user: User) -> List[dict]:
    result = []
    for address in _saved_addresses(db, user):
        if not _has_location(address):
            continue
        result.append(
            {
                "id": address.id,
                "label": address.label or "地址",
                "text": _address_text(address),
                "is_default": bool(address.is_default),
                "has_location": True,
            }
        )
        if len(result) >= 5:
            break
    return result


def _apply_address(slots: dict, address: Address) -> None:
    slots.update(
        {
            "address_id": address.id,
            "address_text": _address_text(address),
            "address_label": address.label or "地址",
            "latitude": float(address.location_lat),
            "longitude": float(address.location_lng),
        }
    )


def _default_address(db: Session, user: User) -> Optional[Address]:
    candidates = [item for item in _saved_addresses(db, user) if _has_location(item)]
    if not candidates:
        return None
    for item in candidates:
        if item.is_default:
            return item
    return candidates[0]


def _match_address(db: Session, user: User, text: str) -> Optional[Address]:
    candidates = [item for item in _saved_addresses(db, user) if _has_location(item)]
    if not candidates:
        return None
    if any(word in text for word in ("默认", "我家", "家里", "家庭地址")):
        return next((item for item in candidates if item.is_default), candidates[0])
    if any(word in text for word in ("公司", "单位", "办公室")):
        for item in candidates:
            if any(word in f"{item.label or ''}{item.name or ''}" for word in ("公司", "单位", "办公室")):
                return item
    index_match = re.search(r"第\s*([1-5一二三四五])\s*个", text)
    if index_match:
        index = "12345".find(index_match.group(1))
        if index < 0:
            index = "一二三四五".find(index_match.group(1))
        if 0 <= index < len(candidates):
            return candidates[index]
    for item in candidates:
        if item.detail and item.detail in text:
            return item
    return None


def _select_address_by_id(db: Session, user: User, address_id: Any) -> Address:
    try:
        address_id = int(address_id)
    except (TypeError, ValueError) as exc:
        raise AgentInputError("地址编号不正确") from exc
    address = (
        db.query(Address)
        .filter(Address.id == address_id, Address.user_id == user.id)
        .first()
    )
    if not address:
        raise AgentConflict("该地址不存在或不属于当前账号")
    if not _has_location(address):
        raise AgentConflict("该地址缺少定位，请重新选择地址后再试")
    return address


def _service_row(db: Session, service_type: Optional[str]) -> Optional[ServiceType]:
    if not service_type:
        return None
    keys = (service_type,) + SERVICE_KEY_ALIASES.get(service_type, ())
    rows = (
        db.query(ServiceType)
        .filter(ServiceType.key.in_(keys), ServiceType.is_active.is_(True))
        .all()
    )
    by_key = {str(row.key).strip().lower(): row for row in rows}
    for key in keys:
        row = by_key.get(key.lower())
        if row:
            return row
    return None


def _ensure_estimate(state: dict) -> Optional[dict]:
    slots = state["slots"]
    service_type = slots.get("service_type")
    if not service_type:
        state["estimate"] = None
        return None
    estimate = pricing_engine.estimate_price(
        service_type=PRICING_SERVICE_MAP.get(service_type, "water_electric"),
        description=slots.get("description") or "",
        images_count=len(slots.get("images") or []),
        urgency="urgent_20" if slots.get("urgent") else "normal",
    )
    state["estimate"] = estimate
    return estimate


def _build_draft(db: Session, user: User, state: dict) -> Tuple[Optional[dict], List[str]]:
    slots = state["slots"]
    missing: List[str] = []

    service = _service_row(db, slots.get("service_type"))
    if not service:
        missing.append("service_type")
    else:
        # 兼容历史库的 aircon/wall 等 key，草稿与状态统一使用数据库真实 key。
        slots["service_type"] = service.key
        slots["service_name"] = service.name
    description = (slots.get("description") or "").strip()
    if len(description) < 2:
        missing.append("description")
    if (
        not slots.get("address_id")
        or slots.get("latitude") is None
        or slots.get("longitude") is None
    ):
        missing.append("address")
    if not slots.get("appoint_time"):
        missing.append("appoint_time")

    if missing:
        return None, missing

    return (
        {
            "service_type": service.key,
            "description": description[:MAX_DESCRIPTION],
            "images": list(slots.get("images") or [])[:MAX_IMAGES],
            "address": {
                "address": str(slots.get("address_text") or "").strip(),
                "latitude": float(slots["latitude"]),
                "longitude": float(slots["longitude"]),
            },
            "appoint_time": slots["appoint_time"],
            "budget": 0,
            "urgent": bool(slots.get("urgent")),
            "urgent_amount": float(slots.get("urgent_amount") or 0),
        },
        [],
    )


# ===== 图片处理 =====

def _detect_image_ext(data: bytes) -> Optional[str]:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(data) > 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    return None


def _decode_base64_image(raw: str) -> Tuple[bytes, str]:
    value = (raw or "").strip()
    if value.startswith("data:"):
        value = value.split(",", 1)[-1]
    try:
        data = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise AgentInputError("照片数据格式不正确，请重新选择照片") from exc
    if not data:
        raise AgentInputError("照片内容为空")
    if len(data) > MAX_IMAGE_BYTES:
        raise AgentInputError("单张照片不能超过 3MB")
    ext = _detect_image_ext(data)
    if not ext:
        raise AgentInputError("仅支持 JPG/PNG/WEBP 格式的照片")
    return data, ext


async def _store_base64_images(user: User, raw_list: List[str]) -> Tuple[List[str], List[str]]:
    urls: List[str] = []
    data_urls: List[str] = []
    for raw in raw_list[:MAX_IMAGES]:
        data, ext = _decode_base64_image(raw)
        try:
            result = await run_in_threadpool(
                upload_service.upload_image,
                "images",
                data,
                f"agent.{ext}",
                owner_id=user.id,
            )
        except HTTPException as exc:
            raise AgentInputError(str(exc.detail)) from exc
        urls.append(result["url"])
        mime = "jpeg" if ext == "jpg" else ext
        data_urls.append(f"data:image/{mime};base64,{base64.b64encode(data).decode()}")
    return urls, data_urls


def _validate_image_urls(image_urls: List[str]) -> List[str]:
    result = []
    for url in image_urls or []:
        value = str(url or "").strip()
        if not value:
            continue
        if not (value.startswith("http://") or value.startswith("https://") or value.startswith("/uploads/")):
            raise AgentInputError("图片地址格式不正确")
        result.append(value[:512])
    return result[:MAX_IMAGES]


def _merge_images(state: dict, new_urls: List[str]) -> None:
    merged = list(state["slots"].get("images") or [])
    for url in new_urls:
        if url not in merged:
            merged.append(url)
    state["slots"]["images"] = merged[:MAX_IMAGES]


# ===== 订单创建 =====

def _order_public(db: Session, state: dict) -> Optional[dict]:
    order_id = state.get("order_id")
    if not order_id:
        return None
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return None
    try:
        address = json.loads(order.address or "{}").get("address")
    except (TypeError, ValueError):
        address = None
    return {
        "id": order.id,
        "order_no": order.order_no,
        "service_name": order.service_name,
        "status": order.status,
        "address": address,
        "appoint_time": order.appoint_time.isoformat() if order.appoint_time else None,
        "budget": float(order.budget or 0),
    }


def _order_actions(order_id: int) -> List[dict]:
    return [
        {
            "type": "navigate",
            "text": "查看订单",
            "url": f"/pages/order-detail-client/index?id={order_id}",
        },
        {
            "type": "navigate",
            "text": "继续下单",
            "url": "/pages/client-publish/index",
        },
    ]


def _created_reply(db: Session, state: dict) -> dict:
    order = _order_public(db, state)
    if not order:
        return {"text": "订单已经提交，请到订单列表查看。", "actions": []}
    return {
        "text": f"订单已提交成功，订单号 {order['order_no']}。师傅接单后会第一时间联系你。",
        "order": order,
        "actions": _order_actions(order["id"]),
    }


def _create_order_from_draft(db: Session, user: User, session: AgentSession, state: dict) -> Order:
    if state.get("status") == "created":
        existing = _order_public(db, state)
        if existing:
            return db.query(Order).filter(Order.id == existing["id"]).first()

    if state.get("status") == "creating":
        raise AgentConflict("订单正在提交，请稍后在订单列表查看")

    draft = state.get("draft")
    if state.get("status") != "awaiting_confirm" or not draft:
        raise AgentConflict("订单信息还不完整，请先补充问题、地址和上门时间")

    if not _phone_ready(user):
        raise AgentConflict("请先绑定手机号后再提交订单")

    claimed = (
        db.query(AgentSession)
        .filter(AgentSession.id == session.id, AgentSession.status == "awaiting_confirm")
        .update({"status": "creating", "updated_at": datetime.utcnow()}, synchronize_session=False)
    )
    db.commit()
    if not claimed:
        db.refresh(session)
        if session.status == "created" and state.get("order_id"):
            state["status"] = "created"
            order = db.query(Order).filter(Order.id == state["order_id"]).first()
            if order:
                return order
        raise AgentConflict("订单正在提交，请稍后在订单列表查看")

    payload = dict(draft)
    try:
        payload["appoint_time"] = datetime.fromisoformat(draft["appoint_time"])
        order = order_service.create_order(db, user, CreateOrderRequest(**payload))
    except (HTTPException, ValueError, TypeError) as exc:
        session.status = "awaiting_confirm"
        session.updated_at = datetime.utcnow()
        db.commit()
        detail = exc.detail if isinstance(exc, HTTPException) else "订单信息校验失败，请确认后重试"
        raise AgentConflict(str(detail)) from exc

    state["status"] = "created"
    state["order_id"] = order.id
    state["order_no"] = order.order_no
    state["confirm_token"] = None
    return order


def _recent_orders_payload(db: Session, user: User, limit: int = 3) -> List[dict]:
    orders = (
        db.query(Order)
        .filter(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": order.id,
            "order_no": order.order_no,
            "service_name": order.service_name,
            "status": order.status,
            "status_text": _ORDER_STATUS_TEXT.get(order.status, order.status),
            "appoint_time": _format_appoint_time(order.appoint_time),
        }
        for order in orders
    ]


def _orders_reply(db: Session, user: User) -> dict:
    orders = _recent_orders_payload(db, user)
    if not orders:
        return {
            "text": "你还没有下过单。直接说哪里需要维修，我来帮你安排师傅。",
            "actions": [],
            "_engine": "rule",
            "_skip_finalize": True,
        }
    lines = ["你最近的订单："]
    for order in orders:
        lines.append(
            f"• {order['order_no']}｜{order['service_name']}｜{order['status_text']}"
        )
    latest = orders[0]
    if latest["appoint_time"]:
        lines.append(f"最近一单预约上门：{latest['appoint_time']}")
    return {
        "text": "\n".join(lines),
        "actions": [
            {
                "type": "navigate",
                "text": "查看最近订单",
                "url": f"/pages/order-detail-client/index?id={latest['id']}",
            },
            {"type": "navigate", "text": "全部订单", "url": "/pages/client-orders/index"},
        ],
        "_engine": "rule",
        "_skip_finalize": True,
    }


def _reset_draft(state: dict) -> None:
    """撤销草稿，保留地址方便用户继续下一单。"""
    slots = state["slots"]
    for key in (
        "service_type",
        "service_name",
        "description",
        "images",
        "appoint_time",
        "appoint_text",
        "urgent",
        "urgent_amount",
    ):
        slots[key] = [] if key == "images" else (False if key == "urgent" else None)
    slots["urgent_amount"] = 0.0
    state.update(
        {
            "status": "collecting",
            "estimate": None,
            "draft": None,
            "confirm_token": None,
            "order_id": None,
            "order_no": None,
        }
    )


# ===== 回复文案 =====

def _compose(*parts: Optional[str]) -> str:
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def _draft_text(state: dict) -> str:
    slots = state["slots"]
    estimate = state.get("estimate") or {}
    lines = ["请确认订单信息："]
    lines.append(f"• 服务：{slots.get('service_name') or SERVICE_NAMES.get(slots.get('service_type'), '上门维修')}")
    lines.append(f"• 问题：{slots.get('description') or '待补充'}")
    lines.append(f"• 地址：{slots.get('address_text') or '待选择'}")
    lines.append(f"• 上门：{slots.get('appoint_text') or '待确认'}")
    if estimate.get("min_price") is not None and estimate.get("max_price") is not None:
        lines.append(
            f"• 参考价：¥{estimate['min_price']:.0f}-{estimate['max_price']:.0f}"
            "（最终以师傅上门检测为准）"
        )
    if slots.get("urgent"):
        lines.append(f"• 加急：是（加急费 ¥{float(slots.get('urgent_amount') or 0):.0f}）")
    if slots.get("images"):
        lines.append(f"• 照片：{len(slots['images'])} 张")
    lines.append("确认无误请回复「确认下单」或点击下方按钮。")
    return "\n".join(lines)


def _missing_text(
    db: Session, user: User, missing: List[str], state: Optional[dict] = None
) -> str:
    has_images = bool(state and state["slots"].get("images"))
    if "service_type" in missing:
        if has_images:
            return "照片已收到。再说一句具体是哪里坏了，比如「空调不制冷」「水管漏水」，我好安排对应师傅。"
        return "请先说说哪里需要维修，比如「空调不制冷」「厨房水管漏水」，也可以直接拍照给我。"
    if "description" in missing:
        return "再补充一句具体故障现象，我好判断需要哪种服务。"
    if "address" in missing:
        located = [item for item in _address_options(db, user) if item["has_location"]]
        if not located:
            return "还没有可用的服务地址，请先添加一个带定位的地址，我就能帮你下单。"
        return "请选择上门地址。"
    if "appoint_time" in missing:
        return "希望师傅什么时候上门？可以直接说「明天上午」，也可以点下面的时段。"
    return "还需要补充一些信息才能下单。"


def _options_for(db: Session, user: User, missing: List[str]) -> dict:
    options: Dict[str, list] = {"services": [], "addresses": [], "times": []}
    if "service_type" in missing:
        options["services"] = [
            {"type": "set_service", "text": name, "value": key}
            for key, name in SERVICE_NAMES.items()
        ]
    if "address" in missing:
        options["addresses"] = _address_options(db, user)
    if "appoint_time" in missing:
        options["times"] = _time_options()
    return options


# ===== 规则引擎（mock / 开发环境降级）=====

def _rule_turn(db: Session, user: User, session: AgentSession, state: dict, message: str) -> dict:
    text = (message or "").strip()
    slots = state["slots"]

    if not text:
        return {"text": "", "_engine": "rule"}

    if _is_order_query(text):
        return _orders_reply(db, user)

    if state.get("status") == "created":
        if _is_explicit_confirmation(text):
            return {**_created_reply(db, state), "_engine": "rule"}
        if _is_cancel(text):
            reply = _created_reply(db, state)
            reply["text"] = "这一单已经提交了。如需取消，请在订单详情页操作。"
            return {**reply, "_engine": "rule"}
        if not (_detect_service(text) or _looks_like_problem(text)):
            reply = _created_reply(db, state)
            reply["text"] = "这一单已经提交成功了，师傅接单后会联系你。" + reply["text"]
            return {**reply, "_engine": "rule"}
        _reset_draft(state)

    if _is_cancel(text) and state.get("status") == "awaiting_confirm":
        _reset_draft(state)
        return {"text": "好的，这次先不下单。需要重新安排随时告诉我。", "_engine": "rule"}

    if state.get("status") == "awaiting_confirm" and _is_explicit_confirmation(text):
        try:
            _create_order_from_draft(db, user, session, state)
        except AgentConflict as exc:
            return {"text": str(exc), "_engine": "rule"}
        return {**_created_reply(db, state), "_engine": "rule"}

    detected = _detect_service(text)
    if detected:
        slots["service_type"] = detected
        slots["service_name"] = SERVICE_NAMES[detected]

    if _is_urgent(text):
        slots["urgent"] = True
        slots["urgent_amount"] = (
            50.0 if any(word in text for word in ("非常急", "特别急", "立刻")) else 20.0
        )

    appointment = _parse_appointment(text)
    if appointment:
        slots["appoint_time"], slots["appoint_text"] = appointment

    matched = _match_address(db, user, text)
    if matched:
        _apply_address(slots, matched)
    elif not slots.get("address_id"):
        default = _default_address(db, user)
        if default:
            _apply_address(slots, default)

    description = _clean_description(text)
    if len(description) >= 2 and (detected or _looks_like_problem(text)):
        slots["description"] = description

    _ensure_estimate(state)
    return {"text": "", "_engine": "rule"}


# ===== 大模型引擎（function calling）=====

SYSTEM_PROMPT = """你是「自家人居家维修」的下单助手，服务对象是平台自家人的家庭成员。
你的任务是陪用户聊天、看图判断问题，并一步步把订单信息补齐。

规则：
1. 先用一句话复述你理解的问题，然后只追问一个缺失信息。
2. 用户发照片时，结合照片判断故障类型和严重程度，但不要编造照片中不存在的细节。
3. 需要地址时调用 list_addresses，让用户选择；不要自己编造地址或坐标。
4. 信息齐全后调用 prepare_order，并请用户确认订单信息。
5. 只有用户明确说「确认下单」「确认」或点击确认按钮后，才允许调用 create_order。
6. 不要在工具返回成功前声称已经下单。
7. 用简体中文，语气亲切、简短，每次回复不超过 120 字。
8. 用户询问「我的订单」「到哪了」「还要多久」时调用 list_my_orders，
   不要把它当成新的维修需求，也不要因此清空当前草稿。

服务类型只能取：electric(水电维修)、air_condition(空调维修)、appliance(家电维修)、
plumbing(管道疏通)、door_window(门窗维修)、circuit(电路检修)、furniture(家具安装)、
wall_repair(墙面修补)。"""


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "set_problem",
            "description": "记录用户描述的故障类型和问题描述",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_type": {
                        "type": "string",
                        "enum": list(SERVICE_NAMES.keys()),
                        "description": "服务类型 key",
                    },
                    "description": {"type": "string", "description": "故障现象，尽量保留用户原话"},
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "estimate_price",
            "description": "基于当前服务类型和描述生成参考价格区间",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_addresses",
            "description": "列出用户已保存的服务地址，供用户选择",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_my_orders",
            "description": "查询当前用户最近的订单和师傅进度；用户问「我的订单/到哪了」时使用",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "select_address",
            "description": "选择用户地址簿中的某个地址作为上门地址",
            "parameters": {
                "type": "object",
                "properties": {
                    "address_id": {"type": "integer", "description": "list_addresses 返回的 id"}
                },
                "required": ["address_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_appointment",
            "description": "设置上门时间，支持「明天上午」「下午三点」「尽快」等表达",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string", "description": "用户的时间表达"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_urgency",
            "description": "设置是否加急以及加急费",
            "parameters": {
                "type": "object",
                "properties": {
                    "urgent": {"type": "boolean"},
                    "urgent_amount": {"type": "number", "enum": [0, 10, 20, 50]},
                },
                "required": ["urgent"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_order",
            "description": "检查信息是否齐全并生成订单草稿，等待用户确认",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": "用户明确确认后提交订单；未确认时调用会被拒绝",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_draft",
            "description": "用户表示放弃本次下单时清空草稿",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


class _ToolRunner:
    """把模型工具调用落到本地状态，所有写操作都在服务端校验。"""

    def __init__(self, db: Session, user: User, session: AgentSession, state: dict, latest_message: str):
        self.db = db
        self.user = user
        self.session = session
        self.state = state
        self.latest_message = latest_message or ""
        self.used_order_query = False

    def dispatch(self, name: str, arguments: Any) -> dict:
        handler = getattr(self, f"tool_{name}", None)
        if not handler:
            return {"ok": False, "error": f"未知工具：{name}"}
        args = arguments if isinstance(arguments, dict) else {}
        try:
            return handler(args)
        except AgentError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception:
            logger.exception("agent tool failed: %s", name)
            return {"ok": False, "error": "工具执行失败，请换一种说法重试"}

    def _draft_state(self) -> dict:
        draft, missing = _build_draft(self.db, self.user, self.state)
        return {"draft_ready": draft is not None, "missing": missing}

    def tool_set_problem(self, args: dict) -> dict:
        description = str(args.get("description") or "").strip()
        service_type = str(args.get("service_type") or "").strip()
        if service_type and service_type not in SERVICE_NAMES:
            return {"ok": False, "error": "service_type 不在允许范围内"}
        if service_type:
            self.state["slots"]["service_type"] = service_type
            self.state["slots"]["service_name"] = SERVICE_NAMES[service_type]
        if description:
            self.state["slots"]["description"] = description[:MAX_DESCRIPTION]
        _ensure_estimate(self.state)
        return {"ok": True, **_self_state(self.state)}

    def tool_estimate_price(self, args: dict) -> dict:
        estimate = _ensure_estimate(self.state)
        if not estimate:
            return {"ok": False, "error": "还不知道服务类型，请先描述故障"}
        return {"ok": True, "estimate": _public_estimate(self.state)}

    def tool_list_addresses(self, args: dict) -> dict:
        return {"ok": True, "addresses": _address_options(self.db, self.user)}

    def tool_list_my_orders(self, args: dict) -> dict:
        self.used_order_query = True
        orders = _recent_orders_payload(self.db, self.user)
        if not orders:
            return {"ok": True, "orders": [], "hint": "该用户还没有下过单"}
        return {"ok": True, "orders": orders}

    def tool_select_address(self, args: dict) -> dict:
        address = _select_address_by_id(self.db, self.user, args.get("address_id"))
        _apply_address(self.state["slots"], address)
        return {"ok": True, "address": {"text": _address_text(address), "label": address.label}}

    def tool_set_appointment(self, args: dict) -> dict:
        parsed = _parse_appointment(str(args.get("text") or ""))
        if not parsed:
            return {
                "ok": False,
                "error": "没听懂上门时间，请给出类似「明天上午」「今天下午3点」的说法",
                "options": _time_options(),
            }
        self.state["slots"]["appoint_time"], self.state["slots"]["appoint_text"] = parsed
        return {"ok": True, "appoint_text": self.state["slots"]["appoint_text"]}

    def tool_set_urgency(self, args: dict) -> dict:
        urgent = bool(args.get("urgent"))
        amount = args.get("urgent_amount")
        try:
            amount = float(amount) if amount is not None else 0.0
        except (TypeError, ValueError):
            amount = 0.0
        if amount not in (0.0, 10.0, 20.0, 50.0):
            amount = 20.0
        self.state["slots"]["urgent"] = urgent and amount > 0
        self.state["slots"]["urgent_amount"] = amount if urgent else 0.0
        _ensure_estimate(self.state)
        return {"ok": True, "urgent": self.state["slots"]["urgent"], "urgent_amount": self.state["slots"]["urgent_amount"]}

    def tool_prepare_order(self, args: dict) -> dict:
        result = self._draft_state()
        if not result["draft_ready"]:
            return {"ok": False, **result, "hint": _missing_text(self.db, self.user, result["missing"], self.state)}
        return {"ok": True, **result, "summary": _draft_text(self.state)}

    def tool_create_order(self, args: dict) -> dict:
        if not _is_explicit_confirmation(self.latest_message):
            return {"ok": False, "error": "用户还没有明确确认，请先复述订单并等待用户确认"}
        _create_order_from_draft(self.db, self.user, self.session, self.state)
        return {"ok": True, "order": _order_public(self.db, self.state)}

    def tool_cancel_draft(self, args: dict) -> dict:
        _reset_draft(self.state)
        return {"ok": True, "status": self.state["status"]}


def _self_state(state: dict) -> dict:
    slots = state["slots"]
    return {
        "slots": {
            "service_type": slots.get("service_type"),
            "service_name": slots.get("service_name"),
            "description": slots.get("description"),
            "address_text": slots.get("address_text"),
            "appoint_text": slots.get("appoint_text"),
            "images_count": len(slots.get("images") or []),
        },
        "estimate": _public_estimate(state),
    }


def _public_estimate(state: dict) -> Optional[dict]:
    estimate = state.get("estimate")
    if not estimate:
        return None
    return {
        key: estimate.get(key)
        for key in (
            "service_type",
            "service_name",
            "min_price",
            "max_price",
            "suggested_price",
            "estimated_minutes",
        )
        if key in estimate
    }


def _extract_tool_calls(message: dict) -> List[dict]:
    calls: List[dict] = []
    for index, call in enumerate(message.get("tool_calls") or []):
        function = (call or {}).get("function") or {}
        name = function.get("name")
        if not name:
            continue
        raw_args = function.get("arguments")
        if isinstance(raw_args, str):
            try:
                arguments = json.loads(raw_args or "{}")
            except ValueError:
                arguments = {}
        elif isinstance(raw_args, dict):
            arguments = raw_args
        else:
            arguments = {}
        calls.append(
            {
                "id": call.get("id") or f"call_{index}",
                "name": name,
                "arguments": arguments,
                "raw": call,
            }
        )

    if not calls:
        legacy = message.get("function_call") or {}
        if legacy.get("name"):
            raw_args = legacy.get("arguments")
            try:
                arguments = json.loads(raw_args or "{}") if isinstance(raw_args, str) else (raw_args or {})
            except ValueError:
                arguments = {}
            calls.append(
                {
                    "id": "call_legacy",
                    "name": legacy["name"],
                    "arguments": arguments,
                    "raw": None,
                }
            )
    return calls


def _agent_models() -> Tuple[str, str]:
    provider = (settings.AI_PROVIDER or "").lower()
    if provider == "doubao":
        return "doubao-pro-32k", "doubao-vision-pro"
    return "qwen-plus", "qwen-vl-plus"


async def _llm_turn(
    db: Session,
    user: User,
    session: AgentSession,
    state: dict,
    message: str,
    image_urls: List[str],
    image_data_urls: List[str],
) -> dict:
    text_model, vision_model = _agent_models()
    llm_messages: List[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in (state.get("messages") or [])[-MAX_MESSAGE_HISTORY:]:
        if item.get("role") in {"user", "assistant"} and item.get("content"):
            llm_messages.append({"role": item["role"], "content": item["content"]})

    vision_images = list(image_data_urls)
    if not vision_images:
        vision_images = [url for url in image_urls if url.startswith(("http://", "https://"))]

    model = text_model
    if vision_images:
        model = vision_model
        content: List[dict] = [
            {"type": "text", "text": message or "请看看这些照片，判断需要什么维修服务。"}
        ]
        for url in vision_images[:3]:
            content.append({"type": "image_url", "image_url": {"url": url}})
        if llm_messages and llm_messages[-1]["role"] == "user":
            llm_messages[-1] = {"role": "user", "content": content}
        else:
            llm_messages.append({"role": "user", "content": content})

    runner = _ToolRunner(db, user, session, state, message)
    final_text = ""
    for _ in range(5):
        response = await ai_service.chat_completion(
            llm_messages,
            model=model,
            temperature=0.2,
            tools=TOOL_SCHEMAS,
            timeout=45.0,
        )
        tool_calls = _extract_tool_calls(response)
        if not tool_calls:
            final_text = str(response.get("content") or "").strip()
            break

        assistant_message: Dict[str, Any] = {
            "role": "assistant",
            "content": response.get("content") or "",
        }
        if response.get("tool_calls"):
            assistant_message["tool_calls"] = response["tool_calls"]
        elif response.get("function_call"):
            assistant_message["function_call"] = response["function_call"]
        llm_messages.append(assistant_message)

        for call in tool_calls:
            result = runner.dispatch(call["name"], call["arguments"])
            llm_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    if not final_text:
        final_text = "我先帮你记录着，麻烦再补充一下问题、地址或上门时间。"
    result = {"text": final_text, "_engine": "llm"}
    if runner.used_order_query and state.get("status") != "created":
        result["_skip_finalize"] = True
        latest = _recent_orders_payload(db, user, limit=1)
        if latest:
            result["actions"] = [
                {
                    "type": "navigate",
                    "text": "查看订单",
                    "url": f"/pages/order-detail-client/index?id={latest[0]['id']}",
                }
            ]
    return result


# ===== 回合收尾 =====

def _finalize_turn(db: Session, user: User, state: dict, reply: dict) -> dict:
    if reply.get("_skip_finalize"):
        reply.setdefault("missing", [])
        reply.setdefault("options", {})
        reply.setdefault("actions", [])
        return reply
    if state.get("status") == "created":
        order = _order_public(db, state)
        reply.setdefault("order", order)
        reply["missing"] = []
        reply["options"] = {}
        if order:
            if not reply.get("actions"):
                reply["actions"] = _order_actions(order["id"])
            if order["order_no"] not in (reply.get("text") or ""):
                reply["text"] = _compose(
                    reply.get("text"),
                    f"订单号 {order['order_no']}，师傅接单后会联系你。",
                )
        return reply
    if state.get("status") == "creating":
        reply["text"] = _compose(reply.get("text"), "订单正在提交，请稍后在订单列表查看。")
        reply["missing"] = []
        reply["options"] = {}
        return reply

    # 两个引擎共用：用户已有带定位的默认地址时自动带入，确认卡里仍会展示。
    if not state["slots"].get("address_id"):
        default_address = _default_address(db, user)
        if default_address:
            _apply_address(state["slots"], default_address)

    draft, missing = _build_draft(db, user, state)
    reply["missing"] = missing
    reply["options"] = _options_for(db, user, missing)
    if draft:
        if state.get("draft") != draft or not state.get("confirm_token"):
            state["confirm_token"] = _new_confirm_token()
        state["draft"] = draft
        state["status"] = "awaiting_confirm"

        if _phone_ready(user):
            reply["actions"] = [
                {"type": "confirm_order", "text": "确认下单", "token": state["confirm_token"]},
                {"type": "cancel_order_draft", "text": "先不下单"},
            ]
            reply["text"] = _compose(reply.get("text"), _draft_text(state))
        else:
            # 仍保留确认按钮，绑定手机号后可直接回来确认；未绑定则返回 409 提示。
            reply["actions"] = [
                {"type": "confirm_order", "text": "确认下单", "token": state["confirm_token"]},
                {"type": "cancel_order_draft", "text": "先不下单"},
                {
                    "type": "navigate",
                    "text": "去绑定手机号",
                    "url": "/pages/client-settings/index",
                },
            ]
            reply["text"] = _compose(
                reply.get("text"),
                _draft_text(state),
                "下单前还需要绑定手机号。",
            )
    else:
        state["status"] = "collecting"
        state["draft"] = None
        state["confirm_token"] = None
        if "address" in missing and not reply["options"].get("addresses"):
            reply["actions"] = [
                {
                    "type": "navigate",
                    "text": "添加服务地址",
                    "url": "/pages/address/index",
                }
            ]
        if reply.get("_engine") == "rule":
            reply["text"] = _compose(
                reply.get("text"), _missing_text(db, user, missing, state)
            )
    return reply


def _response(session: AgentSession, state: dict, reply: dict) -> dict:
    slots = state["slots"]
    draft_view = None
    if state.get("draft") and not reply.get("_skip_finalize"):
        draft_view = {
            "service_type": slots.get("service_type"),
            "service_name": slots.get("service_name"),
            "description": slots.get("description"),
            "address_id": slots.get("address_id"),
            "address_text": slots.get("address_text"),
            "appoint_time": slots.get("appoint_time"),
            "appoint_text": slots.get("appoint_text"),
            "urgent": bool(slots.get("urgent")),
            "urgent_amount": float(slots.get("urgent_amount") or 0),
            "images_count": len(slots.get("images") or []),
            "estimate": _public_estimate(state),
        }
    return {
        "session_id": session.session_no,
        "status": state.get("status") or "collecting",
        "reply": reply.get("text") or "",
        "actions": reply.get("actions") or [],
        "missing": reply.get("missing") or [],
        "options": reply.get("options") or {},
        "draft": draft_view,
        "confirm_token": state.get("confirm_token") if state.get("status") == "awaiting_confirm" else None,
        "estimate": _public_estimate(state),
        "order": reply.get("order"),
    }


# ===== 对外入口 =====

async def handle_turn(
    db: Session,
    user: User,
    *,
    session_id: Optional[str] = None,
    message: str = "",
    image_urls: Optional[List[str]] = None,
    image_base64_list: Optional[List[str]] = None,
    action: Optional[str] = None,
    confirm_token: Optional[str] = None,
) -> dict:
    session, state = _load_session(db, user, session_id)
    message = (message or "").strip()

    if action == "reset":
        state = _new_state()
        reply = {"text": "已开启新的下单对话，请告诉我哪里需要维修。", "_engine": "rule"}
        _finalize_turn(db, user, state, reply)
    elif action == "cancel":
        if state.get("status") == "awaiting_confirm":
            _reset_draft(state)
            reply = {"text": "已取消本次下单草稿。", "_engine": "rule"}
        else:
            reply = {"text": "当前没有待确认的订单。", "_engine": "rule"}
        _finalize_turn(db, user, state, reply)
    elif action == "confirm":
        if state.get("status") == "created":
            reply = _created_reply(db, state)
        else:
            if not confirm_token or confirm_token != state.get("confirm_token"):
                raise AgentConflict("确认信息已失效，请重新确认后再提交")
            _create_order_from_draft(db, user, session, state)
            reply = _created_reply(db, state)
        reply["missing"] = []
        reply["options"] = {}
        _append_message(state, "assistant", reply.get("text") or "")
    else:
        urls = _validate_image_urls(image_urls or [])
        data_urls: List[str] = []
        if image_base64_list:
            stored, data_urls = await _store_base64_images(user, image_base64_list)
            urls.extend(stored)
        _merge_images(state, urls)
        _append_message(state, "user", message or "[照片]")

        provider = (settings.AI_PROVIDER or "mock").lower()
        if provider in {"doubao", "qwen"}:
            snapshot = copy.deepcopy(state)
            try:
                reply = await _llm_turn(db, user, session, state, message, urls, data_urls)
            except Exception as exc:
                logger.exception("agent llm turn failed: session=%s", session.session_no)
                if settings.is_deployed:
                    raise ai_service.AIServiceError("智能下单助手暂不可用") from exc
                state.clear()
                state.update(snapshot)
                reply = _rule_turn(db, user, session, state, message)
        elif provider == "mock" and not settings.is_deployed:
            reply = _rule_turn(db, user, session, state, message)
        else:
            raise ai_service.AIServiceError("生产环境未配置可用的 AI 服务")

        _finalize_turn(db, user, state, reply)
        _append_message(state, "assistant", reply.get("text") or "")

    _save_session(db, session, state)
    logger.info(
        "agent turn: session=%s user=%s status=%s missing=%s",
        session.session_no,
        user.id,
        state.get("status"),
        reply.get("missing") or [],
    )
    return _response(session, state, reply)


def get_session_snapshot(db: Session, user: User, session_id: str) -> dict:
    """读取会话快照，供小程序重新进入聊天页时恢复上下文。"""
    session, state = _load_session(db, user, session_id)
    reply = {
        "text": "",
        "missing": [],
        "options": {},
        "order": _order_public(db, state) if state.get("status") == "created" else None,
    }
    if state.get("status") != "created":
        draft, missing = _build_draft(db, user, state)
        reply["missing"] = missing
        reply["options"] = _options_for(db, user, missing)
        if draft and state.get("status") == "awaiting_confirm":
            reply["actions"] = [
                {"type": "confirm_order", "text": "确认下单", "token": state.get("confirm_token")},
                {"type": "cancel_order_draft", "text": "先不下单"},
            ]
    return _response(session, state, reply)
