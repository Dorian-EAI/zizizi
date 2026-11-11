"""AI 智能估价与问答服务

支持三种模式：
- mock: 纯代码模拟，关键词匹配
- doubao: 火山引擎豆包大模型（OpenAI 兼容接口）
- qwen: 通义千问大模型（OpenAI 兼容接口）
"""

import json
import random
from typing import Optional

import httpx

from app.config import settings
from app.services import pricing_engine
from app.utils.logger import get_logger


logger = get_logger(__name__)


class AIServiceError(RuntimeError):
    """真实 AI 服务未配置或暂不可用。"""


# ===== 预设服务类型价格表 =====
SERVICE_PRICE_TABLE = {
    "aircon": {"name": "空调维修", "min": 100, "max": 300, "time": "40-80分钟", "parts": ["滤网", "制冷剂", "压缩机"]},
    "electric": {"name": "水电维修", "min": 80, "max": 200, "time": "30-60分钟", "parts": ["开关", "电线", "插座"]},
    "appliance": {"name": "家电维修", "min": 100, "max": 400, "time": "40-90分钟", "parts": ["配件"]},
    "plumbing": {"name": "管道疏通", "min": 70, "max": 180, "time": "30-60分钟", "parts": ["管道", "地漏"]},
    "door_window": {"name": "门窗维修", "min": 80, "max": 250, "time": "30-70分钟", "parts": ["门锁", "合页"]},
    "circuit": {"name": "电路检修", "min": 90, "max": 220, "time": "20-50分钟", "parts": ["开关", "电线"]},
    "furniture": {"name": "家具安装", "min": 60, "max": 200, "time": "30-60分钟", "parts": ["螺丝", "配件"]},
    "wall": {"name": "墙面修补", "min": 80, "max": 300, "time": "40-90分钟", "parts": ["腻子", "涂料"]},
}

# 关键词到服务类型的映射（按优先级顺序匹配）
KEYWORD_MAP = [
    (["空调"], "aircon"),
    (["水电", "电路", "跳闸"], "electric"),
    (["管道", "堵塞", "下水道", "马桶堵", "地漏"], "plumbing"),
    (["洗衣机", "冰箱", "热水器", "电视", "油烟机", "微波炉"], "appliance"),
    (["门", "窗"], "door_window"),
    (["家具", "柜子", "床", "桌子"], "furniture"),
    (["墙面", "墙皮", "裂缝", "掉皮", "渗水"], "wall"),
]

# 快捷问题列表
QUICK_QUESTIONS = [
    {"id": "price", "text": "维修价格怎么算？"},
    {"id": "process", "text": "怎么下单预约？"},
    {"id": "warranty", "text": "维修有保修吗？"},
    {"id": "worker", "text": "师傅靠谱吗？"},
    {"id": "payment", "text": "支持哪些支付方式？"},
    {"id": "refund", "text": "不满意能退款吗？"},
]

ANALYZE_SYSTEM_PROMPT = """你是一个专业的居家维修估价助手。请根据用户的问题描述和图片（如有），分析维修需求并返回 JSON 格式的估价结果。

返回的 JSON 必须包含以下字段：
- service_type: 服务类型代码，取值范围 aircon(空调维修)/electric(水电维修)/appliance(家电维修)/plumbing(管道疏通)/door_window(门窗维修)/circuit(电路检修)/furniture(家具安装)/wall(墙面修补)
- service_name: 服务类型中文名称
- confidence: 置信度 0-1 之间的浮点数
- problem_type: 问题类型简述
- severity: 严重程度 low/medium/high
- severity_text: 严重程度中文 low=轻微 medium=中等 high=严重
- estimated_price_min: 最低估价（数字）
- estimated_price_max: 最高估价（数字）
- estimated_time: 预计耗时文字描述
- suggestion: 维修建议
- parts: 可能需要的配件数组

只返回纯 JSON，不要包含 markdown 代码块标记或其他文字。"""

CHAT_SYSTEM_PROMPT = (
    "你是「自家人居家维修」平台的智能客服助手，负责解答用户关于家电维修、"
    "水电维修、管道疏通等居家维修问题。请用简洁友好的中文回答，每次回答不超过 200 字。"
)


