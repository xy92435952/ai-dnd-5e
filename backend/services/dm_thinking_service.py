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
    group_id: Optional[str] = None,
) -> dict:
    """Persist a recoverable multiplayer DM-thinking snapshot on the session."""
    state = dict(session.game_state or {})
    multiplayer = dict(state.get("multiplayer") or {})
    resolved_group_id = (
        group_id
        or _group_id_for_user(multiplayer.get("party_groups") or [], actor_user_id)
        or multiplayer.get("active_group_id")
    )
    snapshot = {
        "active": True,
        "by_user_id": actor_user_id,
        "action_text": (action_text or "")[:80],
        "started_at": datetime.utcnow().isoformat() + "Z",
    }
    if resolved_group_id:
        snapshot["group_id"] = str(resolved_group_id)
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
    group_id: Optional[str] = None,
) -> dict | None:
    if not session.is_multiplayer:
        return None
    snapshot = set_dm_thinking_state(
        session,
        actor_user_id=actor_user_id,
        action_text=action_text,
        group_id=group_id,
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


def _group_id_for_user(party_groups, user_id: Optional[str]) -> Optional[str]:
    if user_id is None:
        return None
    target = str(user_id)
    for group in party_groups or []:
        if not isinstance(group, dict):
            continue
        if target in {str(uid) for uid in group.get("member_user_ids") or []}:
            group_id = group.get("id")
            return str(group_id) if group_id else None
    return None
