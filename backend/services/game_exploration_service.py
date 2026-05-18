import json
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from models import Character, CombatState, Module, Session
from services.context_builder import ContextBuilder
from services.ai_latency import AILatencyTrace
from services.game_combat_setup_service import init_combat
from services.game_multiplayer_service import send_dm_responded_with_visibility
from services.langgraph_client import langgraph_client
from services.state_applicator import StateApplicator
from services.streaming_json import JsonStringFieldDeltaExtractor


async def execute_exploration_action(
    *,
    db: AsyncSession,
    session: Session,
    module: Optional[Module],
    characters: list[Character],
    actor: Optional[Character],
    actor_user_id: str,
    action_text: str,
    action_source: str = "human_input",
    combat_state: Optional[CombatState] = None,
    is_takeover: bool = False,
    takeover_by_user_id: Optional[str] = None,
    after_success=None,
) -> dict:
    """Run the shared exploration DM flow used by /game/action and AI takeover."""
    trace = AILatencyTrace(
        route="/game/action",
        session_id=session.id,
        user_id=actor_user_id,
        metadata={
            "mode": "exploration",
            "multiplayer": bool(session.is_multiplayer),
            "takeover": bool(is_takeover),
        },
    )
    inputs = {}
    try:
        builder = ContextBuilder(
            session=session,
            module=module,
            characters=characters,
            combat_state=combat_state,
        )
        with trace.step("context"):
            inputs = await builder.build(
                player_action=action_text,
                current_actor_id=actor.id if actor else None,
            )

        try:
            with trace.step("dm_agent"):
                dm_result = await langgraph_client.call_dm_agent(
                    **inputs,
                    action_source=action_source,
                    conversation_id=session.id,
                )
        except Exception as exc:
            trace.log_error(error=exc, extra=_latency_context_fields(inputs))
            raise HTTPException(502, f"AI服务暂时不可用: {str(exc)}") from exc
        if not dm_result.get("success", True):
            error = dm_result.get("error", "未知错误")
            trace.log_error(error=error, extra=_latency_context_fields(inputs))
            raise HTTPException(502, f"DM代理处理失败: {error}")

        multiplayer_visibility = getattr(after_success, "multiplayer_visibility", {}) if after_success else {}
        multiplayer_table_reason = getattr(after_success, "multiplayer_table_reason", "") if after_success else ""
        multiplayer_table_decision = getattr(after_success, "multiplayer_table_decision", {}) if after_success else {}
        _attach_multiplayer_table_metadata(
            dm_result=dm_result,
            multiplayer_visibility=multiplayer_visibility,
            multiplayer_table_reason=multiplayer_table_reason,
            multiplayer_table_decision=multiplayer_table_decision,
        )

        applicator = StateApplicator(db)
        with trace.step("apply_state"):
            applied = await applicator.apply(
                session=session,
                result_json=dm_result["result"],
                characters=characters,
                combat_state=combat_state,
            )

        if applied.combat_triggered:
            with trace.step("init_combat"):
                await init_combat(
                    session=session,
                    initial_enemies=applied.initial_enemies,
                    characters=characters,
                    module=module,
                    db=db,
                )

        if after_success:
            with trace.step("after_success"):
                await after_success()

        _persist_last_turn(
            session=session,
            applied=applied,
            actor_user_id=actor_user_id,
            is_takeover=is_takeover,
            takeover_by_user_id=takeover_by_user_id,
        )
        with trace.step("commit"):
            await db.commit()

        if session.is_multiplayer:
            with trace.step("broadcast"):
                await _broadcast_exploration_result(
                    db=db,
                    session=session,
                    actor_user_id=actor_user_id,
                    applied=applied,
                    multiplayer_visibility=multiplayer_visibility,
                    multiplayer_table_reason=multiplayer_table_reason,
                    multiplayer_table_decision=multiplayer_table_decision,
                )
        trace.log_success(extra={
            **_latency_context_fields(inputs),
            "action_type": applied.action_type,
            "combat_triggered": bool(applied.combat_triggered),
        })

        return _build_player_action_response(
            applied=applied,
            is_takeover=is_takeover,
            multiplayer_visibility=multiplayer_visibility,
            multiplayer_table_reason=multiplayer_table_reason,
            multiplayer_table_decision=multiplayer_table_decision,
        )
    except HTTPException:
        raise
    except Exception as exc:
        trace.log_error(error=exc, extra=_latency_context_fields(inputs))
        raise


