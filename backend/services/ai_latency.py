"""Lightweight latency tracing for player-facing AI paths."""

from __future__ import annotations

from contextlib import contextmanager
import logging
import time
from typing import Callable

logger = logging.getLogger("ai_latency")
# Keep player-facing latency traces visible under Uvicorn's default logging
# configuration without forcing a global application log level.
logger.setLevel(logging.INFO)


class AILatencyTrace:
    def __init__(
        self,
        *,
        route: str,
        session_id: str = "",
        user_id: str = "",
        metadata: dict | None = None,
        now: Callable[[], float] | None = None,
    ):
        self.route = route
        self.session_id = session_id
        self.user_id = user_id
        self.metadata = metadata or {}
        self._now = now or time.perf_counter
        self._started = self._now()
        self.timings_ms: dict[str, int] = {}

    @contextmanager
    def step(self, name: str):
        started = self._now()
        try:
            yield
        finally:
            self.timings_ms[name] = int(round((self._now() - started) * 1000))

    def total_ms(self) -> int:
        return int(round((self._now() - self._started) * 1000))

    def log_success(self, *, extra: dict | None = None) -> None:
        self._log("success", extra=extra)

    def log_error(self, *, error: Exception | str, extra: dict | None = None) -> None:
        merged = {"error": str(error)}
        if extra:
            merged.update(extra)
        self._log("error", extra=merged)

    def _log(self, status: str, *, extra: dict | None = None) -> None:
        fields = {
            "route": self.route,
            "status": status,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "total_ms": self.total_ms(),
            **self.metadata,
            **{f"{key}_ms": value for key, value in self.timings_ms.items()},
        }
        if extra:
            fields.update(extra)
        message = "ai_latency %s" % " ".join(f"{key}={value}" for key, value in fields.items())
        logger.info(message)
        # Uvicorn's default config attaches handlers to the "uvicorn" logger
        # tree, not the root logger, so mirror there when the server is active.
        if logging.getLogger("uvicorn").handlers:
            logging.getLogger("uvicorn.error").info(message)
