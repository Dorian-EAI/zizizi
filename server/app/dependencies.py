"""FastAPI 依赖注入 — 认证、角色校验、Token 黑名单

安全说明：
- 所有鉴权失败必须抛 HTTPException(401/403)，不得抛裸 Exception
  裸 Exception 会被全局兜底捕获返回 500，掩盖未授权语义
- admin JWT 载荷 type 必须为 "admin"，且需查询 DB 复核存在性 + is_active
"""

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, Tuple

from app.database import get_db
from app.utils.security import decode_access_token
from app.utils.redis_client import RedisUnavailableError, redis_client
from app.models.user import User, Worker
from app.models.admin import Admin


# 默认密钥占位符 — 启动时若仍为此值且处于生产环境，config 校验会拒绝启动
_DEFAULT_PLACEHOLDER = "change-this-to-a-random-secret-key"


def _extract_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization[len("Bearer "):]


def _verify_token_not_blacklisted(payload: Optional[dict]) -> dict:
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证 token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    jti = payload.get("jti")
    try:
        blacklisted = bool(jti and redis_client.is_token_blacklisted(jti))
    except RedisUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="认证状态暂时无法校验，请稍后重试",
        ) from exc
    if blacklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token 已被注销，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def _subject_id(payload: dict) -> int:
    try:
        subject_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="认证 token 主体无效") from exc
    if subject_id <= 0:
        raise HTTPException(status_code=401, detail="认证 token 主体无效")
    return subject_id


def _verify_token_version(payload: dict, account) -> None:
    try:
        token_version = int(payload.get("ver", 0))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="认证 token 会话版本无效") from exc
    if token_version != int(getattr(account, "token_version", 1) or 1):
        raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录")


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """从 JWT token 解析当前用户（type=user）"""
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证 token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    payload = _verify_token_not_blacklisted(payload)

    if payload.get("type") not in (None, "user"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token 类型不匹配",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = _subject_id(payload)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")
    _verify_token_version(payload, user)
    return user


def get_current_worker(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Worker:
    """从 JWT token 解析当前师傅（type=worker）"""
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证 token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    payload = _verify_token_not_blacklisted(payload)

    if payload.get("type") != "worker":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token 类型不匹配",
            headers={"WWW-Authenticate": "Bearer"},
        )

    worker_id = _subject_id(payload)
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=401, detail="师傅不存在")
    if not worker.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")
    _verify_token_version(payload, worker)
    return worker


def get_current_account(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Tuple[object, str]:
    """通用认证 — 返回 (account, account_type) 元组

    account_type: 'user' 或 'worker'
    """
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证 token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    payload = _verify_token_not_blacklisted(payload)

    account_id = _subject_id(payload)
    account_type = payload.get("type", "user")

    if account_type == "worker":
        account = db.query(Worker).filter(Worker.id == account_id).first()
    elif account_type == "user":
        account = db.query(User).filter(User.id == account_id).first()
    else:
        raise HTTPException(status_code=401, detail="token 类型不合法")

    if not account:
        raise HTTPException(status_code=401, detail="账号不存在")
    if not getattr(account, "is_active", True):
        raise HTTPException(status_code=403, detail="账号已被禁用")
    _verify_token_version(payload, account)

    return account, account_type


def get_current_admin(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Admin:
    """管理员认证：JWT 校验 + DB 复核 + is_active 校验

    安全说明：
    - 必须从 Authorization Header 解析 JWT，不再接受 X-Admin-Id
    - JWT 载荷 type 必须为 "admin"
    - 必须查询 DB 复核 admin 存在且 is_active=True
    - 超级管理员（super_admin）与普通运营（operator）均通过此依赖
    """
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理员未登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    payload = _verify_token_not_blacklisted(payload)

    if payload.get("type") != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="非管理员 token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    admin_id = _subject_id(payload)
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=401, detail="管理员不存在")
    if not admin.is_active:
        raise HTTPException(status_code=403, detail="管理员账号已禁用")
    _verify_token_version(payload, admin)

    return admin


def require_super_admin(
    admin: Admin = Depends(get_current_admin),
) -> Admin:
    """要求超级管理员权限（super_admin）

    用于创建管理员、修改系统配置等高危操作
    """
    if admin.role != "super_admin":
        raise HTTPException(status_code=403, detail="需要超级管理员权限")
    return admin
