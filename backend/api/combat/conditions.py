"""Manual combat condition add/remove endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from database import get_db
from models import Character, CombatState, GameLog
from api.deps import (
    assert_can_act,
    assert_character_in_session,
    assert_session_access,
    get_session_or_404,
    get_user_id,
)
from api.combat._shared import _assert_ai_combat_driver, _broadcast_combat
from api.combat.schemas import ConditionRequest
from schemas.combat_responses import ConditionUpdateResult
from schemas.ws_events import CombatUpdate
from services.combat_concentration_effect_service import (
    clear_concentration_effects_for_caster,
    discard_condition_sources,
)
from services.combat_concentration_service import break_concentration_if_incapacitated
from services.combat_condition_immunity_service import is_condition_immune
from services.dnd_rules import get_life_state

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/condition/add", response_model=ConditionUpdateResult)
async def add_condition(
    session_id: str,
    req: ConditionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Add a manual condition to a combat entity."""
    session = await get_session_or_404(session_id, db)
    await _assert_condition_edit_authority(db, session, user_id, req)
    state = session.game_state or {}

    char = None
    enemy = None
    if req.is_enemy:
        enemies = list(state.get("enemies", []) or [])
        enemy = next((item for item in enemies if str(item.get("id")) == str(req.entity_id)), None)
        if not enemy:
            raise HTTPException(404, f"Enemy {req.entity_id} not found")
        target_id = str(enemy.get("id"))
        target_name = enemy.get("name", "Enemy")
        conditions = list(enemy.get("conditions") or [])
        immune = is_condition_immune(enemy, req.condition)
        applied = not immune
        if applied:
            if req.condition not in conditions:
                conditions.append(req.condition)
            enemy["conditions"] = conditions
            if req.rounds is not None:
                durations = dict(enemy.get("condition_durations") or {})
                durations[req.condition] = req.rounds
                enemy["condition_durations"] = durations
            state["enemies"] = enemies
            session.game_state = dict(state)
            flag_modified(session, "game_state")
        target_state = _enemy_condition_target_state(enemy, target_id)
    else:
        char = await db.get(Character, req.entity_id)
        if not char:
            raise HTTPException(404, "Character not found")
        await assert_character_in_session(char, session, db)
        target_id = str(char.id)
        target_name = char.name
        conditions = list(char.conditions or [])
        immune = is_condition_immune(char, req.condition)
        applied = not immune
        if applied:
            if req.condition not in conditions:
                conditions.append(req.condition)
            char.conditions = conditions
            if req.rounds is not None:
                durations = dict(char.condition_durations or {})
                durations[req.condition] = req.rounds
                char.condition_durations = durations
            concentration_log = break_concentration_if_incapacitated(char, session_id)
            if concentration_log:
                await clear_concentration_effects_for_caster(
                    db,
                    session,
                    char.id,
                    spell_name=(concentration_log.dice_result or {}).get("spell_name"),
                )
                db.add(concentration_log)
        target_state = _character_condition_target_state(char)

    condition_result = _condition_result(
        condition=req.condition,
        action="add",
        target_id=target_id,
        target_name=target_name,
        applied=applied,
        removed=False,
        immune=immune,
    )
    dice_result = _condition_dice_result(
        condition=req.condition,
        action="add",
        condition_result=condition_result,
        target_id=target_id,
        target_name=target_name,
        target_state=target_state,
    )
    narration = _condition_narration(
        target_name,
        condition=req.condition,
        action="add",
        rounds=req.rounds,
        immune=immune,
    )

    db.add(GameLog(
        session_id=session_id,
        role="system",
        content=narration,
        log_type="system",
        dice_result=dice_result,
    ))
    combat = await _latest_combat(db, session_id)
    await db.commit()
    if combat:
        await _broadcast_condition_update(
            session=session,
            combat=combat,
            db=db,
            actor_id=target_id,
            actor_name=target_name,
            narration=narration,
            action="condition_add",
            condition=req.condition,
            condition_action="add",
            condition_result=condition_result,
            target_id=target_id,
            target_name=target_name,
            target_state=target_state,
            dice_result=dice_result,
        )

    response = _condition_response(
        entity_id=str(req.entity_id),
        conditions=conditions,
        action="condition_add",
        target_id=target_id,
        target_name=target_name,
        condition=req.condition,
        condition_action="add",
        condition_result=condition_result,
        target_state=target_state,
        dice_result=dice_result,
        narration=narration,
        applied=applied,
        removed=False,
        immune=immune,
    )
    if char is not None:
        response["concentration"] = char.concentration
    return response


