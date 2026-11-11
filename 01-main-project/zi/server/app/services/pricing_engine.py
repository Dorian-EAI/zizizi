"""规则化定价引擎

基于服务类型、关键词复杂度、紧急程度、面积等因素预估维修价格。
所有价格单位为人民币元（CNY）。
"""

from typing import Optional, List, Dict, Any


# ===== 服务类型定价表 =====
# base: 基础费用（元）
# keywords: 关键词 -> 加价（元）
# base_minutes: 基础工时（分钟）
# per_keyword_minutes: 每命中一个关键词追加的工时（分钟）
SERVICE_PRICING_TABLE: Dict[str, Dict[str, Any]] = {
    "water_electric": {
        "name": "水电维修",
        "base": 80,
        "base_minutes": 60,
        "per_keyword_minutes": 10,
        "keywords": {
            "漏水": 50,
            "跳闸": 30,
            "水管": 40,
            "电线": 50,
            "开关": 20,
        },
    },
    "air_conditioner": {
        "name": "空调维修",
        "base": 120,
        "base_minutes": 90,
        "per_keyword_minutes": 20,
        "keywords": {
            "不制冷": 80,
            "漏水": 60,
            "加氟": 100,
            "安装": 150,
            "拆机": 80,
        },
    },
    "appliance": {
        "name": "家电维修",
        "base": 100,
        "base_minutes": 70,
        "per_keyword_minutes": 15,
        "keywords": {
            "不启动": 80,
            "异响": 50,
            "不加热": 60,
        },
    },
    "pipeline": {
        "name": "管道疏通",
        "base": 60,
        "base_minutes": 50,
        "per_keyword_minutes": 15,
        "keywords": {
            "严重堵塞": 80,
            "下水道": 40,
            "马桶": 30,
        },
    },
    "door_window": {
        "name": "门窗维修",
        "base": 150,
        "base_minutes": 80,
        "per_keyword_minutes": 20,
        "keywords": {
            "换玻璃": 200,
            "漏风": 50,
            "锁坏": 80,
        },
    },
    "circuit": {
        "name": "电路检修",
        "base": 100,
        "base_minutes": 60,
        "per_keyword_minutes": 15,
        "keywords": {
            "跳闸": 50,
            "短路": 80,
            "老化": 100,
            "增容": 200,
        },
    },
    "furniture": {
        "name": "家具安装",
        "base": 80,
        "base_minutes": 60,
        "per_keyword_minutes": 20,
        "keywords": {
            "拆装": 100,
            "定制": 200,
            "大件": 50,
        },
    },
    "wall": {
        "name": "墙面修补",
        "base": 100,
        "base_minutes": 90,
        "per_keyword_minutes": 25,
        "keywords": {
            "大面积": 150,
            "渗水": 100,
            "裂缝": 50,
            "刷漆": 80,
        },
    },
}

# 默认服务类型（传入未知 service_type 时回退）
DEFAULT_SERVICE_TYPE = "water_electric"

# ===== 紧急程度倍率 =====
URGENCY_MULTIPLIERS: Dict[str, float] = {
    "normal": 1.0,
    "urgent_10": 1.1,
    "urgent_20": 1.2,
    "urgent_50": 1.5,
}

# ===== 面积阈值 =====
AREA_THRESHOLD = 100  # 平方米
AREA_MULTIPLIER = 1.2

# ===== 置信度范围 =====
CONFIDENCE_MIN = 0.3
CONFIDENCE_MAX = 0.95


def _round_price(value: float) -> float:
    """价格保留 1 位小数"""
    return round(float(value), 1)


def _match_keywords(description: str, keywords: Dict[str, int]) -> List[Dict[str, Any]]:
    """在描述中匹配关键词，返回命中列表 [{keyword, fee}]"""
    matched = []
    if not description:
        return matched
    for kw, fee in keywords.items():
        if kw in description:
            matched.append({"keyword": kw, "fee": float(fee)})
    return matched


def _calc_confidence(description: str, matched_count: int, has_service_type: bool) -> float:
    """根据描述长度、关键词命中数、是否指定服务类型计算置信度

    - 描述越详细，置信度越高
    - 关键词命中越多，置信度越高
    - 显式指定服务类型，置信度更高
    - 最终裁剪到 [0.3, 0.95] 区间
    """
    confidence = CONFIDENCE_MIN  # 起点 0.3

    desc_len = len(description or "")
    # 描述长度贡献：每 10 字 +0.05，最多 +0.25
    length_bonus = min(desc_len / 10 * 0.05, 0.25)
    confidence += length_bonus

    # 关键词命中贡献：每命中一个 +0.1，最多 +0.3
    keyword_bonus = min(matched_count * 0.1, 0.3)
    confidence += keyword_bonus

    # 显式指定服务类型 +0.05
    if has_service_type:
        confidence += 0.05

    return round(min(max(confidence, CONFIDENCE_MIN), CONFIDENCE_MAX), 2)