async def execute_exploration_action_stream(
    *,
    db: AsyncSession,
    session: Session,
    module: Optional[Module],
    characters: list[Character],
    actor: Optional[Character],
    actor_user_id: str,
    action_text: str,
    action_source: str = "human_input",
    combat_state: Optional[CombatState] = None,
    is_takeover: bool = False,
    takeover_by_user_id: Optional[str] = None,
    after_success=None,
):
    """Run exploration DM flow while yielding user-facing streaming events."""
    trace = AILatencyTrace(
        route="/game/action/stream",
        session_id=session.id,
        user_id=actor_user_id,
        metadata={
            "mode": "exploration",
            "multiplayer": bool(session.is_multiplayer),
            "takeover": bool(is_takeover),
        },
    )
    inputs = {}
    extractor = JsonStringFieldDeltaExtractor("narrative")
    try:
        builder = ContextBuilder(
            session=session,
            module=module,
            characters=characters,
            combat_state=combat_state,
        )
        with trace.step("context"):
            inputs = await builder.build(
                player_action=action_text,
                current_actor_id=actor.id if actor else None,
            )
        yield {"event": "phase", "data": {"phase": "context_ready"}}

        dm_result = None
        try:
            with trace.step("dm_agent"):
                async for event in langgraph_client.stream_dm_agent(
                    **inputs,
                    action_source=action_source,
                    conversation_id=session.id,
                ):
                    if event.get("type") == "llm_token":
                        for delta in extractor.feed(event.get("content", "")):
                            if delta:
                                yield {"event": "narrative_delta", "data": {"text": delta}}
                    elif event.get("type") == "final":
                        dm_result = event.get("payload")
        except Exception as exc:
            trace.log_error(error=exc, extra=_latency_context_fields(inputs))
            yield {"event": "error", "data": {"detail": f"AI服务暂时不可用: {str(exc)}"}}
            return

        if not dm_result:
            trace.log_error(error="DM Agent 未返回最终结果", extra=_latency_context_fields(inputs))
            yield {"event": "error", "data": {"detail": "DM代理处理失败: 未返回最终结果"}}
            return
        if not dm_result.get("success", True):
            error = dm_result.get("error", "未知错误")
            trace.log_error(error=error, extra=_latency_context_fields(inputs))
            yield {"event": "error", "data": {"detail": f"DM代理处理失败: {error}"}}
            return

        multiplayer_visibility = getattr(after_success, "multiplayer_visibility", {}) if after_success else {}
        multiplayer_table_reason = getattr(after_success, "multiplayer_table_reason", "") if after_success else ""
        multiplayer_table_decision = getattr(after_success, "multiplayer_table_decision", {}) if after_success else {}
        _attach_multiplayer_table_metadata(
            dm_result=dm_result,
            multiplayer_visibility=multiplayer_visibility,
            multiplayer_table_reason=multiplayer_table_reason,
            multiplayer_table_decision=multiplayer_table_decision,
        )

        applicator = StateApplicator(db)
        with trace.step("apply_state"):
            applied = await applicator.apply(
                session=session,
                result_json=dm_result["result"],
                characters=characters,
                combat_state=combat_state,
            )

        if applied.combat_triggered:
            with trace.step("init_combat"):
                await init_combat(
                    session=session,
                    initial_enemies=applied.initial_enemies,
                    characters=characters,
                    module=module,
                    db=db,
                )

        if after_success:
            with trace.step("after_success"):
                await after_success()

        _persist_last_turn(
            session=session,
            applied=applied,
            actor_user_id=actor_user_id,
            is_takeover=is_takeover,
            takeover_by_user_id=takeover_by_user_id,
        )
        with trace.step("commit"):
            await db.commit()

        if session.is_multiplayer:
            with trace.step("broadcast"):
                await _broadcast_exploration_result(
                    db=db,
                    session=session,
                    actor_user_id=actor_user_id,
                    applied=applied,
                    multiplayer_visibility=multiplayer_visibility,
                    multiplayer_table_reason=multiplayer_table_reason,
                    multiplayer_table_decision=multiplayer_table_decision,
                )

        trace.log_success(extra={
            **_latency_context_fields(inputs),
            "action_type": applied.action_type,
            "combat_triggered": bool(applied.combat_triggered),
        })

        yield {
            "event": "final",
            "data": _build_player_action_response(
                applied=applied,
                is_takeover=is_takeover,
                multiplayer_visibility=multiplayer_visibility,
                multiplayer_table_reason=multiplayer_table_reason,
                multiplayer_table_decision=multiplayer_table_decision,
            ),
        }
    except Exception as exc:
        trace.log_error(error=exc, extra=_latency_context_fields(inputs))
        yield {"event": "error", "data": {"detail": str(exc)}}


