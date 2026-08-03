"""运营后台业务逻辑"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import extract, func, or_
from sqlalchemy.orm import Session

from app.models.admin import Admin
from app.models.order import Order
from app.models.user import User, Worker
from app.models.wallet import Transaction
from app.services import wechat_pay_service
from app.utils.security import create_access_token, hash_password, verify_password

try:
    from app.models.coupon import CouponTemplate
    _COUPON_MODEL_AVAILABLE = True
except ImportError:
    CouponTemplate = None
    _COUPON_MODEL_AVAILABLE = False


# ===== 辅助函数 =====

def _paginate_query(query, page: int, size: int) -> dict:
    """通用分页封装：{list, total, page, size, has_more}"""
    total = query.count()
    offset = (page - 1) * size
    items = query.order_by(None).order_by(
        # 默认按 id / created_at 倒序，由外层覆盖
    ).offset(offset).limit(size).all()
    return {
        "list": items,
        "total": total,
        "page": page,
        "size": size,
        "has_more": (offset + size) < total,
    }


def _admin_to_dict(admin: Admin) -> dict:
    return {
        "id": admin.id,
        "username": admin.username,
        "real_name": admin.real_name,
        "role": admin.role,
        "is_active": admin.is_active,
        "last_login_at": admin.last_login_at.strftime("%Y-%m-%d %H:%M:%S") if admin.last_login_at else None,
    }


def _user_to_dict(u: User) -> dict:
    return {
        "id": u.id,
        "openid": u.openid,
        "nickname": u.nickname,
        "avatar": u.avatar,
        "phone": u.phone,
        "role": u.role,
        "member_level": u.member_level,
        "growth_value": u.growth_value,
        "balance": float(u.balance or 0),
        "is_active": u.is_active,
        "created_at": u.created_at.strftime("%Y-%m-%d %H:%M:%S") if u.created_at else None,
    }


def _worker_to_dict(w: Worker) -> dict:
    # 身份证号脱敏：DB 中存的是密文，展示时解密+掩码
    from app.utils.aes import decrypt_field, mask_id_card
    id_card_plain = None
    try:
        id_card_plain = decrypt_field(w.id_card)
    except Exception:
        # 解密失败（如旧明文数据、密钥变更等），原值不展示给前端
        id_card_plain = None

    return {
        "id": w.id,
        "openid": w.openid,
        "nickname": w.nickname,
        "avatar": w.avatar,
        "phone": w.phone,
        "real_name": w.real_name,
        # 永远不返回明文身份证号，仅返回掩码
        "id_card_masked": mask_id_card(id_card_plain) if id_card_plain else None,
        "certified": w.certified,
        "skills": w.skills,
        "certificates": w.certificates,
        "rating": float(w.rating or 0),
        "service_count": w.service_count,
        "level": w.level,
        "balance": float(w.balance or 0),
        "is_online": w.is_online,
        "service_area": w.service_area,
        "service_types": w.service_types,
        "is_active": w.is_active,
        "created_at": w.created_at.strftime("%Y-%m-%d %H:%M:%S") if w.created_at else None,
    }


def _order_to_dict(o: Order) -> dict:
    return {
        "id": o.id,
        "order_no": o.order_no,
        "user_id": o.user_id,
        "worker_id": o.worker_id,
        "service_type": o.service_type,
        "service_name": o.service_name,
        "description": o.description,
        "images": o.images,
        "address": o.address,
        "appoint_time": o.appoint_time.strftime("%Y-%m-%d %H:%M:%S") if o.appoint_time else None,
        "budget": float(o.budget or 0),
        "final_price": float(o.final_price or 0) if o.final_price is not None else None,
        "urgent": o.urgent,
        "urgent_amount": float(o.urgent_amount or 0),
        "status": o.status,
        "rating": o.rating,
        "review_content": o.review_content,
        "created_at": o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else None,
        "accepted_at": o.accepted_at.strftime("%Y-%m-%d %H:%M:%S") if o.accepted_at else None,
        "completed_at": o.completed_at.strftime("%Y-%m-%d %H:%M:%S") if o.completed_at else None,
        "paid_at": o.paid_at.strftime("%Y-%m-%d %H:%M:%S") if o.paid_at else None,
    }


def _tx_to_dict(tx: Transaction) -> dict:
    return {
        "id": tx.id,
        "owner_type": tx.owner_type,
        "owner_id": tx.owner_id,
        "type": tx.type,
        "amount": float(tx.amount),
        "balance_after": float(tx.balance_after) if tx.balance_after is not None else None,
        "method": tx.method,
        "order_id": tx.order_id,
        "description": tx.description,
        "status": tx.status,
        "bank_info": tx.bank_info,
        "created_at": tx.created_at.strftime("%Y-%m-%d %H:%M:%S") if tx.created_at else None,
    }


# ===== 管理员登录/创建 =====

def admin_login(db: Session, username: str, password: str) -> dict:
    """管理员登录

    安全说明：
    - 不再支持 "admin/admin123" 自动创建后门账号
    - 默认管理员账号由 init_db.seed_admin 在首次启动时写入（仅在 DB 为空时）
    - 用户名不存在与密码错误统一返回 401，防止用户名枚举

    Returns:
        {token, admin_id, role}
    """
    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")

    admin = db.query(Admin).filter(Admin.username == username).first()

    # 统一错误信息，避免用户名枚举
    cred_error = HTTPException(status_code=401, detail="用户名或密码错误")

    if not admin:
        raise cred_error

    if not admin.is_active:
        raise HTTPException(status_code=403, detail="账号已禁用")

    if not verify_password(password, admin.password_hash):
        raise cred_error

    admin.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(admin)

    from app.config import settings

    token = create_access_token(
        {
            "sub": admin.id,
            "type": "admin",
            "role": admin.role,
            "ver": int(admin.token_version or 1),
        },
        expires_delta=timedelta(minutes=settings.ADMIN_JWT_EXPIRE_MINUTES),
    )
    return {
        "token": token,
        "admin_id": admin.id,
        "role": admin.role,
    }


def create_admin(db: Session, data, creator: Admin = None) -> Admin:
    """创建管理员（仅 super_admin 可调用，调用方在 api 层已校验）

    Args:
        creator: 创建者 Admin 对象，用于审计日志
    """
    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")

    # 密码强度校验（防止 super_admin 创建弱密码账号）
    if len(data.password) < 12:
        raise HTTPException(status_code=400, detail="管理员密码长度至少 12 位")

    exist = db.query(Admin).filter(Admin.username == data.username).first()
    if exist:
        raise HTTPException(status_code=400, detail="用户名已存在")

    # role 必须在合法集合内，且 operator 不能创建 super_admin
    valid_roles = {"super_admin", "operator", "auditor"}
    role = data.role or "operator"
    if role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"角色不合法，允许: {','.join(valid_roles)}")

    admin = Admin(
        username=data.username,
        password_hash=hash_password(data.password),
        real_name=data.real_name,
        role=role,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    # 审计日志（非阻塞）
    try:
        from app.utils.logger import get_logger
        log = get_logger("app.audit")
        log.info(
            "admin_created",
            extra={
                "creator_id": creator.id if creator else None,
                "creator_name": creator.username if creator else "system",
                "new_admin_id": admin.id,
                "new_admin_name": admin.username,
                "new_admin_role": admin.role,
            },
        )
    except Exception:
        pass

    return admin


# ===== Dashboard 统计 =====

def get_dashboard_stats(db: Session) -> dict:
    """获取今日运营数据统计"""
    now = datetime.utcnow()
    start_of_day = datetime(now.year, now.month, now.day)

    today_orders = (
        db.query(func.count(Order.id))
        .filter(Order.created_at >= start_of_day)
        .scalar()
    ) or 0

    today_amount = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.created_at >= start_of_day,
            Transaction.type.in_(["income", "recharge"]),
            Transaction.status == "success",
        )
        .scalar()
    ) or 0.0

    new_users = (
        db.query(func.count(User.id))
        .filter(User.created_at >= start_of_day)
        .scalar()
    ) or 0

    new_workers = (
        db.query(func.count(Worker.id))
        .filter(Worker.created_at >= start_of_day)
        .scalar()
    ) or 0

    pending_withdraw_count = (
        db.query(func.count(Transaction.id))
        .filter(
            Transaction.type == "withdraw",
            Transaction.status == "pending",
        )
        .scalar()
    ) or 0

    return {
        "today_orders": int(today_orders),
        "today_amount": float(today_amount),
        "new_users": int(new_users),
        "new_workers": int(new_workers),
        "pending_withdraw_count": int(pending_withdraw_count),
    }


# ===== 用户管理 =====

def list_users(
    db: Session,
    page: int = 1,
    size: int = 20,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    query = db.query(User)

    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(
            User.nickname.like(like),
            User.phone.like(like),
            User.openid.like(like),
        ))

    if status is not None:
        is_active = True if str(status).lower() in ("1", "true", "active") else False
        query = query.filter(User.is_active == is_active)

    query = query.order_by(User.created_at.desc())
    result = _paginate_query(query, page, size)
    result["list"] = [_user_to_dict(u) for u in result["list"]]
    return result


def toggle_user_active(db: Session, user_id: int, is_active: bool) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return _user_to_dict(user)


# ===== 师傅管理 =====

def list_workers(
    db: Session,
    page: int = 1,
    size: int = 20,
    certified: Optional[int] = None,
    is_online: Optional[bool] = None,
    keyword: Optional[str] = None,
) -> dict:
    query = db.query(Worker)

    if certified is not None:
        query = query.filter(Worker.certified == int(certified))

    if is_online is not None:
        query = query.filter(Worker.is_online == bool(is_online))

    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(
            Worker.nickname.like(like),
            Worker.phone.like(like),
            Worker.real_name.like(like),
        ))

    query = query.order_by(Worker.created_at.desc())
    result = _paginate_query(query, page, size)
    result["list"] = [_worker_to_dict(w) for w in result["list"]]
    return result


def update_worker_certified(db: Session, worker_id: int, certified_status: int) -> dict:
    if certified_status not in (0, 1, 2, 3):
        raise HTTPException(status_code=400, detail="认证状态不合法")
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="师傅不存在")
    worker.certified = certified_status
    db.commit()
    db.refresh(worker)
    return _worker_to_dict(worker)


# ===== 订单管理 =====

def list_orders(
    db: Session,
    page: int = 1,
    size: int = 20,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
) -> dict:
    query = db.query(Order)

    if status:
        query = query.filter(Order.status == status)

    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(
            Order.order_no.like(like),
            Order.service_name.like(like),
        ))

    query = query.order_by(Order.created_at.desc())
    result = _paginate_query(query, page, size)
    result["list"] = [_order_to_dict(o) for o in result["list"]]
    return result


def update_order_status_admin(
    db: Session,
    order_id: int,
    new_status: str,
    remark: Optional[str] = None,
    operator_id: Optional[int] = None,
) -> dict:
    order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if new_status != "cancelled":
        raise HTTPException(status_code=400, detail="后台不能绕过业务流程修改资金或服务状态")
    if order.status not in {"pending", "accepted"}:
        raise HTTPException(status_code=409, detail="仅待接单或未开工订单可由后台取消")
    if not remark or len(remark.strip()) < 2:
        raise HTTPException(status_code=400, detail="后台取消订单必须填写原因")

    from app.services.order_service import _cas_update_status

    _cas_update_status(
        db,
        order,
        "cancelled",
        allowed_from=["pending", "accepted"],
        cancelled_at=datetime.utcnow(),
    )
    db.commit()
    db.refresh(order)

    # 审计日志（非阻塞）
    try:
        from app.utils.logger import get_logger
        log = get_logger("app.audit")
        log.info(
            "admin_update_order_status",
            extra={
                "operator_id": operator_id,
                "order_id": order_id,
                "new_status": "cancelled",
                "remark": remark,
            },
        )
    except Exception:
        pass

    return _order_to_dict(order)


# ===== 提现管理 =====

def list_withdraws_pending(
    db: Session,
    page: int = 1,
    size: int = 20,
) -> dict:
    query = db.query(Transaction).filter(
        Transaction.type == "withdraw",
        Transaction.status == "pending",
    ).order_by(Transaction.created_at.asc())

    result = _paginate_query(query, page, size)
    result["list"] = [_tx_to_dict(tx) for tx in result["list"]]

    for idx, tx in enumerate(result["list"]):
        raw_tx = result["list"]
        if raw_tx:
            owner_type = tx.get("owner_type")
            owner_id = tx.get("owner_id")
            owner_info = None
            if owner_type == "user" and owner_id:
                u = db.query(User).filter(User.id == owner_id).first()
                if u:
                    owner_info = {"nickname": u.nickname, "phone": u.phone}
            elif owner_type == "worker" and owner_id:
                w = db.query(Worker).filter(Worker.id == owner_id).first()
                if w:
                    owner_info = {"nickname": w.nickname, "phone": w.phone, "real_name": w.real_name}
            result["list"][idx]["owner"] = owner_info

    return result


async def approve_withdraw(db: Session, tx_id: int, admin_id: int) -> dict:
    """审批通过提现：触发商户转账 + 改 Transaction 状态"""
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="提现记录不存在")
    if tx.type != "withdraw":
        raise HTTPException(status_code=400, detail="非提现交易")
    if tx.status != "pending":
        raise HTTPException(status_code=400, detail="该提现阶段不可审批")

    worker = None
    if tx.owner_type == "worker":
        worker = db.query(Worker).filter(Worker.id == tx.owner_id).first()

    transfer_result = wechat_pay_service.create_transfer_to_worker(db, tx, worker)

    # 发送提现到账通知
    if tx.status == "success":
        from app.services import message_service
        await message_service.notify_withdraw_success(db, tx)

    return {
        "tx_id": tx.id,
        "status": tx.status,
        "transfer": transfer_result,
    }


# ===== 优惠券模板 =====

def list_coupon_templates(db: Session, page: int = 1, size: int = 20) -> dict:
    if not _COUPON_MODEL_AVAILABLE or CouponTemplate is None:
        return {"list": [], "total": 0, "page": page, "size": size, "has_more": False}

    query = db.query(CouponTemplate).order_by(CouponTemplate.id.desc()) if hasattr(CouponTemplate, "id") else db.query(CouponTemplate)
    result = _paginate_query(query, page, size)

    serializable_list = []
    for item in result["list"]:
        try:
            d = {c.name: getattr(item, c.name) for c in item.__table__.columns}
            for k, v in d.items():
                if isinstance(v, datetime):
                    d[k] = v.strftime("%Y-%m-%d %H:%M:%S")
            serializable_list.append(d)
        except Exception:
            serializable_list.append({})
    result["list"] = serializable_list
    return result


# ===== 反馈管理 =====

def list_feedbacks(db: Session, page: int = 1, size: int = 20) -> dict:
    """反馈列表（无模型时返回空）"""
    return {"list": [], "total": 0, "page": page, "size": size, "has_more": False}
