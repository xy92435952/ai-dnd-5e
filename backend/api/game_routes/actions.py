from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import assert_can_act, assert_session_access, char_brief, get_session_or_404, get_user_id
from api.game_routes.action_multiplayer import (
    assert_current_speaker as _assert_current_speaker,
    handle_multiplayer_table_only_result as _handle_multiplayer_table_only_result,
    resolve_multiplayer_player as _resolve_multiplayer_player,
    run_multiplayer_table_gate as _run_multiplayer_table_gate,
)
from api.game_routes.action_runtime import (
    broadcast_dm_thinking as _broadcast_dm_thinking,
    get_session_member as _get_session_member,
    load_latest_combat_state as _load_latest_combat_state,
    load_recent_log_contents as _load_recent_log_contents,
    maybe_block_combat_input as _maybe_block_combat_input,
)
from database import get_db
from models import Character, GameLog, Module
from schemas.game_requests import PlayerActionRequest
from schemas.game_responses import PlayerActionResponse
from services.character_roster import CharacterRoster
from services.game_action_source_service import normalize_action_source
from services.game_combat_action_service import execute_natural_language_combat_action
from services.game_exploration_service import execute_exploration_action
from services.game_multiplayer_service import apply_multiplayer_room_decision
from services.langgraph_client import langgraph_client
from services.smoke_scenario_seed import (
    is_stage8_public_combat_sync_action,
    try_execute_stage7_5_seed_action,
    try_execute_stage8_public_combat_sync_action,
)
from services import room_service
from services.dm_thinking_service import clear_dm_thinking, start_dm_thinking
from services.game_action_idempotency_service import (
    action_payload_fingerprint,
    clear_pending_record,
    get_action_idempotency_lock,
    get_cached_action_response,
    normalize_idempotency_key,
    persist_completed_record,
    persist_pending_record,
)

router = APIRouter(prefix="/game", tags=["game"])


