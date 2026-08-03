"""地理距离计算工具"""

import math
from typing import List, Dict, Any, Optional

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """使用 Haversine 公式计算两点间距离（公里）"""
    if None in (lat1, lng1, lat2, lng2):
        return 0.0

    rlat1 = math.radians(lat1)
    rlat2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_KM * c


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    """计算两点间距离（米，整数）"""
    return int(haversine_km(lat1, lng1, lat2, lng2) * 1000)


def _extract_latlng(item: Dict[str, Any]) -> Optional[tuple]:
    """从 dict 中提取经纬度，支持多种 key 命名"""
    lat = None
    lng = None

    for key in ("lat", "latitude", "location_lat"):
        if key in item and item[key] is not None:
            lat = float(item[key])
            break

    for key in ("lng", "lon", "longitude", "location_lng"):
        if key in item and item[key] is not None:
            lng = float(item[key])
            break

    if lat is not None and lng is not None:
        return (lat, lng)
    return None


def filter_within_radius(
    list_of_dicts: List[Dict[str, Any]],
    my_lat: float,
    my_lng: float,
    radius_km: float,
) -> List[Dict[str, Any]]:
    """过滤指定半径内的点，附加 distance_km 字段并按距离升序排序"""
    result: List[Dict[str, Any]] = []

    for item in list_of_dicts:
        latlng = _extract_latlng(item)
        if latlng is None:
            continue
        lat2, lng2 = latlng
        d = haversine_km(my_lat, my_lng, lat2, lng2)
        if d <= radius_km:
            new_item = dict(item)
            new_item["distance_km"] = round(d, 2)
            result.append(new_item)

    result.sort(key=lambda x: x.get("distance_km", 0))
    return result
