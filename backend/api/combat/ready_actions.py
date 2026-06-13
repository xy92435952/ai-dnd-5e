"""
api.combat.ready_actions — Ready action declaration endpoint.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Character, CombatState, GameLog
from api.deps import assert_can_act, get_session_or_404, get_user_id
from api.combat._shared import (
    _assert_expected_turn_token,
    _broadcast_combat,
    _build_combat_snapshot,
    _get_ts,
    _save_ts,
)
from api.combat.schemas import ReadyActionRequest
from schemas.combat_responses import CombatActionResult
from schemas.ws_events import CombatUpdate
from services.combat_action_rules_service import (
    CombatActionRuleError,
    validate_can_take_action,
    validate_can_take_reaction,
)
from services.combat_ready_action_service import (
    build_ready_attack_payload,
    build_ready_move_payload,
    build_ready_spell_actor_state,
    build_ready_spell_payload,
    set_ready_spell_concentration_hold,
    validate_ready_move_destination,
    validate_ready_spell,
)
from services.spell_service import spell_service

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/ready-action", response_model=CombatActionResult)
async def ready_action(
    session_id: str,
    req: ReadyActionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")
    await assert_can_act(session, user_id, req.entity_id, db)

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")
    _assert_expected_turn_token(combat, req.expected_turn_token, detail_prefix="Ready action")

    turn_order = combat.turn_order or []
    turn_index = combat.current_turn_index or 0
    current = turn_order[turn_index] if 0 <= turn_index < len(turn_order) else None
    current_id = current.get("character_id") if isinstance(current, dict) else None
    if current_id and str(current_id) != str(req.entity_id):
        raise HTTPException(400, "只能在当前角色回合准备动作")

    actor = await db.get(Character, req.entity_id)
    if not actor:
        raise HTTPException(404, "准备动作角色不存在")
    try:
        validate_can_take_action(actor)
        validate_can_take_reaction(actor)
    except CombatActionRuleError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    if req.action_type not in {"attack", "spell", "move"}:
        raise HTTPException(400, "当前仅支持准备攻击或准备法术")
    if req.trigger != "target_moves":
        raise HTTPException(400, "当前仅支持目标移动触发")
    if not req.target_id:
        raise HTTPException(400, "准备动作需要先选择目标")

    target_name = await _ready_target_name(db, session, req.target_id)
    if not target_name:
        raise HTTPException(404, "准备动作目标不存在")

    turn_state = _get_ts(combat, req.entity_id)
    if turn_state.get("action_used"):
        raise HTTPException(400, "本回合动作已使用")
    if turn_state.get("reaction_used"):
        raise HTTPException(400, "本回合反应已使用，无法准备动作")

    remaining_slots = None
    actor_state = None
    concentration_started = False
    concentration_spell_name = None
    concentration_effect_updates = []
    if req.action_type == "spell":
        spell = validate_ready_spell(req.spell_name, req.spell_level)
        effective_spell_level = int(req.spell_level or int(spell.get("level", 0) or 0) or 0)
        slot_already_consumed = False
        slot_key = None
        slots_remaining = None
        if effective_spell_level > 0:
            slot_key = spell_service.slot_key(effective_spell_level)
            new_slots, slot_error = spell_service.consume_slot(dict(actor.spell_slots or {}), effective_spell_level)
            if slot_error:
                raise HTTPException(400, slot_error)
            actor.spell_slots = new_slots
            remaining_slots = new_slots
            slots_remaining = int(new_slots.get(slot_key, 0) or 0)
            slot_already_consumed = True
        concentration_spell_name, concentration_effect_updates = await set_ready_spell_concentration_hold(
            db,
            session,
            actor,
            spell_name=req.spell_name or "",
            caster_id=str(req.entity_id),
        )
        actor_state = build_ready_spell_actor_state(actor)
        if concentration_effect_updates:
            actor_state["concentration_effect_updates"] = concentration_effect_updates
        concentration_started = True
        ready_payload = build_ready_spell_payload(
            actor_id=req.entity_id,
            actor_name=actor.name,
            target_id=req.target_id,
            target_name=target_name,
            spell_name=req.spell_name or "",
            spell_level=effective_spell_level,
            condition_text=req.condition_text,
            slot_already_consumed=slot_already_consumed,
            slot_key=slot_key,
            slots_remaining=slots_remaining,
            concentration_spell_name=concentration_spell_name,
            trigger_match=req.trigger_match,
        )
        narration = f"{actor.name} 准备法术：{ready_payload['condition_text']}。"
    elif req.action_type == "move":
        move_validation = validate_ready_move_destination(
            combat=combat,
            actor_id=req.entity_id,
            to_x=req.move_to_x,
            to_y=req.move_to_y,
            turn_state=turn_state,
            actor_conditions=list(actor.conditions or []),
        )
        ready_payload = build_ready_move_payload(
            actor_id=req.entity_id,
            actor_name=actor.name,
            target_id=req.target_id,
            target_name=target_name,
            move_from=move_validation["from"],
            move_to=move_validation["to"],
            move_distance=move_validation["distance"],
            condition_text=req.condition_text,
            trigger_match=req.trigger_match,
        )
        narration = f"{actor.name} \u51c6\u5907\u79fb\u52a8\uff1a{ready_payload['condition_text']}\u3002"
    else:
        ready_payload = build_ready_attack_payload(
            actor_id=req.entity_id,
            actor_name=actor.name,
            target_id=req.target_id,
            target_name=target_name,
            is_ranged=req.is_ranged,
            condition_text=req.condition_text,
            trigger_match=req.trigger_match,
        )
        narration = f"{actor.name} 准备攻击：{ready_payload['condition_text']}。"
    turn_state["action_used"] = True
    turn_state["ready_action"] = ready_payload
    _save_ts(combat, req.entity_id, turn_state)

    dice_result = {"type": "ready_action_declared", "ready_action": ready_payload}
    if actor_state:
        dice_result["actor_state"] = actor_state
    if concentration_started:
        dice_result["concentration_started"] = True
        dice_result["concentration_spell_name"] = concentration_spell_name
        dice_result["concentration_effect_updates"] = concentration_effect_updates
    response_payload = {
        "action": "ready_action",
        "narration": narration,
        "ready_action": ready_payload,
        "remaining_slots": remaining_slots,
        "turn_state": turn_state,
        "actor_state": actor_state,
        "caster_state": actor_state,
        "concentration_started": concentration_started,
        "concentration_spell_name": concentration_spell_name,
        "concentration_effect_updates": concentration_effect_updates,
        "combat": await _build_combat_snapshot(db, session, combat, viewer_character_id=str(req.entity_id)),
        "combat_over": False,
        "outcome": None,
        "dice_result": dice_result,
        "special_action": dice_result,
    }

    db.add(GameLog(
        session_id=session_id,
        role="player",
        content=narration,
        log_type="combat",
        dice_result=dice_result,
    ))
    await db.commit()
    await _broadcast_combat(
        session,
        combat,
        CombatUpdate(
            actor_id=str(req.entity_id),
            actor_name=actor.name,
            narration=narration,
            action="ready_action",
            ready_action=ready_payload,
            remaining_slots=remaining_slots,
            actor_state=actor_state,
            caster_state=actor_state,
            concentration_started=concentration_started,
            concentration_spell_name=concentration_spell_name,
            concentration_effect_updates=concentration_effect_updates,
            dice_result=dice_result,
            special_action=dice_result,
        ),
        db=db,
    )

    return response_payload


async def _ready_target_name(db, session, target_id: str) -> str:
    state = session.game_state or {}
    for enemy in state.get("enemies") or []:
        if str(enemy.get("id")) == str(target_id):
            return enemy.get("name") or str(target_id)
    character = await db.get(Character, target_id)
    if character and str(character.session_id) == str(session.id):
        return character.name
    return ""
