"""安全工具：JWT 生成/验证、密码哈希"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4
import bcrypt
from jose import jwt, JWTError
from app.config import settings


def hash_password(password: str) -> str:
    """生成与历史 passlib bcrypt 哈希兼容的密码摘要。"""
    encoded = password.encode("utf-8")
    if not encoded or len(encoded) > 72:
        raise ValueError("密码 UTF-8 编码长度必须在 1 到 72 字节之间")
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    """校验 bcrypt 密码；畸形摘要或超长输入统一按失败处理。"""
    try:
        encoded = plain.encode("utf-8")
        if not encoded or len(encoded) > 72:
            return False
        return bcrypt.checkpw(encoded, hashed.encode("ascii"))
    except (TypeError, ValueError, UnicodeError):
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    # JWT 规范要求 sub 必须为字符串（python-jose 校验严格，整数会触发
    # JWTClaimsError: Subject must be a string）
    if "sub" in to_encode and not isinstance(to_encode["sub"], str):
        to_encode["sub"] = str(to_encode["sub"])
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=settings.JWT_EXPIRE_HOURS)
    )
    to_encode.update({"exp": expire, "jti": str(uuid4())})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
