"""文件上传业务逻辑 — 开发模式本地存储，支持 mock OSS 签名

安全说明：
- 扩展名白名单 + 文件头魔数（magic bytes）双重校验，防止伪装上传
- 删除接口用 os.path.realpath + commonpath 防路径穿越
- 本地静态目录挂载应在 nginx/CDN 层统一加 Content-Disposition: attachment
"""

import os
import re
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
_MANAGED_OBJECT_KEY_RE = re.compile(
    r"^(?P<category>[a-z][a-z0-9_-]{0,31})/"
    r"(?:(?P<owner_id>[1-9][0-9]*)/)?"
    r"[0-9]{4}/[0-9]{2}/[0-9]{2}/[0-9a-f]{32}\."
    r"(?:jpg|jpeg|png|webp|pdf)$"
)

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
    rel_path = f"{category}/{_random_filename(ext)}"
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
    is_certificate = category == "certificate" or category.startswith("certificate/")
    headers = {"x-oss-object-acl": oss2.OBJECT_ACL_PRIVATE} if is_certificate else None
    bucket.put_object(key, file_bytes, headers=headers)

    # 认证材料永远绕过公共 CDN；只保存私有 origin 引用，读取时再签短时 URL。
    base = _build_oss_host(
        bucket_name,
        endpoint,
        "" if is_certificate else (cdn_domain or ""),
    )
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
    put_options = {"Bucket": bucket_name, "Body": io.BytesIO(file_bytes), "Key": key}
    is_certificate = category == "certificate" or category.startswith("certificate/")
    if is_certificate:
        put_options["ACL"] = "private"
    client.put_object(**put_options)

    if cdn_domain and not is_certificate:
        return f"{cdn_domain.rstrip('/')}/{key}"
    return f"https://{bucket_name}.cos.{region}.myqcloud.com/{key}"


def upload_image(
    category: str,
    file_bytes: bytes,
    filename: str,
    *,
    owner_id: Optional[int] = None,
) -> Dict[str, Any]:
    """上传单张图片/文件

    Args:
        category: 分类，certificate 证书类允许 20MB，其余(images 等)10MB
        file_bytes: 文件字节
        filename: 原始文件名
    """
    category = normalize_category(category)
    storage_category = category
    if category == "certificate":
        if owner_id is None or int(owner_id) <= 0:
            raise HTTPException(status_code=400, detail="认证材料缺少所属师傅")
        storage_category = f"certificate/{int(owner_id)}"
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
            url = upload_to_oss(file_bytes, filename, storage_category)
            return {"url": url, "size": len(file_bytes), "filename": filename}
        except Exception as exc:
            if settings.is_deployed:
                raise HTTPException(status_code=503, detail="对象存储暂不可用") from exc
    elif provider == "tencent":
        try:
            url = upload_to_cos(file_bytes, filename, storage_category)
            return {"url": url, "size": len(file_bytes), "filename": filename}
        except Exception as exc:
            if settings.is_deployed:
                raise HTTPException(status_code=503, detail="对象存储暂不可用") from exc

    return _save_local(file_bytes, filename, storage_category)


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


def _certificate_object_key(stored_url: str, worker_id: int) -> str:
    parsed = urlsplit(stored_url or "")
    marker = f"/certificate/{int(worker_id)}/"
    if marker not in parsed.path:
        raise HTTPException(status_code=400, detail="认证材料不属于该师傅")
    key = f"certificate/{int(worker_id)}/" + parsed.path.split(marker, 1)[1].lstrip("/")
    if ".." in key.split("/"):
        raise HTTPException(status_code=400, detail="认证材料对象键无效")
    return key


