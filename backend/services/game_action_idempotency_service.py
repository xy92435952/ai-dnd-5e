import asyncio
import hashlib
import json
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from models import Session

MAX_ACTION_IDEMPOTENCY_RECORDS = 20
ACTION_IDEMPOTENCY_STATE_KEY = "action_idempotency"

_locks: dict[tuple[str, str, str], asyncio.Lock] = {}
_locks_guard = asyncio.Lock()


def normalize_idempotency_key(raw_key: Optional[str]) -> str:
    return (raw_key or "").strip()


async def get_action_idempotency_lock(session_id: str, user_id: str, key: str) -> asyncio.Lock:
    lock_id = (session_id, user_id, key)
    async with _locks_guard:
        lock = _locks.get(lock_id)
        if lock is None:
            lock = asyncio.Lock()
            _locks[lock_id] = lock
        return lock


def action_payload_fingerprint(
    *,
    user_id: str,
    action_text: str,
    action_source: str,
    session_id: str,
) -> str:
    payload = {
        "session_id": session_id,
        "user_id": user_id,
        "action_text": action_text,
        "action_source": action_source,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def get_cached_action_response(
    session: Session,
    *,
    key: str,
    fingerprint: str,
) -> dict[str, Any] | None:
    record = _get_record(session, key)
    if not record:
        return None
    _assert_same_fingerprint(record, fingerprint)
    if record.get("status") == "completed" and isinstance(record.get("response"), dict):
        return record["response"]
    if record.get("status") == "pending":
        raise HTTPException(409, "Action is already in progress; retry with the same idempotency key after it completes")
    return None


def mark_action_pending(
    session: Session,
    *,
    key: str,
    fingerprint: str,
    user_id: str,
) -> None:
    state = dict(session.game_state or {})
    records = dict(state.get(ACTION_IDEMPOTENCY_STATE_KEY) or {})
    record = records.get(key)
    if record:
        _assert_same_fingerprint(record, fingerprint)
        if record.get("status") == "completed":
            return
    records[key] = {
        "status": "pending",
        "fingerprint": fingerprint,
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    state[ACTION_IDEMPOTENCY_STATE_KEY] = _prune_records(records)
    session.game_state = state
    flag_modified(session, "game_state")


def mark_action_completed(
    session: Session,
    *,
    key: str,
    fingerprint: str,
    response: dict[str, Any],
) -> None:
    state = dict(session.game_state or {})
    records = dict(state.get(ACTION_IDEMPOTENCY_STATE_KEY) or {})
    records[key] = {
        **dict(records.get(key) or {}),
        "status": "completed",
        "fingerprint": fingerprint,
        "response": _json_safe_response(response),
        "completed_at": datetime.utcnow().isoformat() + "Z",
    }
    state[ACTION_IDEMPOTENCY_STATE_KEY] = _prune_records(records)
    session.game_state = state
    flag_modified(session, "game_state")


def clear_action_pending(
    session: Session,
    *,
    key: str,
    fingerprint: str,
) -> bool:
    state = dict(session.game_state or {})
    records = dict(state.get(ACTION_IDEMPOTENCY_STATE_KEY) or {})
    record = records.get(key)
    if not record:
        return False
    _assert_same_fingerprint(record, fingerprint)
    if record.get("status") != "pending":
        return False
    records.pop(key, None)
    state[ACTION_IDEMPOTENCY_STATE_KEY] = records
    session.game_state = state
    flag_modified(session, "game_state")
    return True


async def persist_pending_record(db: AsyncSession, session: Session, *, key: str, fingerprint: str, user_id: str) -> None:
    mark_action_pending(session, key=key, fingerprint=fingerprint, user_id=user_id)
    await db.commit()


async def persist_completed_record(db: AsyncSession, session: Session, *, key: str, fingerprint: str, response: dict[str, Any]) -> None:
    mark_action_completed(session, key=key, fingerprint=fingerprint, response=response)
    await db.commit()


async def clear_pending_record(db: AsyncSession, session_id: str, *, key: str, fingerprint: str) -> None:
    await db.rollback()
    fresh_session = await db.get(Session, session_id)
    if fresh_session and clear_action_pending(fresh_session, key=key, fingerprint=fingerprint):
        await db.commit()


def _get_record(session: Session, key: str) -> dict[str, Any] | None:
    records = ((session.game_state or {}).get(ACTION_IDEMPOTENCY_STATE_KEY) or {})
    record = records.get(key)
    return dict(record) if isinstance(record, dict) else None


def _assert_same_fingerprint(record: dict[str, Any], fingerprint: str) -> None:
    existing = record.get("fingerprint")
    if existing and existing != fingerprint:
        raise HTTPException(409, "Idempotency key already used for a different action")


def _prune_records(records: dict[str, Any]) -> dict[str, Any]:
    ordered = sorted(
        records.items(),
        key=lambda item: (
            item[1].get("completed_at")
            or item[1].get("created_at")
            or "",
        ),
    )
    return dict(ordered[-MAX_ACTION_IDEMPOTENCY_RECORDS:])


def _json_safe_response(response: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(response, ensure_ascii=False, default=str))
