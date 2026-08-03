"""敏感字段加解密工具（AES-256-CBC + PBKDF2）

安全说明：
- 主密钥从 settings.FIELD_ENC_KEY 读取；为空时开发模式自动生成临时密钥（仅当前进程有效）
- 每次 encrypt 生成随机 16 字节 salt + 16 字节 IV，嵌入密文前部
  密文格式: base64(salt(16) || iv(16) || ciphertext)
- 相同明文每次加密结果不同，防止彩虹表/批量还原
- 移除了原版的明文 fallback — 缺 cryptography 库时直接抛异常
- 移除了原版的固定 salt — 改为每条数据随机 salt

用法：
    from app.utils.aes import encrypt_field, decrypt_field
    cipher = encrypt_field("350123199001011234")  # 加密身份证号
    plain = decrypt_field(cipher)                  # 解密
"""

import os
import base64
import hashlib
import secrets
from typing import Optional

try:
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


# PBKDF2 参数
_PBKDF2_ITERATIONS = 100000
_KEY_LENGTH = 32  # AES-256 需要 32 字节密钥
_SALT_LENGTH = 16
_IV_LENGTH = 16


def _get_master_key() -> str:
    """从 settings 获取主密钥

    - 生产环境：FIELD_ENC_KEY 必须配置（config.validate_security 已强制）
    - 开发模式：为空时自动生成临时密钥并打印警告（重启后已加密数据无法解密）
    """
    try:
        from app.config import settings
        key = settings.FIELD_ENC_KEY
        if key:
            return key
        # 开发模式兜底：临时密钥
        if not settings.is_deployed:
            import warnings
            warnings.warn(
                "FIELD_ENC_KEY 未配置，使用临时密钥；重启后已加密的 PII 字段将无法解密。"
                "生产环境请在 .env 中配置 FIELD_ENC_KEY",
                RuntimeWarning,
                stacklevel=2,
            )
            return _temp_key_for_dev
        # 生产环境理论不会到这里（validate_security 会拒绝启动）
        raise RuntimeError("FIELD_ENC_KEY 未配置")
    except Exception:
        # settings 加载失败时（极端情况）
        raise RuntimeError("无法加载 settings，FIELD_ENC_KEY 不可用")


# 开发模式临时密钥（进程级常量，重启变化）
_temp_key_for_dev: str = secrets.token_urlsafe(32)


def _derive_key(master: str, salt: bytes) -> bytes:
    """PBKDF2 派生密钥（每条数据 salt 随机）"""
    return hashlib.pbkdf2_hmac(
        "sha256", master.encode("utf-8"), salt, _PBKDF2_ITERATIONS, dklen=_KEY_LENGTH
    )


def encrypt_field(plain: Optional[str]) -> Optional[str]:
    """加密字段，返回 base64(salt || iv || ciphertext)

    Args:
        plain: 明文（None 或空字符串原样返回，不加密）

    Raises:
        RuntimeError: cryptography 库未安装
    """
    if plain is None or plain == "":
        return plain

    if not HAS_CRYPTO:
        raise RuntimeError("cryptography 库未安装，无法加密敏感字段")

    master = _get_master_key()
    salt = os.urandom(_SALT_LENGTH)
    iv = os.urandom(_IV_LENGTH)
    key = _derive_key(master, salt)

    padder = padding.PKCS7(128).padder()
    padded = padder.update(plain.encode("utf-8")) + padder.finalize()

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()

    raw = salt + iv + ciphertext
    return base64.b64encode(raw).decode("utf-8")


def decrypt_field(cipher_b64: Optional[str]) -> Optional[str]:
    """解密字段

    Args:
        cipher_b64: encrypt_field 返回的 base64 字符串

    Returns:
        明文；None/空字符串原样返回

    Raises:
        RuntimeError: cryptography 库未安装
        ValueError: 密文格式错误或解密失败
    """
    if cipher_b64 is None or cipher_b64 == "":
        return cipher_b64

    if not HAS_CRYPTO:
        raise RuntimeError("cryptography 库未安装，无法解密敏感字段")

    # 兼容旧数据：若仍是明文（如未加密的旧身份证号），原样返回
    # 检测方式：合法密文是 base64 且长度 >= salt+iv=32 字节
    try:
        raw = base64.b64decode(cipher_b64.encode("utf-8"))
    except Exception:
        # 非 base64，视为明文兼容返回
        return cipher_b64

    if len(raw) < _SALT_LENGTH + _IV_LENGTH:
        # 长度不足，视为明文兼容返回
        return cipher_b64

    master = _get_master_key()
    salt = raw[:_SALT_LENGTH]
    iv = raw[_SALT_LENGTH:_SALT_LENGTH + _IV_LENGTH]
    ciphertext = raw[_SALT_LENGTH + _IV_LENGTH:]
    key = _derive_key(master, salt)

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    try:
        padded = decryptor.update(ciphertext) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        data = unpadder.update(padded) + unpadder.finalize()
        return data.decode("utf-8")
    except Exception as e:
        raise ValueError(f"解密失败: {e}")


def mask_id_card(id_card: Optional[str]) -> Optional[str]:
    """身份证号脱敏显示：保留前 4 后 4，中间用 * 替换

    例: 350123199001011234 -> 3501**********1234
    """
    if not id_card or len(id_card) < 8:
        return id_card
    return id_card[:4] + "*" * (len(id_card) - 8) + id_card[-4:]


def mask_phone(phone: Optional[str]) -> Optional[str]:
    """手机号脱敏显示：保留前 3 后 4，中间用 * 替换

    例: 13800138000 -> 138****8000
    """
    if not phone or len(phone) < 7:
        return phone
    return phone[:3] + "*" * (len(phone) - 7) + phone[-4:]


# ===== 兼容旧 API（标记为废弃，仅转调新接口）=====

def aes_encrypt(plain: str, key: bytes = None) -> str:
    """[废弃] 兼容旧接口，转调 encrypt_field

    旧接口要求调用方传入 key，存在密钥管理风险，已废弃。
    新代码请直接使用 encrypt_field。
    """
    return encrypt_field(plain)


def aes_decrypt(cipher_b64: str, key: bytes = None) -> str:
    """[废弃] 兼容旧接口，转调 decrypt_field"""
    return decrypt_field(cipher_b64)


def derive_key(password: str) -> bytes:
    """[废弃] 兼容旧接口，返回固定派生密钥（仅供旧代码迁移期使用）"""
    if not HAS_CRYPTO:
        return hashlib.sha256(password.encode("utf-8")).digest()
    salt = b"zjr_repair_salt_fixed"
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS, dklen=_KEY_LENGTH)