def validate_certificate_reference(stored_url: str, worker_id: int) -> None:
    """校验证件来自当前师傅的受检上传，并确认云端对象存在。"""
    from app.config import settings

    key = _certificate_object_key(stored_url, worker_id)
    parsed = urlsplit(stored_url)
    if not settings.is_deployed:
        if stored_url.startswith("/uploads/"):
            base_dir = os.path.realpath(_get_upload_dir())
            path = os.path.realpath(os.path.join(base_dir, key))
            if os.path.commonpath([base_dir, path]) != base_dir or not os.path.isfile(path):
                raise HTTPException(status_code=400, detail="认证材料不存在")
        return

    provider = settings.OSS_PROVIDER.strip().lower()
    try:
        if provider == "aliyun":
            import oss2

            expected_host = urlsplit(_build_oss_host(settings.OSS_BUCKET, settings.OSS_ENDPOINT)).hostname
            if parsed.hostname != expected_host:
                raise HTTPException(status_code=400, detail="认证材料来源无效")
            bucket = oss2.Bucket(
                oss2.Auth(settings.OSS_ACCESS_KEY, settings.OSS_SECRET_KEY),
                settings.OSS_ENDPOINT,
                settings.OSS_BUCKET,
            )
            bucket.head_object(key)
            return
        if provider == "tencent":
            from qcloud_cos import CosConfig, CosS3Client

            expected_host = f"{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com"
            if parsed.hostname != expected_host:
                raise HTTPException(status_code=400, detail="认证材料来源无效")
            client = CosS3Client(
                CosConfig(
                    Region=settings.COS_REGION,
                    SecretId=settings.COS_SECRET_ID,
                    SecretKey=settings.COS_SECRET_KEY,
                )
            )
            client.head_object(Bucket=settings.COS_BUCKET, Key=key)
            return
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="认证材料不存在或暂不可读") from exc
    raise HTTPException(status_code=503, detail="认证材料私有存储未配置")


def sign_private_download_url(
    stored_url: str,
    worker_id: int,
    expires_seconds: int = 600,
) -> str:
    """为私有认证材料生成短时 GET URL；拒绝签名非 certificate 对象。"""
    from app.config import settings

    key = _certificate_object_key(stored_url, worker_id)

    provider = settings.OSS_PROVIDER.strip().lower()
    try:
        if provider == "aliyun":
            import oss2

            auth = oss2.Auth(settings.OSS_ACCESS_KEY, settings.OSS_SECRET_KEY)
            bucket = oss2.Bucket(auth, settings.OSS_ENDPOINT, settings.OSS_BUCKET)
            return bucket.sign_url("GET", key, expires_seconds)
        if provider == "tencent":
            from qcloud_cos import CosConfig, CosS3Client

            config = CosConfig(
                Region=settings.COS_REGION,
                SecretId=settings.COS_SECRET_ID,
                SecretKey=settings.COS_SECRET_KEY,
            )
            client = CosS3Client(config)
            return client.get_presigned_url(
                Method="GET",
                Bucket=settings.COS_BUCKET,
                Key=key,
                Expired=expires_seconds,
            )
    except Exception as exc:
        if settings.is_deployed:
            raise HTTPException(status_code=503, detail="认证材料暂时无法读取") from exc

    if settings.is_deployed:
        raise HTTPException(status_code=503, detail="认证材料私有存储未配置")
    return stored_url


# ===== 删除 =====

def _normalize_host(host: Optional[str]) -> str:
    return (host or "").rstrip(".").lower()


def _validate_managed_object_key(key: str) -> str:
    """只接受本服务生成的对象 key，避免把删除接口变成任意 bucket 删除器。"""
    if not key or len(key) > 384 or "\\" in key or "%" in key:
        raise HTTPException(status_code=400, detail="文件对象键无效")
    if key.startswith("/") or "//" in key or any(
        segment in {"", ".", ".."} for segment in key.split("/")
    ):
        raise HTTPException(status_code=400, detail="文件对象键无效")
    matched = _MANAGED_OBJECT_KEY_RE.fullmatch(key)
    if not matched:
        raise HTTPException(status_code=400, detail="文件对象键不是受管上传对象")
    # 只有认证材料允许（且必须）携带师傅归属目录。
    category = matched.group("category")
    owner_id = matched.group("owner_id")
    if (category == "certificate") != bool(owner_id):
        raise HTTPException(status_code=400, detail="文件对象归属目录无效")
    return key


