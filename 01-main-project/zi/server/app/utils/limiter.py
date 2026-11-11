"""简易内存限流器（生产用 Redis 再升级）"""

import time
from collections import defaultdict
from typing import Any, Dict, Tuple


class RateLimiter:
    """
    滑动窗口/令牌桶简化版：固定窗口计数
    每个 user_id 在 period_sec 内最多调用 max_calls 次
    内存实现，重启失效；分布式部署请改用 Redis
    """

    def __init__(self, max_calls: int, period_sec: int):
        if max_calls <= 0:
            raise ValueError("max_calls must be > 0")
        if period_sec <= 0:
            raise ValueError("period_sec must be > 0")
        self.max_calls = max_calls
        self.period_sec = period_sec
        self._buckets: Dict[Any, list] = defaultdict(list)

    def _cleanup(self, key: Any, now: float) -> None:
        cutoff = now - self.period_sec
        self._buckets[key] = [t for t in self._buckets[key] if t > cutoff]

    def can_call(self, user_id: Any) -> Tuple[bool, int]:
        """
        尝试获取一次配额
        返回: (是否允许, 剩余可用次数)
        """
        now = time.time()
        key = user_id
        self._cleanup(key, now)

        timestamps = self._buckets[key]
        if len(timestamps) >= self.max_calls:
            remaining = 0
            return False, remaining

        timestamps.append(now)
        remaining = self.max_calls - len(timestamps)
        return True, remaining

    def remaining(self, user_id: Any) -> int:
        """查询剩余次数（不消耗配额）"""
        now = time.time()
        self._cleanup(user_id, now)
        return max(0, self.max_calls - len(self._buckets.get(user_id, [])))

    def reset(self, user_id: Any) -> None:
        """重置某用户配额"""
        if user_id in self._buckets:
            del self._buckets[user_id]