# ===== mock 模式实现 =====

def _match_service_type(description: str) -> str:
    """通过关键词匹配服务类型"""
    for keywords, service_type in KEYWORD_MAP:
        for kw in keywords:
            if kw in description:
                return service_type
    return "electric"  # 默认归为水电维修


def _guess_problem_type(description: str, service_type: str) -> str:
    """根据描述推断问题类型"""
    desc = description
    if service_type == "aircon":
        if "不制冷" in desc or "不凉" in desc:
            return "空调不制冷"
        if "不制热" in desc:
            return "空调不制热"
        if "漏水" in desc or "滴水" in desc:
            return "空调漏水"
        if "噪音" in desc or "响" in desc:
            return "空调异响"
        if "不开机" in desc or "启动" in desc:
            return "空调无法启动"
        return "空调故障"
    if service_type == "electric":
        if "跳闸" in desc or "断电" in desc:
            return "频繁跳闸"
        if "插座" in desc:
            return "插座故障"
        if "开关" in desc:
            return "开关损坏"
        if "漏水" in desc:
            return "水管漏水"
        return "水电故障"
    if service_type == "plumbing":
        if "堵塞" in desc or "堵" in desc:
            return "管道堵塞"
        if "漏水" in desc:
            return "管道漏水"
        if "马桶" in desc:
            return "马桶故障"
        return "管道故障"
    if service_type == "appliance":
        for name in ["洗衣机", "冰箱", "热水器", "电视", "油烟机", "微波炉"]:
            if name in desc:
                return f"{name}故障"
        return "家电故障"
    if service_type == "door_window":
        if "锁" in desc:
            return "门锁故障"
        if "玻璃" in desc:
            return "门窗玻璃损坏"
        return "门窗故障"
    if service_type == "furniture":
        return "家具安装/维修"
    if service_type == "wall":
        if "裂缝" in desc:
            return "墙面裂缝"
        if "掉皮" in desc or "起皮" in desc:
            return "墙皮脱落"
        if "渗水" in desc:
            return "墙面渗水"
        return "墙面破损"
    return "维修需求"


def _guess_severity(description: str) -> tuple[str, str]:
    """根据描述推断严重程度，返回 (severity, severity_text)"""
    desc = description
    if any(kw in desc for kw in ["紧急", "急", "马上", "立刻", "无法", "完全", "严重"]):
        return "high", "严重"
    if any(kw in desc for kw in ["不能用", "坏了", "影响", "不方便"]):
        return "medium", "中等"
    return "low", "轻微"


def _build_suggestion(service_type: str) -> str:
    """根据服务类型生成建议"""
    suggestions = {
        "aircon": "可能是缺氟或滤网堵塞，建议先检查滤网是否需要清洗",
        "electric": "建议先检查电箱是否跳闸，不要自行拆卸带电部件，注意用电安全",
        "plumbing": "建议先不要继续使用相关设施，避免污水反溢造成更大损失",
        "appliance": "建议先断电检查，不要强行启动，等待师傅上门检测",
        "door_window": "建议先检查是否有明显松动，注意安全避免夹手",
        "circuit": "建议先断开相关回路电源，不要触摸裸露线路",
        "furniture": "建议清点配件是否齐全，准备安装空间",
        "wall": "建议先清理墙面基层，保持干燥以便施工",
    }
    return suggestions.get(service_type, "建议预约师傅上门检测后报价")