def _strict_cloud_url_key(url: str, allowed_hosts: set[str]) -> str:
    """从云端 URL 提取受管 key；拒绝歧义 URL、非 HTTPS 和伪造相似域名。"""
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="文件 URL 格式无效") from exc
    host = _normalize_host(parsed.hostname)
    if (
        parsed.scheme.lower() != "https"
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith("/")
        or parsed.path.startswith("//")
        or host not in {_normalize_host(item) for item in allowed_hosts if item}
    ):
        raise HTTPException(status_code=400, detail="文件 URL 不属于受管对象存储")
    return _validate_managed_object_key(parsed.path.lstrip("/"))


def get_managed_object_identity(url: str) -> Tuple[str, str]:
    """返回 ``(provider, object_key)``，同时完成删除目标的严格边界校验。"""
    from app.config import settings

    if not url or len(url) > 512:
        raise HTTPException(status_code=400, detail="无效的文件 URL")

    if url.startswith("/uploads/"):
        if settings.is_deployed or settings.OSS_PROVIDER.strip().lower() != "local":
            raise HTTPException(status_code=400, detail="本地文件 URL 不属于当前存储环境")
        return "local", _validate_managed_object_key(url[len("/uploads/"):])

    provider = settings.OSS_PROVIDER.strip().lower()
    if provider == "aliyun":
        origin_host = urlsplit(
            _build_oss_host(settings.OSS_BUCKET, settings.OSS_ENDPOINT)
        ).hostname
        cdn_host = (
            urlsplit(
                _build_oss_host(
                    settings.OSS_BUCKET,
                    settings.OSS_ENDPOINT,
                    settings.OSS_CDN_DOMAIN,
                )
            ).hostname
            if settings.OSS_CDN_DOMAIN
            else None
        )
        key = _strict_cloud_url_key(url, {origin_host or "", cdn_host or ""})
        if key.startswith("certificate/") and _normalize_host(
            urlsplit(url).hostname
        ) != _normalize_host(origin_host):
            raise HTTPException(status_code=400, detail="认证材料必须使用私有 origin URL")
        return provider, key
    if provider == "tencent":
        origin_host = f"{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com"
        cdn_host = None
        if settings.COS_CDN_DOMAIN:
            cdn_value = settings.COS_CDN_DOMAIN.strip()
            cdn_host = urlsplit(
                cdn_value if "://" in cdn_value else f"https://{cdn_value}"
            ).hostname
        key = _strict_cloud_url_key(url, {origin_host, cdn_host or ""})
        if key.startswith("certificate/") and _normalize_host(
            urlsplit(url).hostname
        ) != _normalize_host(origin_host):
            raise HTTPException(status_code=400, detail="认证材料必须使用私有 origin URL")
        return provider, key
    raise HTTPException(status_code=400, detail="当前存储提供商不支持该文件 URL")

def delete_file_by_url(url: str) -> bool:
    """删除本服务产生的本地/OSS/COS 对象。

    安全说明：
    - URL 主机必须与当前 provider 的 origin/CDN 精确匹配；
    - key 必须匹配服务端随机命名格式，不能删除 bucket 中的任意对象；
    - 本地文件仍用 realpath/commonpath 防符号链接和路径穿越。
    """
    from app.config import settings

    provider, key = get_managed_object_identity(url)
    if provider == "aliyun":
        try:
            import oss2

            bucket = oss2.Bucket(
                oss2.Auth(settings.OSS_ACCESS_KEY, settings.OSS_SECRET_KEY),
                settings.OSS_ENDPOINT,
                settings.OSS_BUCKET,
            )
            bucket.delete_object(key)
            return True
        except Exception as exc:
            raise HTTPException(status_code=503, detail="阿里云 OSS 删除暂不可用") from exc
    if provider == "tencent":
        try:
            from qcloud_cos import CosConfig, CosS3Client

            client = CosS3Client(
                CosConfig(
                    Region=settings.COS_REGION,
                    SecretId=settings.COS_SECRET_ID,
                    SecretKey=settings.COS_SECRET_KEY,
                )
            )
            client.delete_object(Bucket=settings.COS_BUCKET, Key=key)
            return True
        except Exception as exc:
            raise HTTPException(status_code=503, detail="腾讯云 COS 删除暂不可用") from exc

    base_dir = os.path.realpath(_get_upload_dir())
    full_path = os.path.realpath(os.path.join(base_dir, key))

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
