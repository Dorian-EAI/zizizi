"""AI 下单 Agent 路由"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.agent import AgentTurnRequest
from app.services import agent_service, ai_service
from app.utils.rate_limit import limiter, LIMIT_AI_AGENT
from app.utils.response import success

router = APIRouter(prefix="/api/ai/agent", tags=["AI 下单助手"])


@router.post("/turn")
@limiter.limit(LIMIT_AI_AGENT)
async def agent_turn(
    request: Request,
    req: AgentTurnRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """多轮对话下单：文字 + 照片 -> 订单草稿 -> 用户确认后创建订单"""
    try:
        result = await agent_service.handle_turn(
            db,
            user,
            session_id=req.session_id,
            message=req.message,
            image_urls=req.image_urls,
            image_base64_list=req.image_base64_list,
            action=req.action,
            confirm_token=req.confirm_token,
        )
    except agent_service.AgentInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except agent_service.AgentConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ai_service.AIServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return success(result, "success")


@router.get("/session/{session_id}")
async def agent_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """恢复会话快照（小程序重新进入聊天页时使用）"""
    try:
        result = agent_service.get_session_snapshot(db, user, session_id)
    except agent_service.AgentInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except agent_service.AgentConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return success(result, "success")
