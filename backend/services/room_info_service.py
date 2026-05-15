"""Aggregated room info for multiplayer lobby and exploration UI."""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models import Session
from services.room_ai_companion_service import list_ai_companions
from services.room_group_service import ensure_multiplayer_state
from services.room_lifecycle_service import is_game_started
from services.room_member_service import list_members


async def get_room_info(
    db: AsyncSession,
    session_id: str,
) -> dict:
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")
    mp_state = await ensure_multiplayer_state(db, session_id)
    members = await list_members(db, session_id)
    ai_companions = await list_ai_companions(db, session_id)
    mp = (session.game_state or {}).get("multiplayer", {})
    return {
        "session_id": session.id,
        "room_code": session.room_code,
        "module_id": session.module_id,
        "save_name": session.save_name,
        "host_user_id": session.host_user_id,
        "max_players": session.max_players,
        "is_multiplayer": session.is_multiplayer,
        "game_started": is_game_started(session),
        "members": members,
        "ai_companions": ai_companions,
        "current_speaker_user_id": mp.get("current_speaker_user_id"),
        "speak_round": mp.get("speak_round", 0),
        "party_groups": mp_state["party_groups"],
        "active_group_id": mp_state["active_group_id"],
        "pending_actions_by_group": mp_state["pending_actions_by_group"],
        "group_readiness": mp_state["group_readiness"],
        "created_at": session.created_at,
    }