def _mock_analyze(description: str, service_type: Optional[str], image_base64: Optional[str]) -> dict:
    """mock 模式分析"""
    # 确定服务类型
    if service_type and service_type in SERVICE_PRICE_TABLE:
        final_type = service_type
    else:
        final_type = _match_service_type(description)

    price_info = SERVICE_PRICE_TABLE[final_type]
    problem_type = _guess_problem_type(description, final_type)
    severity, severity_text = _guess_severity(description)
    suggestion = _build_suggestion(final_type)

    # 根据严重程度调整价格区间
    price_min = float(price_info["min"])
    price_max = float(price_info["max"])
    if severity == "high":
        price_min = round(price_min * 1.3)
        price_max = round(price_max * 1.3)
    elif severity == "medium":
        price_min = round(price_min * 1.1)
        price_max = round(price_max * 1.1)

    # 置信度：有图片或明确服务类型时更高
    confidence = 0.85
    if image_base64:
        confidence += 0.05
    if service_type:
        confidence += 0.05
    confidence = round(confidence + random.uniform(-0.02, 0.05), 2)
    confidence = min(confidence, 0.99)

    return {
        "service_type": final_type,
        "service_name": price_info["name"],
        "confidence": confidence,
        "problem_type": problem_type,
        "severity": severity,
        "severity_text": severity_text,
        "estimated_price_min": float(price_min),
        "estimated_price_max": float(price_max),
        "estimated_time": price_info["time"],
        "suggestion": suggestion,
        "parts": list(price_info["parts"]),
    }


def _mock_chat(message: str, context: Optional[str]) -> dict:
    """mock 模式智能问答"""
    msg = message
    # 价格类问题
    if any(kw in msg for kw in ["价格", "多少钱", "费用", "报价", "收费"]):
        return {
            "text": "我们的维修价格根据服务类型和故障程度而定。空调维修 100-300 元，水电维修 80-200 元，管道疏通 70-180 元。您可以使用「AI 智能估价」功能获取更准确的报价预估哦～",
            "actions": [
                {"text": "智能估价", "type": "navigate", "url": "/pages/ai/analyze"},
            ],
        }
    # 流程类问题
    if any(kw in msg for kw in ["下单", "预约", "流程", "怎么操作", "怎么用"]):
        return {
            "text": "下单流程很简单：1️⃣ 在首页选择服务类型；2️⃣ 填写问题描述并上传照片；3️⃣ 师傅竞价后选择心仪的师傅；4️⃣ 师傅上门服务；5️⃣ 服务完成后在线支付并评价。",
            "actions": [
                {"text": "去下单", "type": "navigate", "url": "/pages/order/create"},
            ],
        }
    # 保修类问题
    if any(kw in msg for kw in ["保修", "售后", "质保"]):
        return {
            "text": "我们提供 90 天质保服务！质保期内同一故障免费上门维修。如遇售后问题，可在订单详情页申请售后，我们会第一时间为您处理。",
            "actions": [
                {"text": "我的订单", "type": "navigate", "url": "/pages/order/list"},
            ],
        }
    # 师傅类问题
    if any(kw in msg for kw in ["师傅", "技工", "认证", "靠谱"]):
        return {
            "text": "平台所有师傅都经过实名认证、技能审核和背景调查，持证上岗。您可以在师傅详情页查看评分、服务次数和用户评价，放心选择～",
            "actions": [],
        }
    # 支付类问题
    if any(kw in msg for kw in ["支付", "付款", "结账", "钱包", "充值"]):
        return {
            "text": "目前支持微信支付和钱包余额支付；支付宝尚未开放。完成支付后可对师傅进行评价。",
            "actions": [
                {"text": "我的钱包", "type": "navigate", "url": "/pages/wallet/index"},
            ],
        }
    # 退款类问题
    if any(kw in msg for kw in ["退款", "退钱", "不满意", "投诉"]):
        return {
            "text": "如果您对服务不满意，可在订单完成后 24 小时内申请售后。我们会核实情况，如确认师傅服务问题，将为您全额或部分退款。客服电话：400-xxx-xxxx。",
            "actions": [
                {"text": "联系客服", "type": "navigate", "url": "/pages/service/contact"},
            ],
        }
    # 估价类问题
    if any(kw in msg for kw in ["估价", "评估", "检测"]):
        return {
            "text": "您可以使用 AI 智能估价功能，描述问题或上传照片，AI 会帮您预估维修价格和所需时间，方便您做预算参考～",
            "actions": [
                {"text": "智能估价", "type": "navigate", "url": "/pages/ai/analyze"},
            ],
        }
    # 加急类问题
    if any(kw in msg for kw in ["加急", "紧急", "快点"]):
        return {
            "text": "下单时可以勾选「加急」选项，订单会优先推送给附近在线师傅，通常能更快上门。加急服务会收取少量加急费。",
            "actions": [
                {"text": "去下单", "type": "navigate", "url": "/pages/order/create"},
            ],
        }
    # 默认回复
    return {
        "text": "您好！我是自家人居家维修智能助手，可以为您解答维修价格、下单流程、售后服务等问题。您也可以直接描述故障问题，我帮您预估维修费用～",
        "actions": [
            {"text": "智能估价", "type": "navigate", "url": "/pages/ai/analyze"},
            {"text": "去下单", "type": "navigate", "url": "/pages/order/create"},
        ],
    }


