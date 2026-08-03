"""认证相关路由"""

import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_current_worker
from app.models.user import User, Worker
from app.schemas.user import (
    WxLoginRequest,
    UpdateProfileRequest,
    SwitchRoleRequest,
    AddressCreate,
    AddressUpdate,
    AddressResponse,
    BindPhoneRequest,
    WorkerCertificationRequest,
)
from app.services import auth_service
from app.utils.response import success
from app.utils.redis_client import redis_client
from app.utils.security import decode_access_token
from app.utils.rate_limit import limiter, LIMIT_WX_LOGIN, LIMIT_WORKER_LOGIN

router = APIRouter(prefix="/api/auth", tags=["认证"])


def _safe_json(value):
    if value is None:
        return []
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return []


def _safe_certification_data(value):
    """认证快照响应白名单，避免未来误把身份证密文/明文带回客户端。"""
    parsed = _safe_json(value)
    if not isinstance(parsed, dict):
        return {}
    allowed = {
        "real_name", "phone", "id_card_masked", "id_front", "id_back",
        "certificate_images", "health_certificate", "service_city",
        "service_districts", "service_types", "price_min", "price_max",
        "submitted_at",
    }
    return {key: parsed[key] for key in allowed if key in parsed}


# ===== 登录 =====
@router.post("/wx-login")
@limiter.limit(LIMIT_WX_LOGIN)
async def wx_login(request: Request, req: WxLoginRequest, db: Session = Depends(get_db)):
    """微信登录（用户）"""
    result = await auth_service.wx_login(db, req.code, req.nickname, req.avatar)
    return success(data=result, message="登录成功")


@router.post("/worker-login")
@limiter.limit(LIMIT_WORKER_LOGIN)
async def worker_login(request: Request, req: WxLoginRequest, db: Session = Depends(get_db)):
    """微信登录（师傅）"""
    result = await auth_service.worker_login(db, req.code, req.nickname, req.avatar)
    return success(data=result, message="登录成功")


# ===== 用户信息 =====
@router.get("/me")
async def get_me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前用户信息"""
    data = auth_service.get_user_info(db, user)
    return success(data=data)


@router.get("/worker/me")
async def get_worker_me(
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """获取当前师傅信息（师傅端登录态用）"""
    certification_data = _safe_certification_data(worker.certification_data)
    status_map = {0: "unsubmitted", 1: "pending", 2: "approved", 3: "rejected"}
    data = {
        "id": worker.id,
        "nickname": worker.nickname,
        "real_name": worker.real_name,
        "avatar": worker.avatar,
        "phone": worker.phone,
        "certified": worker.certified,
        "certification_status": status_map.get(worker.certified, "unsubmitted"),
        "certification_data": certification_data,
        "skills": _safe_json(worker.skills),
        "certificates": _safe_json(worker.certificates),
        "service_types": _safe_json(worker.service_types),
        "rating": round(float(worker.rating or 5.0), 1),
        "service_count": int(worker.service_count or 0),
        "total_orders": int(worker.total_orders or 0),
        "completed_orders": int(worker.completed_orders or 0),
        "level": int(worker.level or 1),
        "balance": round(float(worker.balance or 0.0), 2),
        "is_online": bool(worker.is_online),
        "service_area": worker.service_area,
        "is_active": bool(worker.is_active),
    }
    return success(data=data)


@router.post("/worker/certification")
async def submit_worker_certification(
    request: Request,
    worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
):
    """提交或补充师傅认证资料；仅接受 worker token。

    请求体由本接口手工校验，避免框架默认 422 错误把身份证输入回显到响应。
    """
    try:
        payload = await request.json()
    except (ValueError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=400, detail="请求体不是有效 JSON") from error
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="认证申请信息格式有误")
    try:
        certification = WorkerCertificationRequest.model_validate(payload)
    except ValidationError as error:
        fields = sorted({
            ".".join(str(part) for part in item.get("loc", ())) or "request"
            for item in error.errors(include_input=False, include_context=False)
        })
        raise HTTPException(
            status_code=422,
            detail={"message": "认证申请信息格式有误", "fields": fields},
        ) from None

    result = auth_service.submit_worker_certification(db, worker, certification)
    result["application"] = _safe_certification_data(result.get("application"))
    return success(data=result, message="认证申请已提交，请等待审核")


@router.put("/profile")
async def update_profile(
    req: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新个人资料"""
    user = auth_service.update_user_profile(db, user, req)
    data = auth_service.get_user_info(db, user)
    return success(data=data, message="更新成功")


@router.post("/bind-phone")
async def bind_phone(
    req: BindPhoneRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """通过一次性短信验证码绑定或换绑手机号。"""
    user = auth_service.bind_phone(db, user, req.phone, req.verification_code)
    return success(data=auth_service.get_user_info(db, user), message="手机号绑定成功")


@router.post("/switch-role")
async def switch_role(
    req: SwitchRoleRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """切换角色"""
    user = auth_service.switch_role(db, user, req.role)
    return success(data={"role": user.role}, message="角色切换成功")


# ===== 地址管理 =====
@router.get("/addresses")
async def list_addresses(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取地址列表"""
    addresses = auth_service.get_addresses(db, user)
    data = [AddressResponse.model_validate(a).model_dump(mode="json") for a in addresses]
    return success(data=data)


@router.post("/addresses")
async def create_address(
    req: AddressCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """新增地址"""
    address = auth_service.create_address(db, user, req)
    data = AddressResponse.model_validate(address).model_dump(mode="json")
    return success(data=data, message="地址创建成功")


@router.put("/addresses/{address_id}")
async def update_address(
    address_id: int,
    req: AddressUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """编辑地址"""
    address = auth_service.update_address(db, user, address_id, req)
    data = AddressResponse.model_validate(address).model_dump(mode="json")
    return success(data=data, message="更新成功")


@router.delete("/addresses/{address_id}")
async def delete_address(
    address_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除地址"""
    auth_service.delete_address(db, user, address_id)
    return success(message="删除成功")


@router.put("/addresses/{address_id}/default")
async def set_default_address(
    address_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """设为默认地址"""
    address = auth_service.set_default_address(db, user, address_id)
    data = AddressResponse.model_validate(address).model_dump(mode="json")
    return success(data=data, message="已设为默认")


@router.post("/logout")
async def logout(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):
    """登出并递增数据库会话版本；Redis 黑名单作为额外防线。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供认证 token")
    token = authorization[len("Bearer "):]
    payload = decode_access_token(token)
    if not payload or payload.get("type") not in (None, "user", "worker"):
        raise HTTPException(status_code=401, detail="无效的认证 token")
    try:
        account_id = int(payload.get("sub"))
        token_version = int(payload.get("ver", 0))
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=401, detail="无效的认证 token") from error
    model = Worker if payload.get("type") == "worker" else User
    account = db.query(model).filter(model.id == account_id).with_for_update().first()
    if not account or token_version != int(account.token_version or 1):
        raise HTTPException(status_code=401, detail="登录状态已失效")
    account.token_version = int(account.token_version or 1) + 1
    db.commit()
    if payload.get("jti"):
        redis_client.blacklist_token(payload["jti"], expire_seconds=604800)
    return success(message="登出成功")
