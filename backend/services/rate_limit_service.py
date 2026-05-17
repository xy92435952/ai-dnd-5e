import time
from dataclasses import dataclass
from math import ceil
from threading import Lock


@dataclass
class RateLimitExceeded(Exception):
    retry_after: int


class InMemoryRateLimiter:
    """Small fixed-window limiter for one-backend closed beta deployments."""

    def __init__(self, now=None):
        self._now = now or time.time
        self._buckets: dict[str, tuple[float, int]] = {}
        self._lock = Lock()

    def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        if limit <= 0 or window_seconds <= 0:
            return

        now = self._now()
        with self._lock:
            window_start, count = self._buckets.get(key, (now, 0))
            if now - window_start >= window_seconds:
                window_start, count = now, 0

            if count >= limit:
                retry_after = max(1, ceil(window_seconds - (now - window_start)))
                raise RateLimitExceeded(retry_after=retry_after)

            self._buckets[key] = (window_start, count + 1)

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()


rate_limiter = InMemoryRateLimiter()
