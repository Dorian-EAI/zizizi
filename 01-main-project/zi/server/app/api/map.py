"""地图服务 API"""

from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from app.services import map_service
from app.dependencies import get_current_account
from app.utils.response import success

router = APIRouter(prefix="/api/map", tags=["地图服务"])


class DistanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat1: float = Field(..., ge=-90, le=90)
    lng1: float = Field(..., ge=-180, le=180)
    lat2: float = Field(..., ge=-90, le=90)
    lng2: float = Field(..., ge=-180, le=180)
    mode: Literal["driving", "straight"] = "driving"


class ReverseGeocodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class GeocodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    address: str = Field(..., min_length=2, max_length=200)
    city: str = Field("", max_length=50)


@router.post("/distance")
def calculate_distance(
    req: DistanceRequest,
    account: tuple = Depends(get_current_account),
):
    """计算两点间距离"""
    result = map_service.calculate_distance(req.lat1, req.lng1, req.lat2, req.lng2, req.mode)
    return success(data=result)


@router.post("/reverse-geocode")
def reverse_geocode(
    req: ReverseGeocodeRequest,
    account: tuple = Depends(get_current_account),
):
    """逆地址解析：经纬度 → 中文地址"""
    result = map_service.reverse_geocode(req.lat, req.lng)
    if result:
        return success(data=result)
    # 无 API Key 时返回坐标
    return success(data={"address": "", "latitude": req.lat, "longitude": req.lng, "message": "未配置地图API，无法解析地址"})


@router.post("/geocode")
def geocode(
    req: GeocodeRequest,
    account: tuple = Depends(get_current_account),
):
    """地址解析：中文地址 → 经纬度"""
    result = map_service.geocode(req.address, req.city)
    if result:
        return success(data={"latitude": result[0], "longitude": result[1]})
    return success(data={"latitude": None, "longitude": None, "message": "未配置地图API或地址无法解析"})


@router.get("/config")
def map_config(account: tuple = Depends(get_current_account)):
    """获取当前地图服务配置（前端据此判断使用哪种模式）"""
    from app.config import settings
    return success(data={
        "provider": settings.MAP_PROVIDER,
        "has_amap": bool(settings.AMAP_API_KEY),
        "has_tencent": bool(settings.TENCENT_MAP_KEY),
        "supports_route": settings.MAP_PROVIDER != "local",
    })
