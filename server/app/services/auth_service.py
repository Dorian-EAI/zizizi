"""认证与用户业务逻辑"""

import json
from datetime import datetime
from typing import List

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.coupon import Coupon
from app.models.favorite import FavoriteWorker
from app.models.message import Message
from app.models.order import Order
from app.models.review import Review
from app.models.user import User, Worker, Address
from app.schemas.user import (
    UpdateProfileRequest,
    WorkerCertificationRequest,
    AddressCreate,
    AddressUpdate,
)
from app.services.wechat_service import code2session
from app.utils.aes import encrypt_field, mask_id_card
from app.utils.logger import get_logger
from app.utils.security import create_access_token


logger = get_logger(__name__)


# ===== 登录 =====
async def wx_login(db: Session, code: str, nickname: str = None, avatar: str = None) -> dict:
    """微信用户登录：code 换 openid，不存在则创建"""
    wx_data = await code2session(code)
    openid = wx_data.get("openid")
    unionid = wx_data.get("unionid")
    if not openid:
        raise HTTPException(status_code=400, detail="微信登录失败：未获取到 openid")

    user = db.query(User).filter(User.openid == openid).first()
    is_new = False
    if not user:
        user = User(
            openid=openid,
            unionid=unionid,
            nickname=nickname,
            avatar=avatar,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        is_new = True
    else:
        if unionid and not user.unionid:
            user.unionid = unionid
            db.commit()

    token = create_access_token({
        "sub": user.id,
        "type": "user",
        "role": user.role,
        "ver": int(user.token_version or 1),
    })
    return {"token": token, "user_id": user.id, "role": user.role, "is_new": is_new}


async def worker_login(db: Session, code: str, nickname: str = None, avatar: str = None) -> dict:
    """师傅微信登录：code 换 openid，不存在则创建"""
    wx_data = await code2session(code)
    openid = wx_data.get("openid")
    unionid = wx_data.get("unionid")
    if not openid:
        raise HTTPException(status_code=400, detail="微信登录失败：未获取到 openid")

    worker = db.query(Worker).filter(Worker.openid == openid).first()
    is_new = False
    if not worker:
        worker = Worker(
            openid=openid,
            unionid=unionid,
            nickname=nickname,
            avatar=avatar,
        )
        db.add(worker)
        db.commit()
        db.refresh(worker)
        is_new = True
    else:
        if unionid and not worker.unionid:
            worker.unionid = unionid
            db.commit()

    token = create_access_token({
        "sub": worker.id,
        "type": "worker",
        "ver": int(worker.token_version or 1),
    })
    return {"token": token, "worker_id": worker.id, "is_new": is_new}


# ===== 用户信息 =====
def get_user_info(db: Session, user: User) -> dict:
    """获取当前用户信息"""
    now = datetime.utcnow()
    summary = {
        "orders": db.query(Order.id).filter(Order.user_id == user.id).count(),
        "reviews": db.query(Review.id).filter(Review.user_id == user.id).count(),
        "favorites": db.query(FavoriteWorker.id).filter(FavoriteWorker.user_id == user.id).count(),
        "available_coupons": db.query(Coupon.id).filter(
            Coupon.user_id == user.id,
            Coupon.status == "available",
            or_(Coupon.expire_at.is_(None), Coupon.expire_at > now),
        ).count(),
        "unread_messages": db.query(Message.id).filter(
            Message.owner_type == "user",
            Message.owner_id == user.id,
            Message.is_read.is_(False),
        ).count(),
    }
    return {
        "id": user.id,
        "nickname": user.nickname,
        "avatar": user.avatar,
        "phone": user.phone,
        "role": user.role,
        "member_level": user.member_level,
        "growth_value": user.growth_value,
        "balance": user.balance,
        "summary": summary,
    }


def update_user_profile(db: Session, user: User, data: UpdateProfileRequest) -> User:
    """更新用户个人资料（仅更新非空字段）"""
    if data.nickname is not None:
        user.nickname = data.nickname
    if data.avatar is not None:
        user.avatar = data.avatar
    if data.phone is not None:
        raise HTTPException(status_code=400, detail="修改手机号必须使用短信验证绑定接口")
    db.commit()
    db.refresh(user)
    return user


def submit_worker_certification(
    db: Session,
    worker: Worker,
    data: WorkerCertificationRequest,
) -> dict:
    """保存师傅认证申请并进入待审核状态。

    身份证明文只在本函数的局部变量中短暂存在；数据库仅保存 AES 密文，
    certification_data 与返回值均只包含脱敏号段。
    """
    from app.services import sms_service

    verification_code = data.phone_verification_code.get_secret_value()
    if not sms_service.verify_code(data.phone, verification_code):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    existing_phone = (
        db.query(Worker.id)
        .filter(Worker.phone == data.phone, Worker.id != worker.id)
        .first()
    )
    if existing_phone:
        raise HTTPException(status_code=409, detail="该手机号已绑定其他师傅账号")

    plain_id_card = data.id_card.get_secret_value()
    encrypted_id_card = encrypt_field(plain_id_card)
    submitted_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    price_min = format(data.price_min, "f")
    price_max = format(data.price_max, "f")

    snapshot = {
        "real_name": data.real_name,
        "phone": data.phone,
        "id_card_masked": mask_id_card(plain_id_card),
        "id_front": data.id_front,
        "id_back": data.id_back,
        "certificate_images": list(data.certificate_images),
        "health_certificate": data.health_certificate,
        "service_city": data.service_city,
        "service_districts": list(data.service_districts),
        "service_types": list(data.service_types),
        "price_min": price_min,
        "price_max": price_max,
        "submitted_at": submitted_at,
    }

    worker.real_name = data.real_name
    worker.phone = data.phone
    worker.id_card = encrypted_id_card
    worker.certificates = json.dumps(data.certificate_images, ensure_ascii=False)
    worker.skills = json.dumps(data.service_types, ensure_ascii=False)
    worker.service_types = json.dumps(data.service_types, ensure_ascii=False)
    worker.service_area = data.service_city + " · " + "、".join(data.service_districts)
    worker.certification_data = snapshot
    worker.certified = 1

    try:
        db.commit()
        db.refresh(worker)
    except Exception:
        db.rollback()
        raise

    logger.info("师傅认证申请已提交 worker_id=%s status=pending", worker.id)
    return {
        "certified": 1,
        "certification_status": "pending",
        "submitted_at": submitted_at,
        "application": snapshot,
    }


def bind_phone(db: Session, user: User, phone: str, verification_code: str) -> User:
    """校验一次性短信验证码后绑定或换绑手机号。"""
    from app.services import sms_service
    if not sms_service.verify_code(phone, verification_code):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")
    existing = db.query(User).filter(User.phone == phone, User.id != user.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="该手机号已绑定其他账号")
    user.phone = phone
    db.commit()
    db.refresh(user)
    return user


def switch_role(db: Session, user: User, role: str) -> User:
    """切换用户角色"""
    if role not in ("user", "worker"):
        raise HTTPException(status_code=400, detail="角色必须为 user 或 worker")
    user.role = role
    db.commit()
    db.refresh(user)
    return user


# ===== 地址管理 =====
def create_address(db: Session, user: User, data: AddressCreate) -> Address:
    """新增地址"""
    if data.is_default:
        _clear_default_addresses(db, user.id)
    address = Address(
        user_id=user.id,
        name=data.name,
        phone=data.phone,
        province=data.province,
        city=data.city,
        district=data.district,
        detail=data.detail,
        label=data.label or "家",
        is_default=data.is_default,
        location_lat=data.location_lat,
        location_lng=data.location_lng,
    )
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


def get_addresses(db: Session, user: User) -> List[Address]:
    """获取用户地址列表（默认地址排在最前）"""
    return (
        db.query(Address)
        .filter(Address.user_id == user.id)
        .order_by(Address.is_default.desc(), Address.updated_at.desc())
        .all()
    )


def update_address(db: Session, user: User, address_id: int, data: AddressUpdate) -> Address:
    """编辑地址"""
    address = _get_user_address(db, user.id, address_id)
    if data.name is not None:
        address.name = data.name
    if data.phone is not None:
        address.phone = data.phone
    if data.province is not None:
        address.province = data.province
    if data.city is not None:
        address.city = data.city
    if data.district is not None:
        address.district = data.district
    if data.detail is not None:
        address.detail = data.detail
    if data.label is not None:
        address.label = data.label
    if data.location_lat is not None:
        address.location_lat = data.location_lat
    if data.location_lng is not None:
        address.location_lng = data.location_lng
    if data.is_default is not None:
        if data.is_default:
            _clear_default_addresses(db, user.id, exclude_id=address_id)
        address.is_default = data.is_default
    db.commit()
    db.refresh(address)
    return address


def delete_address(db: Session, user: User, address_id: int) -> None:
    """删除地址"""
    address = _get_user_address(db, user.id, address_id)
    db.delete(address)
    db.commit()


def set_default_address(db: Session, user: User, address_id: int) -> Address:
    """设为默认地址"""
    address = _get_user_address(db, user.id, address_id)
    _clear_default_addresses(db, user.id, exclude_id=address_id)
    address.is_default = True
    db.commit()
    db.refresh(address)
    return address


# ===== 内部工具 =====
def _get_user_address(db: Session, user_id: int, address_id: int) -> Address:
    """获取属于指定用户的地址，不存在则抛异常"""
    address = (
        db.query(Address)
        .filter(Address.id == address_id, Address.user_id == user_id)
        .first()
    )
    if not address:
        raise HTTPException(status_code=404, detail="地址不存在")
    return address


def _clear_default_addresses(db: Session, user_id: int, exclude_id: int = None) -> None:
    """取消该用户其他地址的默认标记"""
    q = db.query(Address).filter(
        Address.user_id == user_id,
        Address.is_default == True,
    )
    if exclude_id:
        q = q.filter(Address.id != exclude_id)
    q.update({"is_default": False})
