"""API 限流配置（基于 slowapi）

设计：
- slowapi 提供装饰器 @limiter.limit("5/minute")，按 IP/用户限流
- 存储后端：内存（默认）或 Redis（生产分布式部署）
- 限流维度：默认按客户端 IP；登录类接口建议同时按 IP + 用户名
- 超限返回 429 Too Many Requests

敏感接口限流策略（已应用）：
- /api/admin/login          5/minute   防爆破
- /api/auth/wx-login        10/minute  防刷微信登录
- /api/auth/worker-login    10/minute
- /api/sms/send-code        1/minute   + 10/day  防短信轰炸
- /api/sms/verify-code       30/minute
- /api/wallet/withdraw      5/minute   防提现刷
- /api/upload/image         30/minute  防大量上传
- /api/upload/images        10/minute

通用接口默认限流（在 main.py 注册全局默认）：
- 全局默认：200/minute per IP

部署说明：
- 生产环境配置 RATE_LIMIT_STORAGE=redis://127.0.0.1:6379/1 启用分布式限流
- 单实例部署可不配置，使用内存存储
"""

from pathlib import Path
from typing import Optional
from urllib.parse import quote

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False


def _get_storage_uri() -> str:
    """获取限流存储 URI

    优先级：
    1. settings.RATE_LIMIT_STORAGE（显式配置）
    2. 生产环境：使用 Redis（与主 Redis 同实例，不同 DB）
    3. 开发模式：内存（不配置）
    """
    try:
        from app.config import settings
        explicit = getattr(settings, "RATE_LIMIT_STORAGE", "")
        if explicit:
            return explicit
        # 生产环境自动用 Redis
        if settings.is_deployed and settings.REDIS_HOST:
            pwd = f":{quote(settings.REDIS_PASSWORD, safe='')}@" if settings.REDIS_PASSWORD else ""
            return (
                f"redis://{pwd}{settings.REDIS_HOST}:{settings.REDIS_PORT}/"
                f"{settings.RATE_LIMIT_REDIS_DB}"
            )
    except Exception:
        pass
    return "memory://"  # 默认内存


# 限流 key 提取函数：优先用真实客户端 IP（处理反向代理）
def _get_client_ip(request) -> str:
    """提取真实客户端 IP

    优先级：
    1. X-Forwarded-For 第一个 IP（nginx/ALB 转发）
    2. X-Real-IP
    3. request.client.host
    """
    try:
        from app.config import settings
        peer = request.client.host if request.client else "0.0.0.0"
        if settings.TRUST_PROXY_HEADERS and _is_trusted_proxy(peer):
            xff = request.headers.get("X-Forwarded-For", "")
            if xff:
                forwarded = _resolve_forwarded_client(xff, peer)
                if forwarded:
                    return forwarded
            xri = request.headers.get("X-Real-IP", "")
            if xri and _is_valid_ip(xri.strip()):
                return xri.strip()
        return peer
    except Exception:
        return "0.0.0.0"


def _is_trusted_proxy(peer: str) -> bool:
    """仅允许显式配置网段内的直连代理提供转发头。"""
    import ipaddress
    from app.config import settings

    try:
        address = ipaddress.ip_address(peer)
        return any(
            address in ipaddress.ip_network(cidr, strict=False)
            for cidr in settings.trusted_proxy_cidr_list
        )
    except ValueError:
        return False


def _is_valid_ip(value: str) -> bool:
    import ipaddress

    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _resolve_forwarded_client(header_value: str, peer: str) -> Optional[str]:
    """从右向左剥离受信代理，防止客户端预置 X-Forwarded-For 左值。"""
    chain = [part.strip() for part in header_value.split(",") if part.strip()] + [peer]
    for candidate in reversed(chain):
        if not _is_valid_ip(candidate):
            return None
        if _is_trusted_proxy(candidate):
            continue
        return candidate
    return None


# 创建全局 limiter 实例
if SLOWAPI_AVAILABLE:
    limiter = Limiter(
        key_func=_get_client_ip,
        storage_uri=_get_storage_uri(),
        default_limits=["300/minute"],  # 全局默认上限
        # All runtime values above come from app.config/environment.  Point
        # SlowAPI at the empty package marker so it does not independently
        # parse .env with the Windows locale encoding (which breaks when the
        # UTF-8 .env contains Chinese comments).
        config_filename=str(Path(__file__).with_name("__init__.py")),
    )
else:
    # slowapi 未安装时使用 no-op 兼容 shim，避免 @limiter.limit(...) 报错
    class _NoOpLimiter:
        """无操作 limiter 占位符，slowapi 未安装时使用"""
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

        def shared_limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

    limiter = _NoOpLimiter()


def register_limiter(app) -> None:
    """注册限流中间件与异常处理器到 FastAPI app

    必须在路由注册之前调用（在 main.py 中）
    """
    if not SLOWAPI_AVAILABLE:
        # 未安装 slowapi 时不启用限流，但记录警告
        import warnings
        warnings.warn(
            "slowapi 未安装，API 限流未启用。生产环境请安装: pip install slowapi",
            RuntimeWarning,
            stacklevel=2,
        )
        return

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)


# ===== 限流策略常量（路由层引用）=====

# 登录类：防爆破
LIMIT_ADMIN_LOGIN = "5/minute"
LIMIT_WX_LOGIN = "10/minute"
LIMIT_WORKER_LOGIN = "10/minute"

# 短信：防轰炸
LIMIT_SMS_SEND = "1/minute"
LIMIT_SMS_SEND_DAILY = "10/day"
LIMIT_SMS_VERIFY = "30/minute"

# 钱包：防提现刷
LIMIT_WITHDRAW = "5/minute"

# 上传：防大量上传
LIMIT_UPLOAD_SINGLE = "30/minute"
LIMIT_UPLOAD_BATCH = "10/minute"

# 创建订单：防恶意下单
LIMIT_CREATE_ORDER = "20/minute"

# AI 下单助手：限制大模型调用成本
LIMIT_AI_AGENT = "30/minute"

# 评价：防刷评
LIMIT_REVIEW = "10/minute"

# 竞价：防刷
LIMIT_BIDDING = "30/minute"
