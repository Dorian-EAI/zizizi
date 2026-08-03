"""地图服务 API"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from app.services import map_service
from app.dependencies import get_current_account
from app.utils.response import success

router = APIRouter(prefix="/api/map", tags=["地图服务"])


@router.get("/distance")
async def calculate_distance(
    lat1: float = Query(..., ge=-90, le=90, description="起点纬度"),
    lng1: float = Query(..., ge=-180, le=180, description="起点经度"),
    lat2: float = Query(..., ge=-90, le=90, description="终点纬度"),
    lng2: float = Query(..., ge=-180, le=180, description="终点经度"),
    mode: str = Query("driving", pattern="^(driving|straight)$", description="driving=驾车距离, straight=直线距离"),
    account: tuple = Depends(get_current_account),
):
    """计算两点间距离"""
    result = map_service.calculate_distance(lat1, lng1, lat2, lng2, mode)
    return success(data=result)


@router.get("/reverse-geocode")
async def reverse_geocode(
    lat: float = Query(..., ge=-90, le=90, description="纬度"),
    lng: float = Query(..., ge=-180, le=180, description="经度"),
    account: tuple = Depends(get_current_account),
):
    """逆地址解析：经纬度 → 中文地址"""
    result = map_service.reverse_geocode(lat, lng)
    if result:
        return success(data=result)
    # 无 API Key 时返回坐标
    return success(data={"address": "", "latitude": lat, "longitude": lng, "message": "未配置地图API，无法解析地址"})


@router.get("/geocode")
async def geocode(
    address: str = Query(..., min_length=2, max_length=200, description="中文地址"),
    city: str = Query("", max_length=50, description="城市（可选）"),
    account: tuple = Depends(get_current_account),
):
    """地址解析：中文地址 → 经纬度"""
    result = map_service.geocode(address, city)
    if result:
        return success(data={"latitude": result[0], "longitude": result[1]})
    return success(data={"latitude": None, "longitude": None, "message": "未配置地图API或地址无法解析"})


@router.get("/config")
async def map_config(account: tuple = Depends(get_current_account)):
    """获取当前地图服务配置（前端据此判断使用哪种模式）"""
    from app.config import settings
    return success(data={
        "provider": settings.MAP_PROVIDER,
        "has_amap": bool(settings.AMAP_API_KEY),
        "has_tencent": bool(settings.TENCENT_MAP_KEY),
        "supports_route": settings.MAP_PROVIDER != "local",
    })
