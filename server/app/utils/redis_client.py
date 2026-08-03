"""Redis 缓存客户端 + Token 黑名单"""

import json
import pickle
import uuid
from functools import wraps
from typing import Any, Optional, Union

from app.config import settings

# 延迟导入 redis，若未安装则优雅降级
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None  # type: ignore
    REDIS_AVAILABLE = False


class RedisUnavailableError(RuntimeError):
    """部署环境无法判定安全状态时使用，调用方必须失败关闭。"""


class RedisClient:
    """Redis 封装：支持缓存、Token 黑名单、分布式锁"""

    def __init__(self):
        self._client: Optional[Any] = None
        self._enabled = False

    def _connect(self) -> bool:
        if not REDIS_AVAILABLE:
            return False
        if self._client is not None:
            return self._enabled
        try:
            self._client = redis.Redis(
                host=getattr(settings, "REDIS_HOST", "127.0.0.1"),
                port=getattr(settings, "REDIS_PORT", 6379),
                db=getattr(settings, "REDIS_DB", 0),
                password=getattr(settings, "REDIS_PASSWORD", None) or None,
                decode_responses=False,
                socket_connect_timeout=2,
                socket_timeout=2,
                health_check_interval=30,
            )
            self._client.ping()
            self._enabled = True
            return True
        except Exception:
            self._client = None
            self._enabled = False
            return False

    # ---------- 基础操作 ----------

    def get(self, key: str) -> Optional[bytes]:
        if not self._connect():
            return None
        try:
            return self._client.get(key)
        except Exception:
            return None

    def get_str(self, key: str) -> Optional[str]:
        val = self.get(key)
        return val.decode("utf-8") if val else None

    def get_json(self, key: str) -> Optional[Any]:
        val = self.get_str(key)
        return json.loads(val) if val else None

    def set(
        self,
        key: str,
        value: Union[str, bytes],
        ex: Optional[int] = None,
    ) -> bool:
        if not self._connect():
            return False
        try:
            if isinstance(value, str):
                value = value.encode("utf-8")
            self._client.set(key, value, ex=ex)
            return True
        except Exception:
            return False

    def set_json(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        return self.set(key, json.dumps(value, ensure_ascii=False), ex=ex)

    def delete(self, key: str) -> bool:
        if not self._connect():
            return False
        try:
            self._client.delete(key)
            return True
        except Exception:
            return False

    def exists(self, key: str) -> bool:
        if not self._connect():
            return False
        try:
            return bool(self._client.exists(key))
        except Exception:
            return False

    def ping(self) -> bool:
        """检查 Redis 是否可用。"""
        if not self._connect():
            return False
        try:
            return bool(self._client.ping())
        except Exception:
            self._client = None
            self._enabled = False
            return False

    def expire(self, key: str, seconds: int) -> bool:
        if not self._connect():
            return False
        try:
            return bool(self._client.expire(key, seconds))
        except Exception:
            return False

    # ---------- Token 黑名单（登出/风控） ----------

    def blacklist_token(self, token_jti: str, expire_seconds: int = 604800) -> bool:
        """将 Token 加入黑名单，默认 7 天过期"""
        return self.set(f"blacklist:token:{token_jti}", "1", ex=expire_seconds)

    def is_token_blacklisted(self, token_jti: str) -> bool:
        key = f"blacklist:token:{token_jti}"
        if not self._connect():
            if settings.is_deployed:
                raise RedisUnavailableError("Redis 不可用，无法校验 token 注销状态")
            return False
        try:
            return bool(self._client.exists(key))
        except Exception as exc:
            self._client = None
            self._enabled = False
            if settings.is_deployed:
                raise RedisUnavailableError("Redis 不可用，无法校验 token 注销状态") from exc
            return False

    # ---------- 缓存装饰器 ----------

    def cached(self, key_prefix: str, expire: int = 60):
        """函数结果缓存装饰器（仅对无异常返回值缓存）"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                cache_key = f"{key_prefix}:{func.__name__}:{hash(args + tuple(sorted(kwargs.items())))}"
                cached_val = self.get_json(cache_key)
                if cached_val is not None:
                    return cached_val
                result = func(*args, **kwargs)
                self.set_json(cache_key, result, ex=expire)
                return result
            return wrapper
        return decorator

    # ---------- 分布式锁（简易） ----------

    def acquire_lock(self, lock_key: str, expire_seconds: int = 10) -> Optional[str]:
        """获取带所有者令牌的分布式锁。

        生产环境 Redis 不可用时返回 ``None``（任务应跳过）；非生产环境返回
        ``local`` 令牌，便于单进程本地开发。
        """
        if not self._connect():
            return None if settings.is_deployed else "local"
        token = uuid.uuid4().hex
        try:
            acquired = self._client.set(lock_key, token, nx=True, ex=expire_seconds)
            return token if acquired else None
        except Exception:
            return None if settings.is_deployed else "local"

    def release_lock(self, lock_key: str, token: str) -> bool:
        """仅锁持有者可以释放，避免过期后误删其他进程的新锁。"""
        if token == "local":
            return True
        if not token or not self._connect():
            return False
        script = (
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
            "return redis.call('del', KEYS[1]) else return 0 end"
        )
        try:
            return bool(self._client.eval(script, 1, lock_key, token))
        except Exception:
            return False


# 全局单例
redis_client = RedisClient()