def _latency_context_fields(inputs: dict) -> dict:
    return {
        "game_state_chars": len(inputs.get("game_state") or ""),
        "module_context_chars": len(inputs.get("module_context") or ""),
        "campaign_memory_chars": len(inputs.get("campaign_memory") or ""),
        "retrieved_context_chars": len(inputs.get("retrieved_context") or ""),
    }


def _build_player_action_response(
    *,
    applied,
    is_takeover: bool,
    multiplayer_visibility: dict,
    multiplayer_table_reason: str,
    multiplayer_table_decision: dict,
) -> dict:
    return {
        "type": applied.action_type,
        "narrative": applied.narrative,
        "companion_reactions": applied.companion_reactions,
        "dice_display": applied.dice_display,
        "player_choices": [] if is_takeover else applied.player_choices,
        "needs_check": None if is_takeover else applied.needs_check,
        "combat_triggered": applied.combat_triggered,
        "combat_ended": applied.combat_ended,
        "combat_end_result": applied.combat_end_result,
        "combat_update": None,
        "visibility": multiplayer_visibility,
        "table_reason": multiplayer_table_reason,
        "table_decision": multiplayer_table_decision,
        "errors": applied.errors,
    }


def _attach_multiplayer_table_metadata(
    *,
    dm_result: dict,
    multiplayer_visibility: dict,
    multiplayer_table_reason: str,
    multiplayer_table_decision: dict,
) -> None:
    if not (multiplayer_visibility or multiplayer_table_reason or multiplayer_table_decision):
        return

    try:
        result_payload = json.loads(dm_result["result"])
        if not isinstance(result_payload, dict):
            return
        if multiplayer_visibility:
            result_payload["visibility"] = multiplayer_visibility
        if multiplayer_table_reason:
            result_payload["table_reason"] = multiplayer_table_reason
        if multiplayer_table_decision:
            result_payload["table_decision"] = multiplayer_table_decision
        dm_result["result"] = json.dumps(result_payload, ensure_ascii=False)
    except Exception:
        pass


def _persist_last_turn(
    *,
    session: Session,
    applied,
    actor_user_id: str,
    is_takeover: bool,
    takeover_by_user_id: Optional[str],
) -> None:
    game_state = dict(session.game_state or {})
    last_turn = {
        "player_choices": applied.player_choices or [],
        "needs_check": applied.needs_check if (applied.needs_check and applied.needs_check.get("required")) else None,
        "last_actor_user_id": actor_user_id,
        "action_type": applied.action_type,
        "ts": datetime.utcnow().isoformat(),
    }
    if is_takeover:
        last_turn["ai_takeover"] = True
        if takeover_by_user_id:
            last_turn["takeover_by"] = takeover_by_user_id
    game_state["last_turn"] = last_turn
    session.game_state = game_state
    flag_modified(session, "game_state")


async def _broadcast_exploration_result(
    *,
    db: AsyncSession,
    session: Session,
    actor_user_id: str,
    applied,
    multiplayer_visibility: dict,
    multiplayer_table_reason: str,
    multiplayer_table_decision: dict,
) -> None:
    from schemas.ws_events import DMResponded, DMSpeakTurn

    try:
        await send_dm_responded_with_visibility(
            session=session,
            visibility=multiplayer_visibility,
            event=DMResponded(
                by_user_id=actor_user_id,
                action_type=applied.action_type,
                narrative=applied.narrative,
                companion_reactions=applied.companion_reactions or "",
                dice_display=applied.dice_display or [],
                combat_triggered=applied.combat_triggered,
                combat_ended=applied.combat_ended,
                visibility=multiplayer_visibility,
                table_reason=multiplayer_table_reason,
                table_decision=multiplayer_table_decision,
            ),
        )
    except Exception:
        pass

    if not session.combat_active and not applied.combat_triggered:
        try:
            from services.ws_manager import ws_manager
            from api.ws import _advance_speaker

            next_user = await _advance_speaker(db, session.id, actor_user_id)
            if next_user:
                await ws_manager.broadcast(session.id, DMSpeakTurn(user_id=next_user, auto=True))
        except Exception:
            pass
