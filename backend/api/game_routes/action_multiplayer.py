from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models import Character, GameLog
from schemas.game_requests import PlayerActionRequest
from services.game_multiplayer_service import (
    apply_multiplayer_room_decision,
    broadcast_multiplayer_table_message,
)

from api.game_routes.action_runtime import get_session_member


async def resolve_multiplayer_player(db: AsyncSession, session, user_id: str):
    member = await get_session_member(db, session.id, user_id)
    if not member or not member.character_id:
        raise HTTPException(403, "你在该房间没有绑定角色")
    return await db.get(Character, member.character_id)


def assert_current_speaker(session, user_id: str) -> None:
    multiplayer_state = (session.game_state or {}).get("multiplayer", {})
    speaker = multiplayer_state.get("current_speaker_user_id")
    if not speaker:
        raise HTTPException(409, "当前没有发言者，请刷新房间状态")
    if speaker != user_id:
        raise HTTPException(403, "现在不是你的发言时机，请等待 / 发言")


async def run_multiplayer_table_gate(
    *,
    db: AsyncSession,
    session,
    user_id: str,
    req: PlayerActionRequest,
):
    from services.graphs.multiplayer_dm_agent import run_multiplayer_dm_agent

    return await run_multiplayer_dm_agent(
        db=db,
        session=session,
        actor_user_id=user_id,
        action_text=req.action_text,
    )


async def handle_multiplayer_table_only_result(
    *,
    db: AsyncSession,
    session,
    req: PlayerActionRequest,
    user_id: str,
    multiplayer_decision,
) -> dict:
    table_message = multiplayer_decision.table_message or "等待队伍决定下一步。"
    db.add(GameLog(
        session_id=req.session_id,
        role="player",
        content=req.action_text,
        log_type="narrative",
    ))
    db.add(GameLog(
        session_id=req.session_id,
        role="dm",
        content=table_message,
        log_type="narrative",
        visibility=multiplayer_decision.visibility,
        table_reason=multiplayer_decision.table_reason,
        table_decision=multiplayer_decision.table_decision,
    ))
    await apply_multiplayer_room_decision(
        db=db,
        session=session,
        actor_user_id=user_id,
        multiplayer_decision=multiplayer_decision,
    )
    await db.commit()
    await broadcast_multiplayer_table_message(
        session=session,
        actor_user_id=user_id,
        table_message=table_message,
        table_reason=multiplayer_decision.table_reason,
        table_decision=multiplayer_decision.table_decision,
        visibility=multiplayer_decision.visibility,
    )
    return {
        "type": "multiplayer_table",
        "narrative": table_message,
        "table_reason": multiplayer_decision.table_reason,
        "table_decision": multiplayer_decision.table_decision,
        "companion_reactions": "",
        "dice_display": [],
        "player_choices": [],
        "needs_check": {"required": False},
        "combat_triggered": False,
        "combat_ended": False,
        "combat_end_result": None,
        "combat_update": None,
        "visibility": multiplayer_decision.visibility,
        "errors": [],
    }
