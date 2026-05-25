"""Start-game flow for multiplayer rooms."""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from models import GameLog, Module, Session
from services.room_lifecycle_service import is_game_started
from services.room_member_service import list_members_raw


def get_start_ready_user_ids(session: Session, members) -> list[str]:
    member_ids = {
        member.get("user_id") if isinstance(member, dict) else member.user_id
        for member in members
        if (member.get("character_id") if isinstance(member, dict) else member.character_id)
    }
    raw = ((session.game_state or {}).get("multiplayer", {}) or {}).get("start_ready_user_ids") or []
    return [user_id for user_id in raw if user_id in member_ids]


async def set_start_ready(
    db: AsyncSession,
    actor_user_id: str,
    session_id: str,
    ready: bool,
) -> dict:
    """Mark whether a room member is ready for the host to start the adventure."""
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")
    if is_game_started(session):
        raise HTTPException(409, "游戏已经开始")

    members = await list_members_raw(db, session_id)
    member = next((item for item in members if item.user_id == actor_user_id), None)
    if not member:
        raise HTTPException(403, "你不在该房间中")
    if ready and not member.character_id:
        raise HTTPException(400, "认领角色后才能确认准备")

    state = dict(session.game_state or {})
    mp = dict(state.get("multiplayer") or {})
    ready_ids = get_start_ready_user_ids(session, members)
    if ready:
        ready_ids = [*ready_ids, actor_user_id] if actor_user_id not in ready_ids else ready_ids
    else:
        ready_ids = [user_id for user_id in ready_ids if user_id != actor_user_id]

    mp["start_ready_user_ids"] = ready_ids
    state["multiplayer"] = mp
    session.game_state = state
    flag_modified(session, "game_state")
    await db.commit()
    return {"ready": ready, "start_ready_user_ids": ready_ids}


async def start_game(
    db: AsyncSession,
    actor_user_id: str,
    session_id: str,
) -> Session:
    """房主开始游戏。"""
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")
    if session.host_user_id != actor_user_id:
        raise HTTPException(403, "只有房主可以开始游戏")
    if is_game_started(session):
        raise HTTPException(409, "游戏已经开始")

    members = await list_members_raw(db, session_id)
    claimed = [m for m in members if m.character_id]
    unclaimed = [m for m in members if not m.character_id]
    if unclaimed:
        raise HTTPException(400, "所有玩家都需要认领角色后才能开始")
    ready_ids = set(get_start_ready_user_ids(session, members))
    unready = [m for m in members if m.user_id not in ready_ids]
    if unready:
        raise HTTPException(400, "所有玩家都需要确认准备后才能开始")

    already_started = bool(session.current_scene)
    if not already_started:
        if not session.player_character_id:
            session.player_character_id = claimed[0].character_id

        module = await db.get(Module, session.module_id)
        parsed = (module.parsed_content or {}) if module else {}
        scenes = parsed.get("scenes", []) or []
        raw_scene = scenes[0]["description"] if scenes and isinstance(scenes[0], dict) else ""
        try:
            from api.game import _generate_opening
            first_scene = await _generate_opening(parsed, raw_scene, (session.game_state or {}).get("dm_style"))
        except Exception:
            first_scene = raw_scene or "冒险正在开始……"

        session.current_scene = first_scene
        db.add(GameLog(
            session_id=session_id,
            role="dm",
            content=f"[开场] {first_scene}",
            log_type="narrative",
        ))

    state = session.game_state or {}
    mp = state.setdefault("multiplayer", {})
    mp["game_started"] = True
    mp["online_user_ids"] = [m.user_id for m in members]
    mp["current_speaker_user_id"] = claimed[0].user_id
    mp["speak_round"] = 1
    mp["pending_actions"] = []
    session.game_state = state
    flag_modified(session, "game_state")

    await db.commit()
    await db.refresh(session)
    return session
