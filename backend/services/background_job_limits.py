from dataclasses import dataclass
import asyncio
from threading import Lock


class JobLimitExceeded(Exception):
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


@dataclass
class JobRunSlot:
    limiter: "BackgroundJobLimiter"
    released: bool = False

    def release(self) -> None:
        if self.released:
            return
        self.released = True
        self.limiter.release_running()


@dataclass
class JobReservation:
    limiter: "BackgroundJobLimiter"
    released: bool = False
    run_slot: JobRunSlot | None = None

    async def acquire_run_slot(self, *, max_concurrent: int) -> JobRunSlot:
        if self.run_slot is None:
            self.run_slot = await self.limiter.acquire_run_slot(max_concurrent=max_concurrent)
        return self.run_slot

    def release(self) -> None:
        if self.released:
            return
        self.released = True
        if self.run_slot is not None:
            self.run_slot.release()
        self.limiter.release()


class BackgroundJobLimiter:
    """Single-process backlog guard for beta background jobs."""

    def __init__(self, *, poll_seconds: float = 0.25):
        self._queued = 0
        self._running = 0
        self._poll_seconds = poll_seconds
        self._lock = Lock()

    def reserve(self, *, max_backlog: int) -> JobReservation:
        if max_backlog <= 0:
            return JobReservation(self)
        with self._lock:
            if self._queued >= max_backlog:
                raise JobLimitExceeded("后台解析队列已满，请稍后再上传")
            self._queued += 1
        return JobReservation(self)

    async def acquire_run_slot(self, *, max_concurrent: int) -> JobRunSlot:
        if max_concurrent <= 0:
            return JobRunSlot(self)

        while True:
            with self._lock:
                if self._running < max_concurrent:
                    self._running += 1
                    return JobRunSlot(self)
            await asyncio.sleep(self._poll_seconds)

    def release_running(self) -> None:
        with self._lock:
            self._running = max(0, self._running - 1)

    def release(self) -> None:
        with self._lock:
            self._queued = max(0, self._queued - 1)

    def stats(self) -> dict:
        return {
            "queued": self._queued,
            "running": self._running,
        }

    def clear(self) -> None:
        with self._lock:
            self._queued = 0
            self._running = 0


module_parse_limiter = BackgroundJobLimiter()