@router.post("/combat/{session_id}/condition/remove", response_model=ConditionUpdateResult)
async def remove_condition(
    session_id: str,
    req: ConditionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Remove a manual condition from a combat entity."""
    session = await get_session_or_404(session_id, db)
    await _assert_condition_edit_authority(db, session, user_id, req)
    state = session.game_state or {}

    char = None
    if req.is_enemy:
        enemies = list(state.get("enemies", []) or [])
        enemy = next((item for item in enemies if str(item.get("id")) == str(req.entity_id)), None)
        if not enemy:
            raise HTTPException(404, f"Enemy {req.entity_id} not found")
        target_id = str(enemy.get("id"))
        target_name = enemy.get("name", "Enemy")
        before = list(enemy.get("conditions") or [])
        conditions = [condition for condition in before if condition != req.condition]
        removed = len(conditions) != len(before)
        enemy["conditions"] = conditions
        discard_condition_sources(enemy, req.condition)
        state["enemies"] = enemies
        session.game_state = dict(state)
        flag_modified(session, "game_state")
        target_state = _enemy_condition_target_state(enemy, target_id)
    else:
        char = await db.get(Character, req.entity_id)
        if not char:
            raise HTTPException(404, "Character not found")
        await assert_character_in_session(char, session, db)
        target_id = str(char.id)
        target_name = char.name
        before = list(char.conditions or [])
        conditions = [condition for condition in before if condition != req.condition]
        removed = len(conditions) != len(before)
        char.conditions = conditions
        discard_condition_sources(char, req.condition)
        target_state = _character_condition_target_state(char)

    condition_result = _condition_result(
        condition=req.condition,
        action="remove",
        target_id=target_id,
        target_name=target_name,
        applied=False,
        removed=removed,
        immune=False,
    )
    dice_result = _condition_dice_result(
        condition=req.condition,
        action="remove",
        condition_result=condition_result,
        target_id=target_id,
        target_name=target_name,
        target_state=target_state,
    )
    narration = _condition_narration(
        target_name,
        condition=req.condition,
        action="remove",
    )

    db.add(GameLog(
        session_id=session_id,
        role="system",
        content=narration,
        log_type="system",
        dice_result=dice_result,
    ))
    combat = await _latest_combat(db, session_id)
    await db.commit()
    if combat:
        await _broadcast_condition_update(
            session=session,
            combat=combat,
            db=db,
            actor_id=target_id,
            actor_name=target_name,
            narration=narration,
            action="condition_remove",
            condition=req.condition,
            condition_action="remove",
            condition_result=condition_result,
            target_id=target_id,
            target_name=target_name,
            target_state=target_state,
            dice_result=dice_result,
        )

    response = _condition_response(
        entity_id=str(req.entity_id),
        conditions=conditions,
        action="condition_remove",
        target_id=target_id,
        target_name=target_name,
        condition=req.condition,
        condition_action="remove",
        condition_result=condition_result,
        target_state=target_state,
        dice_result=dice_result,
        narration=narration,
        applied=False,
        removed=removed,
        immune=False,
    )
    if char is not None:
        response["concentration"] = char.concentration
    return response


async def _assert_condition_edit_authority(
    db: AsyncSession,
    session,
    user_id: str,
    req: ConditionRequest,
) -> None:
    await assert_session_access(session, user_id, db)
    if req.is_enemy:
        await _assert_ai_combat_driver(db, session, user_id)
        return
    await assert_can_act(
        session,
        user_id,
        req.entity_id,
        db,
        require_current_turn=False,
        allow_incapacitated=True,
    )


async def _latest_combat(db: AsyncSession, session_id: str) -> CombatState | None:
    result = await db.execute(
        select(CombatState)
        .where(CombatState.session_id == session_id)
        .order_by(CombatState.created_at.desc())
    )
    return result.scalars().first()


async def _broadcast_condition_update(
    *,
    session,
    combat: CombatState,
    db: AsyncSession,
    actor_id: str,
    actor_name: str,
    narration: str,
    action: str,
    condition: str,
    condition_action: str,
    condition_result: dict,
    target_id: str,
    target_name: str,
    target_state: dict,
    dice_result: dict,
) -> None:
    await _broadcast_combat(
        session,
        combat,
        CombatUpdate(
            actor_id=actor_id,
            actor_name=actor_name,
            narration=narration,
            action=action,
            target_id=target_id,
            target_name=target_name,
            target_state=target_state,
            condition=condition,
            condition_action=condition_action,
            condition_result=condition_result,
            dice_result=dice_result,
            special_action=dice_result,
        ),
        db=db,
    )


def _condition_response(
    *,
    entity_id: str,
    conditions: list[str],
    action: str,
    target_id: str,
    target_name: str,
    condition: str,
    condition_action: str,
    condition_result: dict,
    target_state: dict,
    dice_result: dict,
    narration: str,
    applied: bool,
    removed: bool,
    immune: bool,
) -> dict:
    return {
        "entity_id": entity_id,
        "conditions": conditions,
        "action": action,
        "target_id": target_id,
        "target_name": target_name,
        "condition": condition,
        "condition_action": condition_action,
        "condition_result": condition_result,
        "target_state": target_state,
        "dice_result": dice_result,
        "special_action": dice_result,
        "narration": narration,
        "applied": applied,
        "removed": removed,
        "immune": immune,
    }


def _condition_result(
    *,
    condition: str,
    action: str,
    target_id: str,
    target_name: str,
    applied: bool,
    removed: bool,
    immune: bool,
) -> dict:
    return {
        "condition": condition,
        "condition_action": action,
        "applied": applied,
        "removed": removed,
        "immune": immune,
        "target_id": target_id,
        "target_name": target_name,
    }


def _condition_dice_result(
    *,
    condition: str,
    action: str,
    condition_result: dict,
    target_id: str,
    target_name: str,
    target_state: dict,
) -> dict:
    return {
        "type": "condition_update",
        "condition": condition,
        "condition_action": action,
        "condition_result": condition_result,
        "target_id": target_id,
        "target_name": target_name,
        "target_state": target_state,
    }


def _condition_narration(
    target_name: str,
    *,
    condition: str,
    action: str,
    rounds: int | None = None,
    immune: bool = False,
) -> str:
    if immune:
        return f"{target_name} is immune to condition: {condition}."
    if action == "add":
        if rounds is not None:
            return f"{target_name} gains condition: {condition} for {rounds} round(s)."
        return f"{target_name} gains condition: {condition}."
    return f"{target_name} loses condition: {condition}."


def _character_condition_target_state(character: Character) -> dict:
    return {
        "target_id": str(character.id),
        "target_name": character.name,
        "hp_current": character.hp_current,
        "new_hp": character.hp_current,
        "hp_max": (character.derived or {}).get("hp_max"),
        "conditions": list(character.conditions or []),
        "condition_durations": dict(character.condition_durations or {}),
        "life_state": get_life_state(character),
        "concentration": character.concentration,
        "is_enemy": False,
    }


def _enemy_condition_target_state(enemy: dict, target_id: str) -> dict:
    derived = enemy.get("derived") or {}
    hp_max = enemy.get("hp_max", derived.get("hp_max"))
    return {
        "target_id": target_id,
        "target_name": enemy.get("name", "Enemy"),
        "hp_current": enemy.get("hp_current"),
        "new_hp": enemy.get("hp_current"),
        "hp_max": hp_max,
        "conditions": list(enemy.get("conditions") or []),
        "condition_durations": dict(enemy.get("condition_durations") or {}),
        "life_state": "dead" if int(enemy.get("hp_current", 0) or 0) <= 0 else "alive",
        "is_enemy": True,
    }
