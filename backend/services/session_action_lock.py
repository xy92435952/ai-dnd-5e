"""In-process per-session locks for state-mutating game actions.

The current closed-beta deployment is a single backend worker. These locks
serialize high-risk writes inside that process so two player actions cannot
mutate the same session state at the same time. They are intentionally not a
distributed lock; Redis/PostgreSQL advisory locks are the next step before
multi-worker deployment.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator


_registry_guard = asyncio.Lock()
_locks: dict[str, asyncio.Lock] = {}


async def _get_lock(session_id: str) -> asyncio.Lock:
    async with _registry_guard:
        lock = _locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            _locks[session_id] = lock
        return lock


@dataclass
class SessionActionLockHandle:
    session_id: str
    _lock: asyncio.Lock
    _released: bool = False

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._lock.release()


async def acquire_session_action_lock(session_id: str) -> SessionActionLockHandle:
    lock = await _get_lock(session_id)
    await lock.acquire()
    return SessionActionLockHandle(session_id=session_id, _lock=lock)


@asynccontextmanager
async def session_action_lock(session_id: str) -> AsyncIterator[None]:
    handle = await acquire_session_action_lock(session_id)
    try:
        yield
    finally:
        handle.release()


def session_action_lock_stats() -> dict:
    return {
        "tracked_sessions": len(_locks),
        "locked_sessions": sum(1 for lock in _locks.values() if lock.locked()),
    }
