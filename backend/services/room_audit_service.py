"""Audit logging helpers for sensitive multiplayer room events."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from models import GameLog


def add_room_audit_log(
    db: AsyncSession,
    *,
    session_id: str,
    event_type: str,
    actor_user_id: str | None = None,
    target_user_id: str | None = None,
    details: dict | None = None,
) -> None:
    audit_payload = {
        "event_type": event_type,
        "actor_user_id": actor_user_id,
        "target_user_id": target_user_id,
        "details": details or {},
    }
    db.add(GameLog(
        session_id=session_id,
        role="system",
        content=_format_audit_content(audit_payload),
        log_type="system",
        visibility={"scope": "party", "audit": True},
        table_decision={"audit": audit_payload},
    ))


def _format_audit_content(audit_payload: dict) -> str:
    parts = [f"[Room Audit] {audit_payload['event_type']}"]
    if audit_payload.get("actor_user_id"):
        parts.append(f"actor={audit_payload['actor_user_id']}")
    if audit_payload.get("target_user_id"):
        parts.append(f"target={audit_payload['target_user_id']}")
    return " ".join(parts)
