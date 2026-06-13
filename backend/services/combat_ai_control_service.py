from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Session, SessionMember


async def ai_combat_driver_user_id(
    db: AsyncSession,
    session: Session,
) -> str | None:
    """Resolve the user allowed to drive monster, lair, and AI-party combat."""
    if not session.is_multiplayer:
        return str(session.user_id) if session.user_id else None

    result = await db.execute(
        select(SessionMember)
        .where(SessionMember.session_id == session.id)
        .order_by(SessionMember.joined_at.asc())
    )
    members = list(result.scalars().all())
    if not members:
        return str(session.host_user_id) if session.host_user_id else None

    try:
        from services.room_member_service import OFFLINE_THRESHOLD_SECONDS
    except Exception:
        OFFLINE_THRESHOLD_SECONDS = 30
    threshold = datetime.utcnow() - timedelta(seconds=OFFLINE_THRESHOLD_SECONDS)
    online_members = [
        member for member in members
        if member.last_seen_at is not None and member.last_seen_at >= threshold
    ]
    candidates = online_members or members
    host_user_id = str(session.host_user_id) if session.host_user_id else None
    if host_user_id:
        host = next((member for member in candidates if str(member.user_id) == host_user_id), None)
        if host:
            return str(host.user_id)
    first = candidates[0] if candidates else None
    return str(first.user_id) if first and first.user_id else host_user_id


async def user_can_drive_ai_combat(
    db: AsyncSession,
    session: Session,
    user_id: str | None,
) -> bool:
    if not user_id:
        return False
    if not session.is_multiplayer:
        return True
    driver_user_id = await ai_combat_driver_user_id(db, session)
    return bool(driver_user_id and str(driver_user_id) == str(user_id))
