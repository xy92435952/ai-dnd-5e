import json
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from models import Character, CombatState, Module, Session
from services.context_builder import ContextBuilder
from services.dm_thinking_service import clear_dm_thinking, clear_dm_thinking_state
from services.game_combat_setup_service import init_combat
from services.game_multiplayer_service import send_dm_responded_with_visibility
from services.langgraph_client import langgraph_client
from services.state_applicator import StateApplicator


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
    builder = ContextBuilder(
        session=session,
        module=module,
        characters=characters,
        combat_state=combat_state,
    )
    inputs = await builder.build(
        player_action=action_text,
        current_actor_id=actor.id if actor else None,
    )

    session_id = session.id
    is_multiplayer = bool(session.is_multiplayer)
    thinking_cleared_for_success = False
    try:
        try:
            dm_result = await langgraph_client.call_dm_agent(
                **inputs,
                action_source=action_source,
                conversation_id=session.id,
            )
        except Exception as exc:
            raise HTTPException(502, f"AI服务暂时不可用: {str(exc)}") from exc
        if not dm_result.get("success", True):
            raise HTTPException(502, f"DM代理处理失败: {dm_result.get('error', '未知错误')}")

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
        applied = await applicator.apply(
            session=session,
            result_json=dm_result["result"],
            characters=characters,
            combat_state=combat_state,
        )

        if applied.combat_triggered:
            await init_combat(
                session=session,
                initial_enemies=applied.initial_enemies,
                characters=characters,
                module=module,
                db=db,
            )

        if after_success:
            await after_success()

        _persist_last_turn(
            session=session,
            applied=applied,
            actor_user_id=actor_user_id,
            is_takeover=is_takeover,
            takeover_by_user_id=takeover_by_user_id,
        )
        if session.is_multiplayer:
            clear_dm_thinking_state(session, actor_user_id=actor_user_id)
            thinking_cleared_for_success = True
        await db.commit()

        if session.is_multiplayer:
            await _broadcast_exploration_result(
                db=db,
                session=session,
                actor_user_id=actor_user_id,
                applied=applied,
                multiplayer_visibility=multiplayer_visibility,
                multiplayer_table_reason=multiplayer_table_reason,
                multiplayer_table_decision=multiplayer_table_decision,
            )

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
    finally:
        if is_multiplayer and not thinking_cleared_for_success:
            try:
                await db.rollback()
                fresh_session = await db.get(Session, session_id)
                if fresh_session:
                    await clear_dm_thinking(
                        db,
                        fresh_session,
                        actor_user_id=actor_user_id,
                        broadcast_room=True,
                    )
            except Exception:
                pass


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
    from schemas.ws_events import DMResponded, DMSpeakTurn, RoomStateUpdated

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
                from services import room_service
                room_info = await room_service.get_room_info(db, session.id)
                await ws_manager.broadcast(session.id, RoomStateUpdated(room=room_info))
        except Exception:
            pass