def get_price_breakdown(base: float, keyword_fees: List[Dict[str, Any]],
                        urgency_fee: float, area_fee: float) -> List[Dict[str, Any]]:
    """构造价格明细

    Args:
        base: 基础费用
        keyword_fees: 关键词加价列表 [{keyword, fee}, ...]
        urgency_fee: 紧急加价
        area_fee: 面积加价

    Returns:
        明细列表 [{item, amount}, ...]
    """
    breakdown: List[Dict[str, Any]] = []
    breakdown.append({"item": "基础费用", "amount": _round_price(base)})
    for kw in keyword_fees:
        breakdown.append({
            "item": f"复杂度加价-{kw['keyword']}",
            "amount": _round_price(kw["fee"]),
        })
    if urgency_fee > 0:
        breakdown.append({"item": "紧急加价", "amount": _round_price(urgency_fee)})
    if area_fee > 0:
        breakdown.append({"item": "大面积加价", "amount": _round_price(area_fee)})
    return breakdown


def estimate_price(service_type: Optional[str] = None,
                   description: Optional[str] = None,
                   images_count: int = 0,
                   urgency: str = "normal",
                   city: Optional[str] = None,
                   area_size: Optional[float] = None) -> Dict[str, Any]:
    """规则化估价

    Args:
        service_type: 服务类型代码（如 water_electric / air_conditioner 等）
        description: 问题描述
        images_count: 图片数量（影响置信度）
        urgency: 紧急程度 normal / urgent_10 / urgent_20 / urgent_50
        city: 城市（保留参数，暂未参与计价）
        area_size: 面积（平方米），>100 触发面积加价

    Returns:
        {
            min_price, max_price, suggested_price,
            confidence, estimated_minutes, breakdown
        }
    """
    has_service_type = bool(service_type)
    service_key = service_type if service_type in SERVICE_PRICING_TABLE else DEFAULT_SERVICE_TYPE
    pricing = SERVICE_PRICING_TABLE[service_key]

    base = float(pricing["base"])
    description = (description or "").strip()

    # 1. 关键词命中
    matched_keywords = _match_keywords(description, pricing["keywords"])
    keyword_total = sum(kw["fee"] for kw in matched_keywords)

    # 2. 紧急倍率
    urgency_key = urgency if urgency in URGENCY_MULTIPLIERS else "normal"
    urgency_multiplier = URGENCY_MULTIPLIERS[urgency_key]

    # 3. 面积倍率
    area_size_val = float(area_size) if area_size is not None else 0.0
    apply_area_multiplier = area_size_val > AREA_THRESHOLD
    area_multiplier = AREA_MULTIPLIER if apply_area_multiplier else 1.0

    # 4. 价格计算
    # min_price = base + 命中关键词加价（无倍率）
    base_total = base + keyword_total
    min_price = base_total

    # suggested_price = (base + 关键词加价) * 紧急倍率 * 面积倍率
    suggested_price = base_total * urgency_multiplier * area_multiplier

    # max_price = suggested_price 上浮 20%（考虑现场不可预见因素）
    max_price = suggested_price * 1.2

    # 紧急加价 = base_total * (urgency_multiplier - 1)
    urgency_fee = base_total * (urgency_multiplier - 1.0)
    # 面积加价 = base_total * urgency_multiplier * (area_multiplier - 1)
    area_fee = base_total * urgency_multiplier * (area_multiplier - 1.0)

    # 5. 工时估算
    estimated_minutes = int(pricing["base_minutes"]
                            + len(matched_keywords) * pricing["per_keyword_minutes"])
    # 紧急程度略微影响工时（加急单通常现场更复杂）
    if urgency_key != "normal":
        estimated_minutes = int(estimated_minutes * 1.1)

    # 6. 置信度
    confidence = _calc_confidence(description, len(matched_keywords), has_service_type)
    # 有图片时小幅提升置信度
    if images_count and images_count > 0:
        confidence = round(min(confidence + 0.05 * min(images_count, 2), CONFIDENCE_MAX), 2)

    # 7. 明细
    breakdown = get_price_breakdown(base, matched_keywords, urgency_fee, area_fee)

    return {
        "service_type": service_key,
        "service_name": pricing["name"],
        "min_price": _round_price(min_price),
        "max_price": _round_price(max_price),
        "suggested_price": _round_price(suggested_price),
        "confidence": confidence,
        "estimated_minutes": estimated_minutes,
        "breakdown": breakdown,
    }


# ===== 服务类型关键词识别（用于 chat 场景从自然语言推断服务类型）=====

# 自然语言关键词 -> pricing_engine 服务类型
NATURAL_LANGUAGE_KEYWORD_MAP: List[tuple] = [
    (["空调", "制冷", "加氟"], "air_conditioner"),
    (["水管", "漏水", "水电", "龙头", "马桶漏水"], "water_electric"),
    (["家电", "洗衣机", "冰箱", "电视", "热水器", "油烟机", "微波炉"], "appliance"),
    (["管道", "堵塞", "下水道", "马桶堵", "地漏"], "pipeline"),
    (["门", "窗", "玻璃", "门锁", "漏风"], "door_window"),
    (["电路", "跳闸", "短路", "电线", "插座"], "circuit"),
    (["家具", "柜子", "床", "桌子", "拆装"], "furniture"),
    (["墙面", "墙皮", "裂缝", "掉皮", "渗水", "刷漆"], "wall"),
]


def detect_service_type_from_text(text: str) -> Optional[str]:
    """从自然语言文本中识别服务类型，无法识别时返回 None"""
    if not text:
        return None
    for keywords, service_type in NATURAL_LANGUAGE_KEYWORD_MAP:
        for kw in keywords:
            if kw in text:
                return service_type
    return None
