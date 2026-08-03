"""雪花 ID 生成器（简化版，可选 uuid 兜底）"""

import time
import uuid
import threading
from typing import Optional


class SnowflakeId:
    """简化版雪花 ID
    - 1 bit 符号位
    - 41 bit 时间戳（毫秒，可用 ~69 年）
    - 5 bit datacenter_id（0-31）
    - 5 bit worker_id（0-31）
    - 12 bit 序列号（每毫秒 4096 个）
    """

    EPOCH = 1700000000000  # 2023-11-14 22:13:20 UTC

    def __init__(self, datacenter: int = 1, worker: int = 1):
        if not (0 <= datacenter <= 31):
            raise ValueError("datacenter_id must be 0-31")
        if not (0 <= worker <= 31):
            raise ValueError("worker_id must be 0-31")
        self.datacenter_id = datacenter
        self.worker_id = worker
        self._sequence = 0
        self._last_timestamp = -1
        self._lock = threading.Lock()

    def _current_millis(self) -> int:
        return int(time.time() * 1000)

    def _til_next_millis(self, last_ts: int) -> int:
        ts = self._current_millis()
        while ts <= last_ts:
            ts = self._current_millis()
        return ts

    def next_id(self) -> int:
        with self._lock:
            timestamp = self._current_millis()

            if timestamp < self._last_timestamp:
                raise RuntimeError("Clock moved backwards, refusing to generate id")

            if timestamp == self._last_timestamp:
                self._sequence = (self._sequence + 1) & 0xFFF
                if self._sequence == 0:
                    timestamp = self._til_next_millis(self._last_timestamp)
            else:
                self._sequence = 0

            self._last_timestamp = timestamp

            sid = (
                ((timestamp - self.EPOCH) << 22)
                | (self.datacenter_id << 17)
                | (self.worker_id << 12)
                | self._sequence
            )
            return sid


_default_snowflake: Optional[SnowflakeId] = None


def generate_id() -> int:
    """便捷函数：生成雪花 ID；失败时用 uuid 兜底（取 16 hex 转 int）"""
    global _default_snowflake
    try:
        if _default_snowflake is None:
            _default_snowflake = SnowflakeId(datacenter=1, worker=1)
        return _default_snowflake.next_id()
    except Exception:
        return int(uuid.uuid4().hex[:16], 16)


def generate_short_id() -> str:
    """生成短 ID（uuid4 hex 前 16 位）"""
    return uuid.uuid4().hex[:16]
