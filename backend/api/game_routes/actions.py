from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import char_brief, get_session_or_404, get_user_id
from database import get_db
from models import Character, CombatState, GameLog, Module, SessionMember
from schemas.game_requests import AITakeoverRequest, PlayerActionRequest
from schemas.game_responses import PlayerActionResponse
from services.character_roster import CharacterRoster
from services.game_action_source_service import normalize_action_source
from services.game_combat_action_service import execute_natural_language_combat_action
from services.game_exploration_service import execute_exploration_action
from services.game_multiplayer_service import (
    apply_multiplayer_room_decision,
    broadcast_multiplayer_table_message,
)
from services.langgraph_client import langgraph_client

router = APIRouter(prefix="/game", tags=["game"])


@router.post("/action", response_model=PlayerActionResponse)
async def player_action(
    req: PlayerActionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """玩家行动统一入口：战斗自然语言分支 + 探索 DM Agent 分支。"""
    session = await get_session_or_404(req.session_id, db)
    module = await db.get(Module, session.module_id)
    action_source = normalize_action_source(session, req.action_text, req.action_source)
    effective_action_text = req.action_text
    multiplayer_decision = None

    if session.is_multiplayer:
        player = await _resolve_multiplayer_player(db, session, user_id)
        if not session.combat_active:
            _assert_current_speaker(session, user_id)
            multiplayer_decision = await _run_multiplayer_table_gate(
                db=db,
                session=session,
                user_id=user_id,
                req=req,
            )
            if not multiplayer_decision.should_call_base_dm:
                return await _handle_multiplayer_table_only_result(
                    db=db,
                    session=session,
                    req=req,
                    user_id=user_id,
                    multiplayer_decision=multiplayer_decision,
                )
            effective_action_text = multiplayer_decision.effective_action_text or req.action_text
        await _broadcast_dm_thinking(session.id, user_id, req.action_text)
    else:
        player = await db.get(Character, session.player_character_id)

    roster = CharacterRoster(db, session)
    characters = ([player] if player else []) + await roster.companions()
    combat_state = await _load_latest_combat_state(db, session.id) if session.combat_active else None

    db.add(GameLog(
        session_id=req.session_id,
        role="player",
        content=req.action_text,
        log_type="narrative" if not session.combat_active else "combat",
    ))

    if session.combat_active:
        blocked = await _maybe_block_combat_input(
            db=db,
            session_id=req.session_id,
            action_text=req.action_text,
            action_source=action_source,
        )
        if blocked:
            return blocked

    if session.combat_active and combat_state and player:
        return await execute_natural_language_combat_action(
            db=db,
            session=session,
            combat_state=combat_state,
            player=player,
            characters=characters,
            action_text=req.action_text,
        )

    async def after_multiplayer_success():
        await apply_multiplayer_room_decision(
            db=db,
            session=session,
            actor_user_id=user_id,
            multiplayer_decision=multiplayer_decision,
        )

    after_multiplayer_success.multiplayer_visibility = (
        multiplayer_decision.visibility if multiplayer_decision else {}
    )
    after_multiplayer_success.multiplayer_table_reason = (
        multiplayer_decision.table_reason if multiplayer_decision else ""
    )
    after_multiplayer_success.multiplayer_table_decision = (
        multiplayer_decision.table_decision if multiplayer_decision else {}
    )

    return await execute_exploration_action(
        db=db,
        session=session,
        module=module,
        characters=characters,
        actor=player,
        actor_user_id=user_id,
        action_text=effective_action_text,
        action_source=action_source,
        combat_state=combat_state,
        after_success=after_multiplayer_success if multiplayer_decision else None,
    )


@router.post("/sessions/{session_id}/ai-takeover", response_model=PlayerActionResponse)
async def ai_takeover_action(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """替离线的当前发言者 AI 代演一句，然后走完整探索 DM 流程。"""
    from services.room_service import OFFLINE_THRESHOLD_SECONDS

    session = await get_session_or_404(session_id, db)
    if not session.is_multiplayer:
        raise HTTPException(400, "仅多人模式可用")
    if session.combat_active:
        raise HTTPException(400, "战斗中由先攻顺序自动处理 AI 行动，无需手动代演")

    if not await _get_session_member(db, session.id, user_id):
        raise HTTPException(403, "你不在该房间中")

    speaker_uid = ((session.game_state or {}).get("multiplayer", {}) or {}).get("current_speaker_user_id")
    if not speaker_uid:
        raise HTTPException(400, "当前没有发言者")
    if speaker_uid == user_id:
        raise HTTPException(400, "你就是当前发言者，请直接出招")

    speaker_member = await _get_session_member(db, session.id, speaker_uid)
    if not speaker_member or not speaker_member.character_id:
        raise HTTPException(400, "当前发言者没有绑定角色")

    threshold = datetime.utcnow() - timedelta(seconds=OFFLINE_THRESHOLD_SECONDS)
    if speaker_member.last_seen_at and speaker_member.last_seen_at >= threshold:
        raise HTTPException(409, "该玩家仍在线，无法触发 AI 代演（请等他出招或转发言权）")

    speaker_char = await db.get(Character, speaker_member.character_id)
    if not speaker_char:
        raise HTTPException(404, "speaker 的角色已被删除")

    module = await db.get(Module, session.module_id)
    roster = CharacterRoster(db, session)
    characters = [speaker_char] + await roster.companions()
    recent_contents = await _load_recent_log_contents(db, session_id)
    action_text = await langgraph_client.generate_takeover_action(
        character=char_brief(speaker_char),
        scene=session.current_scene or "",
        recent_logs=recent_contents,
    )

    db.add(GameLog(
        session_id=session_id,
        role="player",
        content=f"[AI 代演] {action_text}",
        log_type="narrative",
    ))
    await _broadcast_dm_thinking(session.id, speaker_uid, action_text)

    return await execute_exploration_action(
        db=db,
        session=session,
        module=module,
        characters=characters,
        actor=speaker_char,
        actor_user_id=speaker_uid,
        action_text=action_text,
        action_source="ai_takeover",
        is_takeover=True,
        takeover_by_user_id=user_id,
    )


async def _resolve_multiplayer_player(db: AsyncSession, session, user_id: str):
    member = await _get_session_member(db, session.id, user_id)
    if not member or not member.character_id:
        raise HTTPException(403, "你在该房间没有绑定角色")
    return await db.get(Character, member.character_id)


def _assert_current_speaker(session, user_id: str) -> None:
    multiplayer_state = (session.game_state or {}).get("multiplayer", {})
    speaker = multiplayer_state.get("current_speaker_user_id")
    if speaker and speaker != user_id:
        raise HTTPException(403, "现在不是你的发言时机，请等待 / 发言")


async def _run_multiplayer_table_gate(
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


async def _handle_multiplayer_table_only_result(
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


async def _broadcast_dm_thinking(session_id: str, user_id: str, action_text: str) -> None:
    try:
        from schemas.ws_events import DMThinkingStart
        from services.ws_manager import ws_manager

        await ws_manager.broadcast(session_id, DMThinkingStart(
            by_user_id=user_id,
            action_text=action_text[:80],
        ))
    except Exception:
        pass


async def _maybe_block_combat_input(
    *,
    db: AsyncSession,
    session_id: str,
    action_text: str,
    action_source: str,
) -> Optional[dict]:
    from services.input_guard import classify_player_input

    guard = await classify_player_input(action_text, source=action_source)
    if guard["verdict"] not in ("off_topic", "rule_violation", "injection"):
        return None

    db.add(GameLog(
        session_id=session_id,
        role="dm",
        content=guard["refusal"],
        log_type="combat",
    ))
    await db.commit()
    return {
        "type": f"blocked_{guard['verdict']}",
        "narrative": guard["refusal"],
        "companion_reactions": "",
        "dice_display": [],
        "player_choices": [],
        "needs_check": {"required": False},
        "combat_triggered": False,
        "combat_ended": False,
        "combat_end_result": None,
        "combat_update": None,
        "errors": [],
    }


async def _load_latest_combat_state(db: AsyncSession, session_id: str):
    result = await db.execute(
        select(CombatState)
        .where(CombatState.session_id == session_id)
        .order_by(CombatState.created_at.desc())
    )
    return result.scalars().first()


async def _get_session_member(db: AsyncSession, session_id: str, user_id: str):
    result = await db.execute(
        select(SessionMember).where(
            SessionMember.session_id == session_id,
            SessionMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _load_recent_log_contents(db: AsyncSession, session_id: str) -> list[str]:
    result = await db.execute(
        select(GameLog)
        .where(GameLog.session_id == session_id)
        .order_by(GameLog.created_at.desc())
        .limit(8)
    )
    return [log.content for log in reversed(result.scalars().all())]
