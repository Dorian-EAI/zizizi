"""运营后台路由

安全说明：
- 所有 admin 路由均通过 get_current_admin 依赖进行 JWT 鉴权
- 账号、认证、订单状态与资金相关写操作要求 super_admin 角色
- 不再接受 X-Admin-Id Header 这种弱鉴权方式
- 登录接口强制限流防爆破
"""

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from typing import List, Optional

from app.database import get_db
from app.dependencies import (
    get_current_admin,
    get_current_admin_for_password_change,
    require_admin_operator,
    require_super_admin,
)
from app.models.admin import Admin
from app.models.order import Order, OrderCancellationRequest
from app.models.service import ServiceType
from app.schemas.admin import (
    AdminCreateRequest,
    AdminChangePasswordRequest,
    AdminLoginRequest,
    AdminLoginResponse,
    AdminResetPasswordRequest,
    DashboardResponse,
    ToggleActiveRequest,
    UpdateOrderStatusRequest,
    WorkerCertifyRequest,
)
from app.schemas.order import CancelRequestReview
from app.services import admin_service, cancellation_service, upload_service
from app.utils.response import success
from app.utils.rate_limit import limiter, LIMIT_ADMIN_LOGIN, LIMIT_UPLOAD_BATCH, LIMIT_UPLOAD_SINGLE
from app.utils.redis_client import redis_client
from app.utils.security import decode_access_token

router = APIRouter(prefix="/api/admin", tags=["运营后台"])

# 管理员只允许为运营内容选择公开图片分类，认证材料等私有目录不允许从后台写入。
_ADMIN_UPLOAD_CATEGORIES = {"service", "banner", "content", "images"}
_ADMIN_UPLOAD_MAX_MB = 10


def _admin_upload_category(category: str) -> str:
    value = upload_service.normalize_category(category)
    if value not in _ADMIN_UPLOAD_CATEGORIES:
        raise HTTPException(status_code=400, detail="不支持的后台上传分类")
    return value


async def _read_admin_upload(file: UploadFile) -> bytes:
    """分块读取并限制大小，避免后台误传超大文件占满内存。"""
    max_bytes = _ADMIN_UPLOAD_MAX_MB * 1024 * 1024
    data = bytearray()
    while True:
        chunk = await file.read(min(1024 * 1024, max_bytes + 1 - len(data)))
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > max_bytes:
            raise HTTPException(status_code=413, detail=f"文件大小超过上限 {_ADMIN_UPLOAD_MAX_MB}MB")
    return bytes(data)


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
        must_change_password=result["must_change_password"],
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


@router.put("/password")
async def change_password(
    req: AdminChangePasswordRequest,
    admin: Admin = Depends(get_current_admin_for_password_change),
    db: Session = Depends(get_db),
):
    """验证旧密码后改密，并立即让全部旧管理员 token 失效。"""
    admin_service.change_admin_password(db, admin, req.current_password, req.new_password)
    return success(message="密码已修改，请重新登录")


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


