"""文件上传业务逻辑 — 开发模式本地存储，支持 mock OSS 签名

安全说明：
- 扩展名白名单 + 文件头魔数（magic bytes）双重校验，防止伪装上传
- 删除接口用 os.path.realpath + commonpath 防路径穿越
- 本地静态目录挂载应在 nginx/CDN 层统一加 Content-Disposition: attachment
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from urllib.parse import urlsplit

from fastapi import HTTPException


def _get_upload_dir() -> str:
    """返回稳定的绝对上传目录，不受进程启动目录影响。"""
    try:
        from app.config import SERVER_ROOT, settings

        configured = Path(getattr(settings, "UPLOAD_DIR", "./uploads")).expanduser()
        if not configured.is_absolute():
            configured = SERVER_ROOT / configured
        return str(configured.resolve())
    except Exception:
        return str((Path(__file__).resolve().parents[2] / "uploads").resolve())


def _random_filename(ext: str) -> str:
    """生成按日期目录 + uuid 的文件名：2026/07/29/xxxxx.jpg"""
    now = datetime.now()
    date_dir = f"{now.year:04d}/{now.month:02d}/{now.day:02d}"
    name = uuid.uuid4().hex
    if not ext.startswith("."):
        ext = f".{ext}"
    return f"{date_dir}/{name}{ext}"


def _build_key(category: str, ext: str) -> str:
    """生成云存储对象键：images/2026/07/29/xxxxx.jpg"""
    now = datetime.now()
    date_dir = f"{now.year:04d}/{now.month:02d}/{now.day:02d}"
    name = uuid.uuid4().hex
    if ext and not ext.startswith("."):
        ext = f".{ext}"
    return f"{category}/{date_dir}/{name}{ext}"


def _build_oss_host(bucket: str, endpoint: str, cdn_domain: str = "") -> str:
    """根据 endpoint 生成 OSS 访问域名，endpoint 可为完整 URL 或域名"""
    if cdn_domain:
        value = cdn_domain.strip().rstrip("/")
        return value if "://" in value else "https://" + value

    raw = endpoint.strip().rstrip("/")
    parsed = urlsplit(raw if "://" in raw else "https://" + raw)
    if not parsed.hostname:
        raise ValueError("OSS endpoint 格式无效")
    scheme = parsed.scheme or "https"
    host = parsed.netloc
    bucket_prefix = bucket.lower() + "."
    if not parsed.hostname.lower().startswith(bucket_prefix):
        host = bucket + "." + host
    return f"{scheme}://{host}"


# 扩展名 → MIME 期望映射
ALLOWED_IMAGE_EXTS = {"jpg", "jpeg", "png", "webp", "pdf"}
_CATEGORY_RE = __import__("re").compile(r"^[a-z][a-z0-9_-]{0,31}$")

# 文件头魔数（magic bytes）校验表 — 防止 HTML/JS/SVG 伪装成图片上传
# 仅校验前若干字节即可确定真实类型
_MAGIC_BYTES = {
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "webp": [b"RIFF"],  # RIFF....WEBP
    "pdf": [b"%PDF"],
}


def _is_allowed_ext(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[-1].lower()
    return ext in ALLOWED_IMAGE_EXTS


def normalize_category(category: str) -> str:
    """限制对象键目录，避免特殊字符和路径片段进入云存储 key。"""
    value = (category or "images").strip().lower()
    if not _CATEGORY_RE.fullmatch(value):
        raise HTTPException(status_code=400, detail="上传分类格式不正确")
    return value


def _get_ext(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def _is_size_ok(file_bytes: bytes, max_mb: int) -> bool:
    return len(file_bytes) <= max_mb * 1024 * 1024


def _verify_magic_bytes(file_bytes: bytes, ext: str) -> bool:
    """校验文件头魔数是否与扩展名一致

    防止攻击者把 HTML/JS/SVG 重命名为 .jpg 上传导致存储型 XSS。
    PDF 与 webp 校验较宽松（PDF 头部固定 %PDF，webp 校验 RIFF+WEBP）。
    """
    if not file_bytes:
        return False
    expected = _MAGIC_BYTES.get(ext)
    if not expected:
        # 未在表中登记的扩展名不做魔数校验（已被白名单过滤）
        return True
    for magic in expected:
        if file_bytes.startswith(magic):
            # webp 还需校验偏移 8-12 字节为 WEBP
            if ext == "webp" and len(file_bytes) >= 12:
                return file_bytes[8:12] == b"WEBP"
            return True
    return False


def _ensure_dir(full_path: str) -> None:
    dir_name = os.path.dirname(full_path)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)


def _save_local(file_bytes: bytes, filename: str, category: str) -> Dict[str, Any]:
    """本地保存文件"""
    ext = _get_ext(filename)
    rel_path = _random_filename(ext)
    base_dir = os.path.realpath(_get_upload_dir())
    full_path = os.path.realpath(os.path.join(base_dir, rel_path))

    # 二次校验：确保最终路径仍在 base_dir 之内（防 rel_path 中含 ..）
    if os.path.commonpath([base_dir, full_path]) != base_dir:
        raise HTTPException(status_code=400, detail="非法的文件路径")

    _ensure_dir(full_path)

    with open(full_path, "wb") as f:
        f.write(file_bytes)

    size = len(file_bytes)
    url = f"/uploads/{rel_path}"

    return {
        "url": url,
        "size": size,
        "filename": filename,
    }


# ===== 上传 =====

def upload_to_oss(file_bytes: bytes, filename: str, category: str = "images") -> str:
    """直接上传文件到阿里云 OSS，返回可访问 URL。

    若未配置 OSS 或缺少 oss2 库则抛出异常，由调用方回退本地。
    """
    try:
        from app.config import settings
    except Exception as exc:
        raise RuntimeError("Settings not available") from exc

    access_key = getattr(settings, "OSS_ACCESS_KEY", None) or getattr(settings, "OSS_ACCESS_KEY_ID", None)
    secret_key = getattr(settings, "OSS_SECRET_KEY", None) or getattr(settings, "OSS_ACCESS_KEY_SECRET", None)
    bucket_name = getattr(settings, "OSS_BUCKET", None)
    endpoint = getattr(settings, "OSS_ENDPOINT", None)
    cdn_domain = getattr(settings, "OSS_CDN_DOMAIN", None)

    if not (access_key and secret_key and bucket_name and endpoint):
        raise RuntimeError("OSS not configured")

    try:
        import oss2
    except ImportError as exc:
        raise RuntimeError("oss2 library not installed") from exc

    ext = _get_ext(filename)
    key = _build_key(category, ext)

    auth = oss2.Auth(access_key, secret_key)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)
    bucket.put_object(key, file_bytes)

    base = _build_oss_host(bucket_name, endpoint, cdn_domain or "")
    return f"{base}/{key}"


def upload_to_cos(file_bytes: bytes, filename: str, category: str = "images") -> str:
    """直接上传文件到腾讯云 COS，返回可访问 URL。

    若未配置 COS 或缺少 qcloud_cos 库则抛出异常，由调用方回退本地。
    """
    try:
        from app.config import settings
    except Exception as exc:
        raise RuntimeError("Settings not available") from exc

    secret_id = getattr(settings, "COS_SECRET_ID", None)
    secret_key = getattr(settings, "COS_SECRET_KEY", None)
    bucket_name = getattr(settings, "COS_BUCKET", None)
    region = getattr(settings, "COS_REGION", None)
    cdn_domain = getattr(settings, "COS_CDN_DOMAIN", None)

    if not (secret_id and secret_key and bucket_name and region):
        raise RuntimeError("COS not configured")

    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError as exc:
        raise RuntimeError("qcloud_cos library not installed") from exc

    ext = _get_ext(filename)
    key = _build_key(category, ext)

    config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
    client = CosS3Client(config)

    import io
    client.put_object(Bucket=bucket_name, Body=io.BytesIO(file_bytes), Key=key)

    if cdn_domain:
        return f"{cdn_domain.rstrip('/')}/{key}"
    return f"https://{bucket_name}.cos.{region}.myqcloud.com/{key}"


def upload_image(category: str, file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """上传单张图片/文件

    Args:
        category: 分类，certificate 证书类允许 20MB，其余(images 等)10MB
        file_bytes: 文件字节
        filename: 原始文件名
    """
    category = normalize_category(category)
    if not _is_allowed_ext(filename):
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型，仅允许: {', '.join(sorted(ALLOWED_IMAGE_EXTS))}",
        )

    # 魔数校验：防止 HTML/JS/SVG 伪装成图片上传导致存储型 XSS
    ext = _get_ext(filename)
    if not _verify_magic_bytes(file_bytes, ext):
        raise HTTPException(
            status_code=400,
            detail="文件内容与扩展名不匹配，疑似伪造文件",
        )

    max_mb = 20 if category and category.lower() == "certificate" else 10
    if not _is_size_ok(file_bytes, max_mb):
        raise HTTPException(status_code=400, detail=f"文件大小超过上限 {max_mb}MB")

    provider = "local"
    try:
        from app.config import settings
        provider = getattr(settings, "OSS_PROVIDER", "local")
    except Exception:
        pass

    if provider == "aliyun":
        try:
            url = upload_to_oss(file_bytes, filename, category)
            return {"url": url, "size": len(file_bytes), "filename": filename}
        except Exception as exc:
            if settings.is_deployed:
                raise HTTPException(status_code=503, detail="对象存储暂不可用") from exc
    elif provider == "tencent":
        try:
            url = upload_to_cos(file_bytes, filename, category)
            return {"url": url, "size": len(file_bytes), "filename": filename}
        except Exception as exc:
            if settings.is_deployed:
                raise HTTPException(status_code=503, detail="对象存储暂不可用") from exc

    return _save_local(file_bytes, filename, category)


def upload_images_batch(
    files: List[Tuple[bytes, str]],
    category: str,
) -> List[Dict[str, Any]]:
    """批量上传，遇异常中断"""
    results: List[Dict[str, Any]] = []
    for file_bytes, filename in files:
        res = upload_image(category, file_bytes, filename)
        results.append(res)
    return results


# ===== 删除 =====

def delete_file_by_url(url: str) -> bool:
    """根据 URL 删除本地文件（防路径穿越）

    安全说明：
    - 用 os.path.realpath 解析最终绝对路径，再校验是否在上传目录内
    - 防止 url="/uploads/../../etc/passwd" 类攻击逃逸上传目录
    """
    if not url or not url.startswith("/uploads/"):
        raise HTTPException(status_code=400, detail="无效的文件 URL")

    # 解析相对路径，禁止 .. 与绝对路径
    rel = url[len("/uploads/"):]
    if not rel or ".." in rel.split("/"):
        raise HTTPException(status_code=400, detail="非法的文件路径")

    base_dir = os.path.realpath(_get_upload_dir())
    full_path = os.path.realpath(os.path.join(base_dir, rel))

    # 关键：二次校验最终路径必须仍在上传根目录下
    # 防止通过符号链接或特殊路径绕过前缀校验
    try:
        if os.path.commonpath([base_dir, full_path]) != base_dir:
            raise HTTPException(status_code=400, detail="非法的文件路径")
    except ValueError:
        # 跨盘符等异常情况
        raise HTTPException(status_code=400, detail="非法的文件路径")

    if not os.path.isfile(full_path):
        return False

    try:
        os.remove(full_path)
        return True
    except OSError:
        return False



# ===== OSS 签名（mock / 真实兼容）=====

def _sign_mock(category: str, provider: str = "local") -> Dict[str, Any]:
    from app.config import settings

    if settings.is_deployed:
        raise HTTPException(status_code=503, detail="生产环境禁止返回 Mock 上传签名")
    category = normalize_category(category)
    now_ts = int(datetime.utcnow().timestamp())
    expire_seconds = 3600
    date_dir = datetime.now().strftime("%Y/%m/%d")
    dir_prefix = f"{category}/{date_dir}/"
    return {
        "access_id": "mock-access-id",
        "policy": "mock-policy-base64==",
        "signature": "mock-signature-base64==",
        "dir": dir_prefix,
        "host": "https://mock-oss.example.com",
        "expire_seconds": expire_seconds,
        "provider": provider,
        "cdn_domain": "",
    }


def _sign_aliyun_oss(category: str) -> Dict[str, Any]:
    category = normalize_category(category)
    try:
        from app.config import settings
        access_id = getattr(settings, "OSS_ACCESS_KEY", None) or getattr(settings, "OSS_ACCESS_KEY_ID", None)
        access_secret = getattr(settings, "OSS_SECRET_KEY", None) or getattr(settings, "OSS_ACCESS_KEY_SECRET", None)
        bucket = getattr(settings, "OSS_BUCKET", None)
        endpoint = getattr(settings, "OSS_ENDPOINT", None)
        host = getattr(settings, "OSS_HOST", None)
        cdn_domain = getattr(settings, "OSS_CDN_DOMAIN", None)
    except Exception:
        access_id = access_secret = bucket = endpoint = host = cdn_domain = None

    now_ts = int(datetime.utcnow().timestamp())
    expire_seconds = 3600
    expire_ts = now_ts + expire_seconds

    date_dir = datetime.now().strftime("%Y/%m/%d")
    dir_prefix = f"{category}/{date_dir}/"

    if access_id and access_secret and bucket and endpoint:
        try:
            import oss2
            import json
            import base64
            import hmac
            import hashlib

            policy_dict = {
                "expiration": datetime.utcfromtimestamp(expire_ts).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "conditions": [
                    ["starts-with", "$key", dir_prefix],
                    {"bucket": bucket},
                ],
            }
            policy_b64 = base64.b64encode(json.dumps(policy_dict).encode("utf-8")).decode("utf-8")
            h = hmac.new(access_secret.encode("utf-8"), policy_b64.encode("utf-8"), hashlib.sha1)
            signature = base64.b64encode(h.digest()).decode("utf-8")
            host_value = host or _build_oss_host(bucket, endpoint, cdn_domain)
            return {
                "access_id": access_id,
                "policy": policy_b64,
                "signature": signature,
                "dir": dir_prefix,
                "host": host_value,
                "expire_seconds": expire_seconds,
                "provider": "aliyun",
                "cdn_domain": cdn_domain or "",
            }
        except ImportError:
            pass
        except Exception:
            pass

    from app.config import settings

    if settings.is_deployed:
        raise HTTPException(status_code=503, detail="阿里云 OSS 签名服务暂不可用")
    return _sign_mock(category, provider="aliyun")


def _sign_tencent_cos(category: str) -> Dict[str, Any]:
    category = normalize_category(category)
    try:
        from app.config import settings
        secret_id = getattr(settings, "COS_SECRET_ID", None)
        secret_key = getattr(settings, "COS_SECRET_KEY", None)
        bucket = getattr(settings, "COS_BUCKET", None)
        region = getattr(settings, "COS_REGION", None)
        cdn_domain = getattr(settings, "COS_CDN_DOMAIN", None)
    except Exception:
        secret_id = secret_key = bucket = region = cdn_domain = None

    now_ts = int(datetime.utcnow().timestamp())
    expire_seconds = 3600
    expire_ts = now_ts + expire_seconds

    date_dir = datetime.now().strftime("%Y/%m/%d")
    dir_prefix = f"{category}/{date_dir}/"

    if secret_id and secret_key and bucket and region:
        try:
            import json
            import base64
            import hmac
            import hashlib

            policy_dict = {
                "expiration": datetime.utcfromtimestamp(expire_ts).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "conditions": [
                    ["starts-with", "$key", dir_prefix],
                    {"bucket": bucket},
                ],
            }
            policy_b64 = base64.b64encode(json.dumps(policy_dict).encode("utf-8")).decode("utf-8")
            h = hmac.new(secret_key.encode("utf-8"), policy_b64.encode("utf-8"), hashlib.sha1)
            signature = base64.b64encode(h.digest()).decode("utf-8")
            host_value = (cdn_domain or f"https://{bucket}.cos.{region}.myqcloud.com").rstrip("/")
            return {
                "access_id": secret_id,
                "policy": policy_b64,
                "signature": signature,
                "dir": dir_prefix,
                "host": host_value,
                "expire_seconds": expire_seconds,
                "provider": "tencent",
                "cdn_domain": cdn_domain or "",
            }
        except Exception:
            pass

    from app.config import settings

    if settings.is_deployed:
        raise HTTPException(status_code=503, detail="腾讯云 COS 签名服务暂不可用")
    return _sign_mock(category, provider="tencent")


def sign_oss_upload(category: str = "images") -> Dict[str, Any]:
    """生成 OSS/COS 直传签名

    根据配置的 OSS_PROVIDER 返回对应云厂商的 post policy，未配置则返回 mock 值。
    """
    category = normalize_category(category)
    provider = "local"
    try:
        from app.config import settings
        provider = getattr(settings, "OSS_PROVIDER", "local")
    except Exception:
        pass

    if provider == "aliyun":
        return _sign_aliyun_oss(category)
    if provider == "tencent":
        return _sign_tencent_cos(category)
    if settings.is_deployed:
        raise HTTPException(status_code=400, detail="本地存储不支持客户端直传签名，请使用上传接口")
    return _sign_mock(category)
