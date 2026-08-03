"""安全中间件集合

包含：
1. SecurityHeadersMiddleware — 注入安全响应头
   - X-Content-Type-Options: nosniff（防 MIME sniffing）
   - X-Frame-Options: DENY（防点击劫持）
   - X-XSS-Protection: 1; mode=block（旧浏览器 XSS 过滤）
   - Referrer-Policy: strict-origin-when-cross-origin
   - Strict-Transport-Security（生产强制 HTTPS）
   - Content-Security-Policy: default-src 'self'（管理后台页面）
   - Permissions-Policy（限制设备 API）

2. 限流中间件配置（slowapi 集成）
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """注入安全响应头

    所有响应都会附加以下头：
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: 限制摄像头/麦克风/地理位置等

    生产环境额外附加：
    - Strict-Transport-Security: max-age=31536000; includeSubDomains
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # 防止 MIME sniffing（防止上传 SVG/HTML 被当 HTML 解析）
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 防止点击劫持（管理后台禁止被 iframe 嵌套）
        response.headers["X-Frame-Options"] = "DENY"

        # 旧浏览器 XSS 过滤
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer 仅在同源时发送完整 URL，跨源仅发 origin
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 权限策略：禁用敏感设备 API
        response.headers["Permissions-Policy"] = (
            "geolocation=(self), microphone=(), camera=(), "
            "payment=(self), usb=(), magnetometer=(), gyroscope=()"
        )

        # 生产环境强制 HTTPS（仅在 HTTPS 响应时生效）
        if settings.is_deployed:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # 管理后台页面（/admin）附加 CSP
        if request.url.path.startswith("/admin"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://unpkg.com; "
                "img-src 'self' data: https: http:; "
                "font-src 'self' data:; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            )

        return response


def get_cors_origins() -> list:
    """获取 CORS 允许的源列表

    - 生产环境：必须显式配置 CORS_ORIGINS 白名单
    - 开发模式（APP_DEBUG=true）且未配置 CORS_ORIGINS：允许 *（便于本地联调）
    """
    origins = settings.cors_origin_list
    if origins:
        return origins
    # 开发模式兜底
    if settings.APP_DEBUG:
        return ["*"]
    # 非开发非生产（staging 或未明确指定），保守策略
    return []


def should_enable_trusted_host() -> bool:
    """是否启用 TrustedHostMiddleware

    - 生产环境：必须启用
    - 开发模式：默认不启用（localhost 联调方便）
    """
    return settings.is_deployed or bool(settings.allowed_hosts_list)


def get_allowed_hosts() -> list:
    """获取 TrustedHost 白名单"""
    hosts = settings.allowed_hosts_list
    if not hosts and settings.APP_DEBUG:
        # 开发模式默认允许 localhost
        return ["localhost", "127.0.0.1", "*"]
    return hosts or ["*"]