@router.get("/accounts")
async def list_admin_accounts(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return success(data=admin_service.list_admin_accounts(db, page, size))


@router.get("/audit-logs")
async def list_admin_audit_logs(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    action: Optional[str] = Query(None, max_length=64),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """后台持久化审计日志；auditor 可读但不可执行任何写操作。"""
    return success(data=admin_service.list_admin_audits(db, page, size, action))


@router.put("/accounts/{admin_id}/active")
async def set_admin_active(
    admin_id: int,
    req: ToggleActiveRequest,
    admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    target = admin_service.set_admin_active(db, admin_id, req.is_active, admin)
    return success(data={"id": target.id, "is_active": target.is_active}, message="状态已更新")


@router.put("/accounts/{admin_id}/password")
async def reset_admin_password(
    admin_id: int,
    req: AdminResetPasswordRequest,
    admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    target = admin_service.reset_admin_password(db, admin_id, req.new_password, admin)
    return success(
        data={"id": target.id, "must_change_password": True},
        message="密码已重置，该管理员下次登录必须改密",
    )


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


# ===== 服务内容管理 =====
@router.get("/services")
async def list_all_services(
    page: int = Query(1, ge=1),
    size: int = Query(200, ge=1, le=500),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """后台服务列表：包含已禁用服务，避免禁用后无法再次编辑启用。"""
    q = db.query(ServiceType).order_by(ServiceType.sort_order.asc(), ServiceType.id.asc())
    total = q.count()
    rows = q.offset((page - 1) * size).limit(size).all()
    items = [
        {
            "id": svc.id,
            "key": svc.key,
            "name": svc.name,
            "icon": svc.icon,
            "banner": svc.banner,
            "category": svc.category,
            "price_min": float(svc.price_min or 0),
            "price_max": float(svc.price_max or 0),
            "price_unit": svc.price_unit,
            "sort_order": int(svc.sort_order or 0),
            "is_active": bool(svc.is_active),
        }
        for svc in rows
    ]
    return success(data={"list": items, "total": total, "page": page, "size": size})


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
    result = admin_service.list_users(
        db,
        page=page,
        size=size,
        keyword=keyword,
        status=status,
        reveal_sensitive=admin.role == "super_admin",
    )
    return success(data=result)


@router.put("/users/{user_id}/active")
async def toggle_user_active(
    user_id: int,
    req: ToggleActiveRequest,
    admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """启用/禁用用户"""
    result = admin_service.toggle_user_active(db, user_id, req.is_active, admin.id)
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
        db,
        page=page,
        size=size,
        certified=certified,
        is_online=is_online,
        keyword=keyword,
        reveal_sensitive=admin.role == "super_admin",
    )
    return success(data=result)


@router.put("/workers/{worker_id}/certify")
async def update_worker_certified(
    worker_id: int,
    req: WorkerCertifyRequest,
    admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """更新师傅认证状态 0/1/2/3"""
    result = admin_service.update_worker_certified(db, worker_id, req.certified, admin.id)
    return success(data=result, message="认证状态已更新")


@router.get("/workers/{worker_id}/certification")
def get_worker_certification(
    worker_id: int,
    admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """读取认证申请；证件只返回十分钟有效的私有对象签名 URL。"""
    result = admin_service.get_worker_certification(db, worker_id)
    return success(data=result)


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
    admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """管理员修改订单状态"""
    result = admin_service.update_order_status_admin(
        db,
        order_id,
        req.status,
        operator_id=admin.id,
        remark=req.remark,
    )
    return success(data=result, message="订单状态已更新")


# ===== 取消申请 =====
@router.get("/cancel-requests")
async def list_cancel_requests(
    status: Optional[str] = Query(None, max_length=16),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """后台取消申请列表。"""
    q = db.query(OrderCancellationRequest, Order).join(
        Order, Order.id == OrderCancellationRequest.order_id
    )
    if status:
        q = q.filter(OrderCancellationRequest.status == status)
    total = q.count()
    rows = (
        q.order_by(OrderCancellationRequest.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    items = []
    for request, order in rows:
        item = cancellation_service.serialize_request(request) or {}
        item.update(
            {
                "order_no": order.order_no,
                "service_name": order.service_name,
                "order_status": order.status,
                "order_final_price": float(order.final_price or 0),
            }
        )
        items.append(item)
    return success(data={"list": items, "total": total, "page": page, "size": size})


@router.put("/cancel-requests/{request_id}/approve")
async def approve_cancel_request(
    request_id: int,
    req: CancelRequestReview,
    admin: Admin = Depends(require_admin_operator),
    db: Session = Depends(get_db),
):
    """通过取消申请并取消订单。"""
    request = cancellation_service.approve_request(db, admin.id, request_id, req.remark)
    admin_service.add_admin_audit(
        db,
        admin.id,
        "cancel_request.approve",
        "order_cancellation_request",
        request.id,
        {"order_id": request.order_id, "remark": req.remark},
        commit=True,
    )
    return success(
        data=cancellation_service.serialize_request(request),
        message="取消申请已通过",
    )


@router.put("/cancel-requests/{request_id}/reject")
async def reject_cancel_request(
    request_id: int,
    req: CancelRequestReview,
    admin: Admin = Depends(require_admin_operator),
    db: Session = Depends(get_db),
):
    """拒绝取消申请，必须填写原因。"""
    remark = (req.remark or "").strip()
    if not remark:
        raise HTTPException(status_code=400, detail="请填写拒绝原因")
    request = cancellation_service.reject_request(db, admin.id, request_id, remark)
    admin_service.add_admin_audit(
        db,
        admin.id,
        "cancel_request.reject",
        "order_cancellation_request",
        request.id,
        {"order_id": request.order_id, "remark": remark},
        commit=True,
    )
    return success(
        data=cancellation_service.serialize_request(request),
        message="取消申请已拒绝",
    )


# ===== 提现管理 =====
@router.get("/withdraws/pending")
async def list_pending_withdraws(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    admin: Admin = Depends(require_super_admin),
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


@router.put("/withdraws/{tx_id}/reject")
async def reject_withdraw(
    tx_id: int,
    reason: str = Query("", max_length=200, description="驳回原因"),
    admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """驳回提现并退回可提现余额"""
    result = await admin_service.reject_withdraw(db, tx_id, admin.id, reason)
    return success(data=result, message="提现已驳回")


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


# ===== 运营图片上传 =====
@router.post("/upload/image")
@limiter.limit(LIMIT_UPLOAD_SINGLE)
async def admin_upload_image(
    request: Request,
    category: str = Query("service", max_length=32, description="service / banner / content / images"),
    file: UploadFile = File(...),
    admin: Admin = Depends(require_admin_operator),
    db: Session = Depends(get_db),
):
    """管理员上传运营图片（服务图标、Banner、案例图等），写入审计日志。"""
    category = _admin_upload_category(category)
    file_bytes = await _read_admin_upload(file)
    result = await run_in_threadpool(
        upload_service.upload_image,
        category,
        file_bytes,
        file.filename or "",
        owner_id=admin.id,
    )
    admin_service.add_admin_audit(
        db,
        admin.id,
        "upload.image",
        "storage_object",
        category,
        {"url": result["url"], "category": category, "size": result["size"]},
        commit=True,
    )
    return success(data=result, message="上传成功")


@router.post("/upload/images")
@limiter.limit(LIMIT_UPLOAD_BATCH)
async def admin_upload_images(
    request: Request,
    category: str = Query("service", max_length=32, description="service / banner / content / images"),
    files: List[UploadFile] = File(..., description="最多 9 张"),
    admin: Admin = Depends(require_admin_operator),
    db: Session = Depends(get_db),
):
    """管理员批量上传运营图片（最多 9 张）。"""
    if len(files) > 9:
        raise HTTPException(status_code=400, detail="最多支持同时上传 9 张图片")
    category = _admin_upload_category(category)
    results = []
    for item in files:
        file_bytes = await _read_admin_upload(item)
        result = await run_in_threadpool(
            upload_service.upload_image,
            category,
            file_bytes,
            item.filename or "",
            owner_id=admin.id,
        )
        results.append(result)
    admin_service.add_admin_audit(
        db,
        admin.id,
        "upload.images",
        "storage_object",
        category,
        {
            "urls": [item["url"] for item in results],
            "count": len(results),
            "size": sum(item["size"] for item in results),
        },
        commit=True,
    )
    return success(data=results, message="上传成功")