# ===== 大模型 API 调用 =====

def _parse_ai_json(content: str) -> dict:
    """解析 AI 返回的 JSON 内容，兼容 markdown 代码块"""
    content = content.strip()
    # 去除 markdown 代码块
    if content.startswith("```"):
        lines = content.split("\n")
        lines = lines[1:]  # 去掉首行 ```json 或 ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    return json.loads(content)


def _normalize_analyze_result(result: dict) -> dict:
    """规范化分析结果，补全缺失字段"""
    defaults = {
        "service_type": "electric",
        "service_name": "水电维修",
        "confidence": 0.8,
        "problem_type": "未知问题",
        "severity": "low",
        "severity_text": "轻微",
        "estimated_price_min": 0.0,
        "estimated_price_max": 0.0,
        "estimated_time": "30-60分钟",
        "suggestion": "建议预约师傅上门检测后报价",
        "parts": [],
    }
    # 根据 service_type 补全 service_name 和 parts
    if "service_type" in result and result["service_type"] in SERVICE_PRICE_TABLE:
        info = SERVICE_PRICE_TABLE[result["service_type"]]
        defaults["service_name"] = info["name"]
        defaults["parts"] = list(info["parts"])
        defaults["estimated_time"] = info["time"]
    for key, val in defaults.items():
        if key not in result or result[key] is None:
            result[key] = val
    # 确保数值类型正确
    result["estimated_price_min"] = float(result["estimated_price_min"])
    result["estimated_price_max"] = float(result["estimated_price_max"])
    result["confidence"] = float(result["confidence"])
    return result


