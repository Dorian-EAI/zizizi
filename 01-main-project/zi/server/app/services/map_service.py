"""地图服务 — 距离计算、地址逆解析、路线规划

支持三种模式：
  - local:   纯 Haversine 直线距离，无需任何外部 API Key
  - amap:    高德 Web 服务 API（路径规划 + 逆地址解析）
  - tencent: 腾讯位置服务 API

配置项在 config.py:
  MAP_PROVIDER = "local" | "amap" | "tencent"
  AMAP_API_KEY = "高德 Web Key"
  TENCENT_MAP_KEY = "腾讯位置服务 Key"
"""

import math
import logging
from typing import Optional, Tuple, Dict, Any

from app.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# 基础：Haversine 直线距离（始终可用，无需 API Key）
# ============================================================

EARTH_RADIUS = 6371000  # 地球半径（米）


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """计算两个 GPS 坐标之间的球面直线距离（米）

    公式: a = sin²(Δφ/2) + cos(φ1)·cos(φ2)·sin²(Δλ/2)
          c = 2·atan2(√a, √(1-a))
          d = R·c
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(EARTH_RADIUS * c, 1)


def haversine_distance_text(distance_m: float) -> str:
    """将距离（米）转为友好的文本"""
    if distance_m < 1000:
        return f"{int(distance_m)}m"
    return f"{distance_m / 1000:.1f}km"


# ============================================================
# 统一对外接口
# ============================================================

def calculate_distance(
    lat1: float, lng1: float,
    lat2: float, lng2: float,
    mode: str = "driving",
) -> Dict[str, Any]:
    """计算两点间距离

    Args:
        mode: "driving" 驾车距离 / "straight" 直线距离

    Returns:
        {
            "distance_meters": float,      # 距离（米）
            "distance_text": str,          # 友好文本
            "duration_seconds": int|None,  # 预计耗时（秒），直线模式为 None
            "route_mode": str,             # 使用的计算模式
        }
    """
    # 直线模式 / 没有配置 API Key
    if mode == "straight" or settings.MAP_PROVIDER == "local":
        dist = haversine_distance(lat1, lng1, lat2, lng2)
        return {
            "distance_meters": dist,
            "distance_text": haversine_distance_text(dist),
            "duration_seconds": None,
            "route_mode": "haversine",
        }

    # 高德 API
    if settings.MAP_PROVIDER == "amap" and settings.AMAP_API_KEY:
        result = _amap_route_distance(lat1, lng1, lat2, lng2, mode)
        if result:
            return result
        # 降级到直线
        logger.warning("[地图服务] 高德 API 调用失败，降级为直线距离")

    # 腾讯 API
    if settings.MAP_PROVIDER == "tencent" and settings.TENCENT_MAP_KEY:
        result = _tencent_route_distance(lat1, lng1, lat2, lng2, mode)
        if result:
            return result
        logger.warning("[地图服务] 腾讯 API 调用失败，降级为直线距离")

    # 降级
    dist = haversine_distance(lat1, lng1, lat2, lng2)
    return {
        "distance_meters": dist,
        "distance_text": haversine_distance_text(dist),
        "duration_seconds": None,
        "route_mode": "haversine_fallback",
    }


def reverse_geocode(lat: float, lng: float) -> Optional[Dict[str, str]]:
    """逆地址解析：经纬度 → 中文地址

    Returns:
        {
            "address": "福建省厦门市思明区...",
            "province": "福建省",
            "city": "厦门市",
            "district": "思明区",
            "street": "...",
        }
        或 None（解析失败）
    """
    if settings.MAP_PROVIDER == "amap" and settings.AMAP_API_KEY:
        return _amap_reverse_geocode(lat, lng)
    if settings.MAP_PROVIDER == "tencent" and settings.TENCENT_MAP_KEY:
        return _tencent_reverse_geocode(lat, lng)
    # 无 API Key 时返回空
    return None


def geocode(address: str, city: str = "") -> Optional[Tuple[float, float]]:
    """地址解析：中文地址 → 经纬度

    Returns:
        (latitude, longitude) 或 None
    """
    if settings.MAP_PROVIDER == "amap" and settings.AMAP_API_KEY:
        return _amap_geocode(address, city)
    if settings.MAP_PROVIDER == "tencent" and settings.TENCENT_MAP_KEY:
        return _tencent_geocode(address, city)
    return None


# ============================================================
# 高德 Web 服务 API
# ============================================================

def _amap_route_distance(lat1, lng1, lat2, lng2, mode="driving") -> Optional[Dict]:
    """高德路径规划"""
    try:
        import httpx
        url = "https://restapi.amap.com/v3/direction/driving"
        params = {
            "key": settings.AMAP_API_KEY,
            "origin": f"{lng1},{lat1}",
            "destination": f"{lng2},{lat2}",
            "strategy": 0,  # 速度优先
            "extensions": "base",
        }
        with httpx.Client(timeout=5) as client:
            resp = client.get(url, params=params)
            data = resp.json()

        if data.get("status") != "1":
            logger.error(f"[高德] 路径规划失败: {data.get('info')}")
            return None

        route = data.get("route", {}).get("paths", [{}])[0]
        distance_m = float(route.get("distance", 0))
        duration_s = int(route.get("duration", 0))
        return {
            "distance_meters": distance_m,
            "distance_text": haversine_distance_text(distance_m),
            "duration_seconds": duration_s,
            "route_mode": "amap_driving",
        }
    except Exception:
        logger.error("[高德] 路径规划调用异常")
        return None


def _amap_reverse_geocode(lat: float, lng: float) -> Optional[Dict]:
    """高德逆地址解析"""
    try:
        import httpx
        url = "https://restapi.amap.com/v3/geocode/regeo"
        params = {
            "key": settings.AMAP_API_KEY,
            "location": f"{lng},{lat}",
            "extensions": "base",
        }
        with httpx.Client(timeout=5) as client:
            resp = client.get(url, params=params)
            data = resp.json()

        if data.get("status") != "1":
            return None

        comp = data.get("regeocode", {}).get("addressComponent", {})
        return {
            "address": data.get("regeocode", {}).get("formatted_address", ""),
            "province": comp.get("province", "") or "",
            "city": comp.get("city", "") or "",
            "district": comp.get("district", "") or "",
            "street": comp.get("street", "") or "",
        }
    except Exception:
        logger.error("[高德] 逆地址解析异常")
        return None


def _amap_geocode(address: str, city: str = "") -> Optional[Tuple[float, float]]:
    """高德地址解析"""
    try:
        import httpx
        url = "https://restapi.amap.com/v3/geocode/geo"
        params = {
            "key": settings.AMAP_API_KEY,
            "address": address,
            "city": city,
        }
        with httpx.Client(timeout=5) as client:
            resp = client.get(url, params=params)
            data = resp.json()

        if data.get("status") != "1":
            return None

        geocodes = data.get("geocodes", [])
        if not geocodes:
            return None

        location = geocodes[0].get("location", "")  # "lng,lat"
        if "," not in location:
            return None
        lng_str, lat_str = location.split(",")
        return (float(lat_str), float(lng_str))
    except Exception:
        logger.error("[高德] 地址解析异常")
        return None


# ============================================================
# 腾讯位置服务 API
# ============================================================

def _tencent_route_distance(lat1, lng1, lat2, lng2, mode="driving") -> Optional[Dict]:
    """腾讯路径规划"""
    try:
        import httpx
        url = "https://apis.map.qq.com/ws/distance/v1/"
        params = {
            "key": settings.TENCENT_MAP_KEY,
            "mode": "driving",
            "from": f"{lat1},{lng1}",
            "to": f"{lat2},{lng2}",
        }
        with httpx.Client(timeout=5) as client:
            resp = client.get(url, params=params)
            data = resp.json()

        if data.get("status") != 0:
            logger.error(f"[腾讯] 路径规划失败: {data.get('message')}")
            return None

        elements = data.get("result", {}).get("elements", [])
        if not elements:
            return None

        el = elements[0]
        distance_m = float(el.get("distance", 0))
        duration_s = int(el.get("duration", 0))
        return {
            "distance_meters": distance_m,
            "distance_text": haversine_distance_text(distance_m),
            "duration_seconds": duration_s,
            "route_mode": "tencent_driving",
        }
    except Exception:
        logger.error("[腾讯] 路径规划调用异常")
        return None


def _tencent_reverse_geocode(lat: float, lng: float) -> Optional[Dict]:
    """腾讯逆地址解析"""
    try:
        import httpx
        url = "https://apis.map.qq.com/ws/geocoder/v1/"
        params = {
            "key": settings.TENCENT_MAP_KEY,
            "location": f"{lat},{lng}",
        }
        with httpx.Client(timeout=5) as client:
            resp = client.get(url, params=params)
            data = resp.json()

        if data.get("status") != 0:
            return None

        result = data.get("result", {})
        addr_comp = result.get("address_components", {})
        return {
            "address": result.get("address", ""),
            "province": addr_comp.get("province", ""),
            "city": addr_comp.get("city", ""),
            "district": addr_comp.get("district", ""),
            "street": addr_comp.get("street", ""),
        }
    except Exception:
        logger.error("[腾讯] 逆地址解析异常")
        return None


def _tencent_geocode(address: str, city: str = "") -> Optional[Tuple[float, float]]:
    """腾讯地址解析"""
    try:
        import httpx
        url = "https://apis.map.qq.com/ws/geocoder/v1/"
        params = {
            "key": settings.TENCENT_MAP_KEY,
            "address": address,
        }
        if city:
            params["region"] = city

        with httpx.Client(timeout=5) as client:
            resp = client.get(url, params=params)
            data = resp.json()

        if data.get("status") != 0:
            return None

        location = data.get("result", {}).get("location", {})
        lat = location.get("lat")
        lng = location.get("lng")
        if lat is None or lng is None:
            return None
        return (float(lat), float(lng))
    except Exception:
        logger.error("[腾讯] 地址解析异常")
        return None


# ============================================================
# 便捷工具
# ============================================================

def parse_order_address(address_str: str) -> Optional[Dict]:
    """解析订单地址字段

    订单 address 字段可能是:
    - JSON 字符串: {"address": "...", "latitude": 24.5, "longitude": 118.1, ...}
    - 纯文本: "福建省厦门市思明区..."
    """
    if not address_str:
        return None

    import json

    # 尝试 JSON 解析
    try:
        data = json.loads(address_str)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass

    # 纯文本地址
    return {"address": address_str, "latitude": None, "longitude": None}


def get_order_coords(address_str: str) -> Tuple[Optional[float], Optional[float]]:
    """从订单地址字段提取经纬度"""
    parsed = parse_order_address(address_str)
    if not parsed:
        return None, None
    return parsed.get("latitude"), parsed.get("longitude")


def calculate_distance_for_order(
    order_address: str,
    worker_lat: float,
    worker_lng: float,
    mode: str = "driving",
) -> Optional[Dict]:
    """计算师傅当前位置到订单地址的距离

    Returns:
        距离信息 dict 或 None（订单无经纬度时）
    """
    order_lat, order_lng = get_order_coords(order_address)
    if order_lat is None or order_lng is None:
        return None
    return calculate_distance(worker_lat, worker_lng, order_lat, order_lng, mode)


def sort_orders_by_distance(
    orders: list,
    worker_lat: float,
    worker_lng: float,
) -> list:
    """对订单列表按距离排序（近→远）

    为每个订单附加 distance_info 字段
    无经纬度的订单排在最后
    """
    enriched = []
    for order in orders:
        order_lat, order_lng = get_order_coords(
            order.address if hasattr(order, "address") else order.get("address", "")
        )
        if order_lat and order_lng:
            dist_info = calculate_distance(worker_lat, worker_lng, order_lat, order_lng)
            enriched.append((order, dist_info, dist_info["distance_meters"]))
        else:
            enriched.append((order, None, float("inf")))

    enriched.sort(key=lambda x: x[2])

    return [
        {**({"__order__": o} if not isinstance(o, dict) else o),
         "distance_info": di}
        for o, di, _ in enriched
    ]