@router.post("/action", response_model=PlayerActionResponse)
async def player_action(
    req: PlayerActionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """玩家行动统一入口：战斗自然语言分支 + 探索 DM Agent 分支。"""
    key = normalize_idempotency_key(req.idempotency_key)
    if key:
        return await _run_player_action_idempotently(req=req, db=db, user_id=user_id, key=key)
    return await _run_player_action(req=req, db=db, user_id=user_id)


async def _run_player_action_idempotently(
    *,
    req: PlayerActionRequest,
    db: AsyncSession,
    user_id: str,
    key: str,
):
    session = await get_session_or_404(req.session_id, db)
    await assert_session_access(session, user_id, db)
    session_id = session.id
    action_source = normalize_action_source(session, req.action_text, req.action_source)
    fingerprint = action_payload_fingerprint(
        session_id=session_id,
        user_id=user_id,
        action_text=req.action_text,
        action_source=action_source,
    )

    lock = await get_action_idempotency_lock(session_id, user_id, key)
    async with lock:
        await db.refresh(session)
        cached = get_cached_action_response(session, key=key, fingerprint=fingerprint)
        if cached is not None:
            return cached
        await persist_pending_record(db, session, key=key, fingerprint=fingerprint, user_id=user_id)
    try:
        result = await _run_player_action(req=req, db=db, user_id=user_id)
        if result.get("retryable"):
            await clear_pending_record(db, session_id, key=key, fingerprint=fingerprint)
            return result
        await persist_completed_record(db, session, key=key, fingerprint=fingerprint, response=result)
        return result
    except Exception:
        await clear_pending_record(db, session_id, key=key, fingerprint=fingerprint)
        raise


async def _run_player_action(
    *,
    req: PlayerActionRequest,
    db: AsyncSession,
    user_id: str,
):
    session = await get_session_or_404(req.session_id, db)
    await assert_session_access(session, user_id, db)
    module = await db.get(Module, session.module_id)
    action_source = normalize_action_source(session, req.action_text, req.action_source)
    effective_action_text = req.action_text
    multiplayer_decision = None

    if session.is_multiplayer:
        await room_service.update_heartbeat(db, session.id, user_id)
        player = await _resolve_multiplayer_player(db, session, user_id)
        if not session.combat_active:
            if player:
                await assert_can_act(session, user_id, player.id, db, require_current_turn=False)
            _assert_current_speaker(session, user_id)
            if not is_stage8_public_combat_sync_action(req.action_text):
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
        dm_thinking = await start_dm_thinking(
            db,
            session,
            actor_user_id=user_id,
            action_text=req.action_text,
        )
        party_groups = ((session.game_state or {}).get("multiplayer", {}) or {}).get("party_groups") or []
        await _broadcast_dm_thinking(
            session.id,
            user_id,
            req.action_text,
            dm_thinking=dm_thinking,
            party_groups=party_groups,
        )
    else:
        player = await db.get(Character, session.player_character_id)
        if not session.combat_active and player:
            await assert_can_act(session, user_id, player.id, db, require_current_turn=False)

    roster = CharacterRoster(db, session)
    characters = await roster.party()
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
            await clear_dm_thinking(db, session, actor_user_id=user_id, broadcast_room=True)
            return blocked

    if session.combat_active and combat_state and player:
        await assert_can_act(session, user_id, player.id, db)
        try:
            result = await execute_natural_language_combat_action(
                db=db,
                session=session,
                combat_state=combat_state,
                player=player,
                characters=characters,
                action_text=req.action_text,
            )
            await clear_dm_thinking(db, session, actor_user_id=user_id, broadcast_room=True)
            return result
        except Exception:
            await db.rollback()
            fresh_session = await get_session_or_404(req.session_id, db)
            await clear_dm_thinking(db, fresh_session, actor_user_id=user_id, broadcast_room=True)
            raise

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

    stage7_5_result = await try_execute_stage7_5_seed_action(
        db=db,
        session=session,
        module=module,
        characters=characters,
        actor_user_id=user_id,
        action_text=effective_action_text,
        action_source=action_source,
    )
    if stage7_5_result is not None:
        await clear_dm_thinking(db, session, actor_user_id=user_id, broadcast_room=True)
        return stage7_5_result

    stage8_public_result = await try_execute_stage8_public_combat_sync_action(
        db=db,
        session=session,
        module=module,
        characters=characters,
        actor_user_id=user_id,
        action_text=effective_action_text,
        action_source=action_source,
    )
    if stage8_public_result is not None:
        if multiplayer_decision:
            await after_multiplayer_success()
            await db.commit()
        await clear_dm_thinking(db, session, actor_user_id=user_id, broadcast_room=True)
        await _broadcast_deterministic_action_result(session, user_id, stage8_public_result)
        return stage8_public_result

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
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)
    if not session.is_multiplayer:
        raise HTTPException(400, "仅多人模式可用")
    if session.combat_active:
        raise HTTPException(400, "战斗中由先攻顺序自动处理 AI 行动，无需手动代演")

    if not await _get_session_member(db, session.id, user_id):
        raise HTTPException(403, "你不在该房间中")
    await room_service.update_heartbeat(db, session.id, user_id)

    speaker_uid = ((session.game_state or {}).get("multiplayer", {}) or {}).get("current_speaker_user_id")
    if not speaker_uid:
        raise HTTPException(400, "当前没有发言者")
    if speaker_uid == user_id:
        raise HTTPException(400, "你就是当前发言者，请直接出招")

    speaker_member = await _get_session_member(db, session.id, speaker_uid)
    if not speaker_member or not speaker_member.character_id:
        raise HTTPException(400, "当前发言者没有绑定角色")

    threshold = datetime.utcnow() - timedelta(seconds=room_service.OFFLINE_THRESHOLD_SECONDS)
    if speaker_member.last_seen_at and speaker_member.last_seen_at >= threshold:
        raise HTTPException(409, "该玩家仍在线，无法触发 AI 代演（请等他出招或转发言权）")

    speaker_char = await db.get(Character, speaker_member.character_id)
    if not speaker_char:
        raise HTTPException(404, "speaker 的角色已被删除")

    await assert_can_act(session, speaker_uid, speaker_char.id, db, require_current_turn=False)

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
    dm_thinking = await start_dm_thinking(
        db,
        session,
        actor_user_id=speaker_uid,
        action_text=action_text,
    )
    party_groups = ((session.game_state or {}).get("multiplayer", {}) or {}).get("party_groups") or []
    await _broadcast_dm_thinking(
        session.id,
        speaker_uid,
        action_text,
        dm_thinking=dm_thinking,
        party_groups=party_groups,
    )

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


async def _broadcast_deterministic_action_result(session, actor_user_id: str, result: dict) -> None:
    if not session.is_multiplayer:
        return
    try:
        from schemas.ws_events import DMResponded
        from services.game_multiplayer_service import send_dm_responded_with_visibility

        visibility = result.get("visibility") or {}
        await send_dm_responded_with_visibility(
            session=session,
            visibility=visibility,
            event=DMResponded(
                by_user_id=actor_user_id,
                action_type=result.get("type") or "deterministic_action",
                narrative=result.get("narrative") or "",
                companion_reactions=result.get("companion_reactions") or "",
                dice_display=result.get("dice_display") or [],
                combat_triggered=bool(result.get("combat_triggered")),
                combat_ended=bool(result.get("combat_ended")),
                visibility=visibility,
                table_reason=result.get("table_reason") or "",
                table_decision=result.get("table_decision") or {},
            ),
        )
    except Exception:
        pass