async def chat_completion(
    messages: list,
    model: str,
    temperature: float = 0.3,
    tools: Optional[list] = None,
    timeout: float = 30.0,
) -> dict:
    """调用 OpenAI 兼容的 chat/completions，返回 message 对象

    传入 tools 时启用 function calling；由调用方负责工具循环与结果校验。
    """
    headers = {
        "Authorization": f"Bearer {settings.AI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    url = settings.AI_API_BASE.rstrip("/") + "/chat/completions"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]


async def _call_llm(messages: list, model: str, temperature: float = 0.3) -> str:
    """调用大模型 API（OpenAI 兼容格式），返回原始文本内容"""
    message = await chat_completion(messages, model=model, temperature=temperature)
    return message.get("content") or ""


async def _llm_analyze(description: str, service_type: Optional[str], image_base64: Optional[str],
                      text_model: str, vision_model: str) -> dict:
    """通用大模型分析（doubao/qwen 共用）"""
    user_text = f"问题描述：{description}"
    if service_type:
        user_text += f"\n用户预设服务类型：{service_type}"

    if image_base64:
        model = vision_model
        user_content = [
            {"type": "text", "text": user_text + "\n（附带问题图片，请结合图片分析）"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
        ]
    else:
        model = text_model
        user_content = user_text

    messages = [
        {"role": "system", "content": ANALYZE_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    try:
        content = await _call_llm(messages, model)
        result = _parse_ai_json(content)
        return _normalize_analyze_result(result)
    except Exception as exc:
        logger.exception("AI analyze request failed")
        if settings.is_deployed:
            raise AIServiceError("智能分析服务暂不可用") from exc
        return _mock_analyze(description, service_type, image_base64)


async def _llm_chat(message: str, context: Optional[str], text_model: str) -> dict:
    """通用大模型问答（doubao/qwen 共用）"""
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    if context:
        messages.append({"role": "system", "content": f"对话上下文：{context}"})
    messages.append({"role": "user", "content": message})
    try:
        text = await _call_llm(messages, text_model, temperature=0.5)
        return {"text": text.strip(), "actions": []}
    except Exception as exc:
        logger.exception("AI chat request failed")
        if settings.is_deployed:
            raise AIServiceError("智能问答服务暂不可用") from exc
        return _mock_chat(message, context)


# ===== 对外接口 =====

# 价格类问题关键词
PRICE_QUESTION_KEYWORDS = ["价格", "多少钱", "费用", "报价", "收费"]


def _handle_pricing_question(message: str) -> Optional[dict]:
    """处理价格类问题：识别服务类型并调用 pricing_engine 给出预估

    若消息不包含价格关键词，或无法识别服务类型，返回 None（由上层走默认问答流程）。
    """
    if not any(kw in message for kw in PRICE_QUESTION_KEYWORDS):
        return None

    service_type = pricing_engine.detect_service_type_from_text(message)
    if not service_type:
        # 未识别到具体服务类型，走原有 mock 兜底回复
        return None

    estimate = pricing_engine.estimate_price(
        service_type=service_type,
        description=message,
        images_count=0,
        urgency="normal",
    )

    text = (
        f"根据您的描述，识别为「{estimate['service_name']}」服务。"
        f"预估价格区间 {estimate['min_price']}-{estimate['max_price']} 元，"
        f"建议报价 {estimate['suggested_price']} 元，"
        f"预计耗时约 {estimate['estimated_minutes']} 分钟。"
        f"实际费用以师傅上门检测后为准，您可以在下单时使用「智能估价」获取更精确的报价～"
    )
    return {
        "text": text,
        "actions": [
            {"text": "智能估价", "type": "navigate", "url": "/pages/ai/analyze"},
            {"text": "去下单", "type": "navigate", "url": "/pages/order/create"},
        ],
        "estimate": estimate,
    }


async def analyze(description: str, service_type: Optional[str] = None, image_base64: Optional[str] = None) -> dict:
    """分析用户描述和图片，返回推荐服务类型和价格预估

    Args:
        description: 问题描述
        service_type: 用户预设的服务类型（可选）
        image_base64: 图片 base64 编码（可选）

    Returns:
        包含 service_type / service_name / confidence / problem_type /
        severity / estimated_price_min / estimated_price_max / estimated_time /
        suggestion / parts 的字典
    """
    provider = (settings.AI_PROVIDER or "mock").lower()
    if provider == "doubao":
        return await _llm_analyze(description, service_type, image_base64,
                                  text_model="doubao-pro-32k", vision_model="doubao-vision-pro")
    if provider == "qwen":
        return await _llm_analyze(description, service_type, image_base64,
                                  text_model="qwen-plus", vision_model="qwen-vl-plus")
    if provider == "mock" and not settings.is_deployed:
        return _mock_analyze(description, service_type, image_base64)
    raise AIServiceError("生产环境未配置可用的 AI 服务")


async def chat(message: str, context: Optional[str] = None) -> dict:
    """智能问答

    Args:
        message: 用户消息
        context: 对话上下文（可选）

    Returns:
        包含 text / actions 的字典（价格类问题会附带 estimate 字段）
    """
    # 价格类问题优先走规则化定价引擎，给出确定性预估
    pricing_answer = _handle_pricing_question(message)
    if pricing_answer is not None:
        return pricing_answer

    provider = (settings.AI_PROVIDER or "mock").lower()
    if provider == "doubao":
        return await _llm_chat(message, context, text_model="doubao-pro-32k")
    if provider == "qwen":
        return await _llm_chat(message, context, text_model="qwen-plus")
    if provider == "mock" and not settings.is_deployed:
        return _mock_chat(message, context)
    raise AIServiceError("生产环境未配置可用的 AI 服务")


def get_quick_questions() -> list:
    """获取快捷问题列表"""
    return QUICK_QUESTIONS
