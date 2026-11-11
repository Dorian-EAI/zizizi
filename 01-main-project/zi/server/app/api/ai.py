"""AI 智能助手路由"""

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_current_account
from app.schemas.ai import (
    AIAnalyzeRequest,
    AIChatRequest,
    EstimateRequest,
)
from app.services import ai_service, pricing_engine
from app.utils.response import success

router = APIRouter(prefix="/api/ai", tags=["AI智能助手"])


@router.post("/analyze")
async def analyze(
    req: AIAnalyzeRequest,
    account=Depends(get_current_account),
):
    """智能估价分析 — 根据描述和图片预估维修价格"""
    if not req.description or not req.description.strip():
        raise HTTPException(status_code=400, detail="请输入问题描述")
    try:
        result = await ai_service.analyze(
            description=req.description.strip(),
            service_type=req.service_type,
            image_base64=req.image_base64,
        )
    except ai_service.AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return success(result, "分析成功")


@router.post("/chat")
async def chat(
    req: AIChatRequest,
    account=Depends(get_current_account),
):
    """智能问答 — 解答维修相关问题（价格类问题会自动调用定价引擎给出预估）"""
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="请输入问题")
    try:
        result = await ai_service.chat(
            message=req.message.strip(),
            context=req.context,
        )
    except ai_service.AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return success(result, "回复成功")


@router.post("/estimate")
async def estimate(
    req: EstimateRequest,
    account=Depends(get_current_account),
):
    """规则化估价 — 基于服务类型、关键词、紧急程度、面积等给出价格区间"""
    description = (req.description or "").strip()
    result = pricing_engine.estimate_price(
        service_type=req.service_type,
        description=description,
        images_count=req.images_count,
        urgency=req.urgency,
        city=req.city,
        area_size=req.area_size,
    )
    return success(result, "估价成功")


@router.get("/quick-questions")
async def quick_questions():
    """获取快捷问题列表（无需登录）"""
    return success(ai_service.get_quick_questions(), "success")
