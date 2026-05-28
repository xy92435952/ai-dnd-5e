from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from models import Session


def set_dm_thinking_state(
    session: Session,
    *,
    actor_user_id: str,
    action_text: str,
) -> dict:
    """Persist a recoverable multiplayer DM-thinking snapshot on the session."""
    state = dict(session.game_state or {})
    multiplayer = dict(state.get("multiplayer") or {})
    snapshot = {
        "active": True,
        "by_user_id": actor_user_id,
        "action_text": (action_text or "")[:80],
        "started_at": datetime.utcnow().isoformat() + "Z",
    }
    multiplayer["dm_thinking"] = snapshot
    state["multiplayer"] = multiplayer
    session.game_state = state
    flag_modified(session, "game_state")
    return snapshot


def clear_dm_thinking_state(
    session: Session,
    *,
    actor_user_id: Optional[str] = None,
) -> bool:
    """Clear the recoverable DM-thinking snapshot if it belongs to this action."""
    state = dict(session.game_state or {})
    multiplayer = dict(state.get("multiplayer") or {})
    current = multiplayer.get("dm_thinking")
    if not current:
        return False
    if actor_user_id and current.get("by_user_id") not in {None, actor_user_id}:
        return False

    multiplayer.pop("dm_thinking", None)
    state["multiplayer"] = multiplayer
    session.game_state = state
    flag_modified(session, "game_state")
    return True


async def start_dm_thinking(
    db: AsyncSession,
    session: Session,
    *,
    actor_user_id: str,
    action_text: str,
) -> dict | None:
    if not session.is_multiplayer:
        return None
    snapshot = set_dm_thinking_state(
        session,
        actor_user_id=actor_user_id,
        action_text=action_text,
    )
    await db.commit()
    return snapshot


async def clear_dm_thinking(
    db: AsyncSession,
    session: Session,
    *,
    actor_user_id: Optional[str] = None,
    broadcast_room: bool = False,
) -> bool:
    if not session.is_multiplayer:
        return False
    changed = clear_dm_thinking_state(session, actor_user_id=actor_user_id)
    if not changed:
        return False
    await db.commit()
    if broadcast_room:
        await _broadcast_room_snapshot(db, session)
    return True


async def _broadcast_room_snapshot(db: AsyncSession, session: Session) -> None:
    try:
        from schemas.ws_events import RoomStateUpdated
        from services import room_service
        from services.ws_manager import ws_manager

        room_info = await room_service.get_room_info(db, session.id)
        await ws_manager.broadcast(session.id, RoomStateUpdated(room=room_info))
    except Exception:
        pass
