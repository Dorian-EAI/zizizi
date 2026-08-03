"""运营后台路由

安全说明：
- 所有 admin 路由均通过 get_current_admin 依赖进行 JWT 鉴权
- 高危操作（create_admin）额外要求 super_admin 角色
- 不再接受 X-Admin-Id Header 这种弱鉴权方式
- 登录接口强制限流防爆破
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.dependencies import get_current_admin, require_super_admin
from app.models.admin import Admin
from app.schemas.admin import (
    AdminCreateRequest,
    AdminLoginRequest,
    AdminLoginResponse,
    DashboardResponse,
    ToggleActiveRequest,
    UpdateOrderStatusRequest,
    WorkerCertifyRequest,
)
from app.services import admin_service
from app.utils.response import success
from app.utils.rate_limit import limiter, LIMIT_ADMIN_LOGIN
from app.utils.redis_client import redis_client
from app.utils.security import decode_access_token

router = APIRouter(prefix="/api/admin", tags=["运营后台"])


# ===== 登录（强制限流防爆破） =====
@router.post("/login")
@limiter.limit(LIMIT_ADMIN_LOGIN)
async def admin_login(request: Request, req: AdminLoginRequest, db: Session = Depends(get_db)):
    """管理员登录（账号密码错误统一返回 401，防止用户名枚举）"""
    result = admin_service.admin_login(db, req.username, req.password)
    resp = AdminLoginResponse(
        token=result["token"],
        admin_id=result["admin_id"],
        role=result["role"],
    ).model_dump()
    return success(data=resp, message="登录成功")


@router.post("/logout")
async def admin_logout(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):
    """管理员登出：数据库会话版本立即失效全部旧 token。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="管理员未登录")
    token = authorization[len("Bearer "):]
    payload = decode_access_token(token)
    if not payload or payload.get("type") != "admin":
        raise HTTPException(status_code=401, detail="无效的管理员 token")
    try:
        admin_id = int(payload.get("sub"))
        token_version = int(payload.get("ver", 0))
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=401, detail="无效的管理员 token") from error
    admin = db.query(Admin).filter(Admin.id == admin_id).with_for_update().first()
    if not admin or token_version != int(admin.token_version or 1):
        raise HTTPException(status_code=401, detail="管理员登录状态已失效")
    admin.token_version = int(admin.token_version or 1) + 1
    db.commit()
    if payload.get("jti"):
        redis_client.blacklist_token(payload["jti"], expire_seconds=86400)
    return success(message="登出成功")


@router.post("/create")
async def create_admin(
    req: AdminCreateRequest,
    admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """创建管理员（仅 super_admin 可调用）"""
    new_admin = admin_service.create_admin(db, req, creator=admin)
    data = {
        "id": new_admin.id,
        "username": new_admin.username,
        "real_name": new_admin.real_name,
        "role": new_admin.role,
        "is_active": new_admin.is_active,
    }
    return success(data=data, message="创建成功")


# ===== Dashboard =====
@router.get("/dashboard")
async def dashboard(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """首页数据统计"""
    stats = admin_service.get_dashboard_stats(db)
    resp = DashboardResponse(**stats).model_dump()
    return success(data=resp)


# ===== 用户管理 =====
@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = Query(None, max_length=64),
    status: Optional[str] = Query(None),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """用户列表（分页、搜索、状态筛选）"""
    result = admin_service.list_users(db, page=page, size=size, keyword=keyword, status=status)
    return success(data=result)


@router.put("/users/{user_id}/active")
async def toggle_user_active(
    user_id: int,
    req: ToggleActiveRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """启用/禁用用户"""
    result = admin_service.toggle_user_active(db, user_id, req.is_active)
    return success(data=result, message="状态已更新")


# ===== 师傅管理 =====
@router.get("/workers")
async def list_workers(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    certified: Optional[int] = Query(None),
    is_online: Optional[bool] = Query(None),
    keyword: Optional[str] = Query(None, max_length=64),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """师傅列表"""
    result = admin_service.list_workers(
        db, page=page, size=size, certified=certified, is_online=is_online, keyword=keyword
    )
    return success(data=result)


@router.put("/workers/{worker_id}/certify")
async def update_worker_certified(
    worker_id: int,
    req: WorkerCertifyRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """更新师傅认证状态 0/1/2/3"""
    result = admin_service.update_worker_certified(db, worker_id, req.certified)
    return success(data=result, message="认证状态已更新")


# ===== 订单管理 =====
@router.get("/orders")
async def list_orders(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None, max_length=64),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """订单列表"""
    result = admin_service.list_orders(db, page=page, size=size, status=status, keyword=keyword)
    return success(data=result)


@router.put("/orders/{order_id}/status")
async def update_order_status(
    order_id: int,
    req: UpdateOrderStatusRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员修改订单状态"""
    result = admin_service.update_order_status_admin(
        db, order_id, req.status, req.remark, operator_id=admin.id
    )
    return success(data=result, message="订单状态已更新")


# ===== 提现管理 =====
@router.get("/withdraws/pending")
async def list_pending_withdraws(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """待审核提现列表"""
    result = admin_service.list_withdraws_pending(db, page=page, size=size)
    return success(data=result)


@router.put("/withdraws/{tx_id}/approve")
async def approve_withdraw(
    tx_id: int,
    admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """审批通过提现（触发转账）"""
    result = await admin_service.approve_withdraw(db, tx_id, admin.id)
    return success(data=result, message="提现审批完成")


# ===== 优惠券模板 =====
@router.get("/coupons/templates")
async def list_coupon_templates(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """优惠券模板列表（无模型时返回空）"""
    result = admin_service.list_coupon_templates(db, page=page, size=size)
    return success(data=result)


# ===== 反馈管理 =====
@router.get("/feedbacks")
async def list_feedbacks(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """反馈列表（无模型时返回空）"""
    result = admin_service.list_feedbacks(db, page=page, size=size)
    return success(data=result)
