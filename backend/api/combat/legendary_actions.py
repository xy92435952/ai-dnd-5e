"""Combat Legendary Action endpoints."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.combat._shared import (
    _assert_ai_combat_driver,
    _broadcast_combat,
    _build_combat_snapshot,
    _clear_active_ai_control_prompt,
    _get_ts,
    _save_ts,
)
from api.combat.ai_turn_utils import build_reaction_prompt
from api.deps import assert_session_access, entity_snapshot, get_session_or_404, get_user_id
from database import get_db
from models import Character, CombatState, GameLog
from schemas.combat_responses import CombatActionResult
from schemas.ws_events import CombatUpdate
from services.combat_condition_immunity_service import is_condition_immune, normalize_condition
from services.combat_concentration_effect_service import clear_concentration_effects_for_caster
from services.combat_concentration_service import break_concentration_if_incapacitated, do_concentration_check
from services.combat_legendary_action_service import spend_legendary_action
from services.combat_ready_spell_concentration_service import clear_ready_spell_for_lost_concentration
from services.combat_reaction_service import build_pending_attack_reaction
from services.combat_resistance_service import apply_enemy_damage_resistance
from services.combat_service import CombatService
from services.combat_temporary_hp_service import build_character_target_state
from services.dnd_rules import (
    apply_character_damage,
    get_life_state,
    get_temporary_hp,
    get_wild_shape_hp,
    roll_attack,
    roll_dice,
    roll_saving_throw,
)
from services.session_access_service import assert_character_in_session

svc = CombatService()

router = APIRouter(prefix="/game", tags=["combat"])


class LegendaryActionRequest(BaseModel):
    actor_id: str
    action_id: str | None = None
    target_id: str | None = None
    target_ids: list[str] | None = None


@router.post("/combat/{session_id}/legendary-action", response_model=CombatActionResult)
async def use_legendary_action(
    session_id: str,
    req: LegendaryActionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Resolve a non-damage Legendary Action window and spend its resource."""
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)
    await _assert_ai_combat_driver(db, session, user_id)
    if not session.combat_active:
        raise HTTPException(400, "Current session is not in combat")

    combat_result = await db.execute(
        select(CombatState)
        .where(CombatState.session_id == session_id)
        .order_by(CombatState.created_at.desc())
    )
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "Combat state not found")

    state = dict(session.game_state or {})
    enemies = list(state.get("enemies") or [])
    actor = next((enemy for enemy in enemies if str(enemy.get("id")) == str(req.actor_id)), None)
    if not actor:
        raise HTTPException(404, "Legendary Action actor not found")
    if int(actor.get("hp_current", 0) or 0) <= 0:
        raise HTTPException(400, "Defeated enemies cannot use Legendary Actions")

    spent = spend_legendary_action(actor, req.action_id)
    if not spent.get("spent"):
        raise HTTPException(400, _legendary_action_error(spent))

    action = spent["action"]
    actor_id = str(actor.get("id"))
    actor_name = str(actor.get("name") or "Enemy")
    uses = int(actor.get("legendary_action_uses", 0) or 0)
    remaining = int(actor.get("legendary_action_uses_remaining", 0) or 0)
    cost = int(spent.get("cost", 1) or 1)
    action_name = str(action.get("name") or "Legendary Action")
    description = str(action.get("description") or action.get("effect") or "").strip()
    target_ids = _legendary_action_target_ids(req, action)

    effect = await _resolve_legendary_action_effect(
        db,
        session=session,
        session_id=session_id,
        combat=combat,
        actor=actor,
        enemies=enemies,
        action=action,
        target_id=target_ids[0] if target_ids else None,
        target_ids=target_ids,
    )

    state["enemies"] = enemies
    session.game_state = state
    flag_modified(session, "game_state")
    _clear_active_ai_control_prompt(session)

    actor_state = {
        "target_id": actor_id,
        "target_name": actor_name,
        "legendary_action_uses": uses,
        "legendary_action_uses_remaining": remaining,
        "legendary_actions": actor.get("legendary_actions") or [],
    }
    target_state = effect.get("target_state") or actor_state
    narration = _build_legendary_action_narration(
        actor_name=actor_name,
        action_name=action_name,
        cost=cost,
        remaining=remaining,
        uses=uses,
        description=description,
        effect=effect,
    )

    dice_result = {
        "type": "legendary_action",
        "actor_id": actor_id,
        "actor_name": actor_name,
        "action_id": action.get("id"),
        "action_name": action_name,
        "cost": cost,
        "remaining": remaining,
        "uses": uses,
        "description": description,
        **effect.get("dice_result", {}),
    }
    if effect.get("target_id"):
        dice_result["target_id"] = effect["target_id"]
        dice_result["target_name"] = effect.get("target_name")
    db.add(GameLog(
        session_id=session_id,
        role="system",
        content=narration,
        log_type="combat",
        dice_result=dice_result,
    ))
    if effect.get("concentration_log"):
        db.add(effect["concentration_log"])
    for concentration_log in effect.get("concentration_logs") or []:
        if concentration_log and concentration_log is not effect.get("concentration_log"):
            db.add(concentration_log)
    await db.commit()
    await db.refresh(session)

    combat_snapshot = await _build_combat_snapshot(db, session, combat)
    response_fields = effect.get("response", {})
    await _broadcast_combat(
        session,
        combat,
        CombatUpdate(
            combat=combat_snapshot,
            actor_id=actor_id,
            actor_name=actor_name,
            narration=narration,
            action="legendary_action",
            legendary_action=dice_result,
            target_id=effect.get("target_id"),
            target_name=effect.get("target_name"),
            target_new_hp=effect.get("target_new_hp"),
            target_state=target_state,
            actor_state=actor_state,
            player_targeted=response_fields.get("player_targeted", False),
            player_can_react=response_fields.get("player_can_react", False),
            reaction_prompt=response_fields.get("reaction_prompt"),
            save=response_fields.get("save"),
            damage=response_fields.get("damage"),
            total_damage=response_fields.get("total_damage"),
            damage_roll=response_fields.get("damage_roll"),
            damage_type=response_fields.get("damage_type"),
            target_results=response_fields.get("target_results") or [],
            aoe_results=response_fields.get("aoe_results") or [],
            concentration_check=response_fields.get("concentration_check"),
            concentration_checks=response_fields.get("concentration_checks") or [],
            concentration_effect_updates=response_fields.get("concentration_effect_updates") or [],
            dice_result=dice_result,
            special_action=dice_result,
        ),
        db=db,
    )

    response = {
        "success": True,
        "action": "legendary_action",
        "actor_id": actor_id,
        "actor_name": actor_name,
        "target_id": effect.get("target_id"),
        "target_name": effect.get("target_name"),
        "hp_before": effect.get("hp_before"),
        "target_new_hp": effect.get("target_new_hp"),
        "narration": narration,
        "log_msg": narration,
        "dice_result": dice_result,
        "special_action": dice_result,
        "actor_state": actor_state,
        "target_state": target_state,
        "combat": combat_snapshot,
        "legendary_action": dice_result,
    }
    response.update(effect.get("response", {}))
    return response


@router.post("/combat/{session_id}/legendary-action/skip", response_model=CombatActionResult)
async def skip_legendary_action(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Persistently skip the active Legendary Action window without spending resources."""
    session = await get_session_or_404(session_id, db)
    await assert_session_access(session, user_id, db)
    await _assert_ai_combat_driver(db, session, user_id)
    if not session.combat_active:
        raise HTTPException(400, "Current session is not in combat")

    combat_result = await db.execute(
        select(CombatState)
        .where(CombatState.session_id == session_id)
        .order_by(CombatState.created_at.desc())
    )
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "Combat state not found")

    _clear_active_ai_control_prompt(session)
    await db.commit()
    await db.refresh(session)
    combat_snapshot = await _build_combat_snapshot(db, session, combat)
    await _broadcast_combat(
        session,
        combat,
        CombatUpdate(
            combat=combat_snapshot,
            action="legendary_action_skip",
            narration="Legendary Action skipped.",
            legendary_action_prompt=None,
            lair_action_prompt=None,
        ),
        db=db,
    )
    return {
        "success": True,
        "action": "legendary_action_skip",
        "narration": "Legendary Action skipped.",
        "combat": combat_snapshot,
        "legendary_action_prompt": None,
        "lair_action_prompt": None,
    }


async def _resolve_legendary_action_effect(
    db: AsyncSession,
    *,
    session,
    session_id: str,
    combat,
    actor: dict,
    enemies: list[dict],
    action: dict,
    target_id: str | None,
    target_ids: list[str] | None = None,
) -> dict:
    target_ids = _normalize_target_ids(target_ids or ([target_id] if target_id else []))
    if _is_save_legendary_action(action):
        if len(target_ids) > 1:
            return await _resolve_legendary_save_many(
                db,
                session=session,
                session_id=session_id,
                combat=combat,
                actor=actor,
                enemies=enemies,
                action=action,
                target_ids=target_ids,
            )
        if not target_ids:
            raise HTTPException(400, "Legendary Action save requires a target")
        return await _resolve_legendary_save(
            db,
            session=session,
            session_id=session_id,
            combat=combat,
            actor=actor,
            enemies=enemies,
            action=action,
            target_id=target_ids[0],
        )

    if not _is_attack_legendary_action(action):
        return {
            "dice_result": {"resolution": "utility"},
            "response": {"resolution": "utility"},
        }

    if not target_ids:
        raise HTTPException(400, "Legendary Action attack requires a target")

    return await _resolve_legendary_attack(
        db,
        session=session,
        session_id=session_id,
        combat=combat,
        actor=actor,
        enemies=enemies,
        action=action,
        target_id=target_ids[0],
    )


async def _resolve_legendary_attack(
    db: AsyncSession,
    *,
    session,
    session_id: str,
    combat,
    actor: dict,
    enemies: list[dict],
    action: dict,
    target_id: str,
) -> dict:
    target_character = await db.get(Character, target_id)
    target_enemy = None
    if target_character:
        await assert_character_in_session(target_character, session, db)
        target_snapshot = entity_snapshot(target_character, is_enemy=False)
        target_name = target_character.name
        hp_before = int(target_character.hp_current or 0)
    else:
        target_enemy = next((enemy for enemy in enemies if str(enemy.get("id")) == str(target_id)), None)
        if not target_enemy:
            raise HTTPException(404, "Legendary Action target not found")
        target_snapshot = _enemy_attack_target_snapshot(target_enemy)
        target_name = str(target_enemy.get("name") or "target")
        hp_before = int(target_enemy.get("hp_current", 0) or 0)

    if hp_before <= 0:
        raise HTTPException(400, "Legendary Action target is already defeated")

    attack_bonus = (
        _first_int(action, "attack_bonus", "to_hit", "hit_bonus", "attack_mod")
        if isinstance(action, dict)
        else None
    )
    if attack_bonus is None:
        attack_bonus = (
            _first_int(actor, "attack_bonus", "to_hit", "hit_bonus", "attack_mod")
            or _first_int(actor.get("derived") or {}, "attack_bonus")
            or 3
        )
    attacker = {
        "id": str(actor.get("id") or ""),
        "name": str(actor.get("name") or "Enemy"),
        "conditions": actor.get("conditions") or [],
        "condition_durations": actor.get("condition_durations") or {},
        "derived": {
            **(actor.get("derived") or {}),
            "attack_bonus": attack_bonus,
            "ranged_attack_bonus": attack_bonus,
        },
    }
    attack_roll = roll_attack(
        attacker,
        target_snapshot,
        is_ranged=_is_ranged_legendary_action(action),
    )
    attack_roll.update({
        "attacker_id": str(actor.get("id") or ""),
        "attacker_name": str(actor.get("name") or "Enemy"),
        "target_id": target_id,
        "target_name": target_name,
    })

    damage_dice = _first_text(action, "damage_dice", "damage") or _first_text(actor, "damage_dice") or "1d6"
    damage_type = _first_text(action, "damage_type", "type") or _first_text(actor, "damage_type") or ""
    damage_roll = None
    rolled_damage = 0
    applied_damage = 0
    target_state = None
    concentration_log = None
    concentration_effect_updates: list[dict] = []
    attack_events: list[dict] = []

    if attack_roll.get("hit"):
        damage_roll = roll_dice(damage_dice)
        rolled_damage = int(damage_roll.get("total", 0) or 0)
        if attack_roll.get("is_crit"):
            crit_expr = _critical_damage_dice(damage_dice)
            if crit_expr:
                crit_roll = roll_dice(crit_expr)
                crit_extra = int(crit_roll.get("total", 0) or 0)
                rolled_damage += crit_extra
                damage_roll = {
                    **damage_roll,
                    "total": rolled_damage,
                    "crit_extra": crit_extra,
                    "crit_extra_roll": crit_roll,
                }

        if target_character:
            applied_damage = rolled_damage
            temporary_hp_before_damage = get_temporary_hp(target_character)
            wild_shape_hp_before_damage = get_wild_shape_hp(target_character)
            class_resources_before_damage = dict(target_character.class_resources or {})
            conditions_before_damage = list(target_character.conditions or [])
            condition_durations_before_damage = dict(target_character.condition_durations or {})
            damage_result = apply_character_damage(
                target_character,
                applied_damage,
                is_critical=bool(attack_roll.get("is_crit")),
            )
            concentration_log = await do_concentration_check(target_character, applied_damage, session_id)
            if concentration_log and concentration_log.dice_result and concentration_log.dice_result.get("broke"):
                concentration_spell_name = concentration_log.dice_result.get("spell_name")
                concentration_effect_updates = await clear_concentration_effects_for_caster(
                    db,
                    session,
                    target_character.id,
                    spell_name=concentration_spell_name,
                )
                ready_spell_clear = await clear_ready_spell_for_lost_concentration(
                    db,
                    session,
                    target_character,
                    concentration_spell_name=concentration_spell_name,
                    triggered_by=actor_id,
                )
            else:
                ready_spell_clear = None
            target_state = build_character_target_state(target_character)
            target_state["target_name"] = target_name
            if concentration_effect_updates:
                target_state["concentration_effect_updates"] = concentration_effect_updates
            if ready_spell_clear:
                target_state["ready_action_failed"] = ready_spell_clear.ready_action_failed
            if target_character.is_player and applied_damage > 0:
                attack_events.append({
                    "attack_total": attack_roll.get("attack_total", 0),
                    "target_ac": attack_roll.get("target_ac", target_snapshot.get("ac", 10)),
                    "damage": applied_damage,
                    "damage_type": damage_type,
                    "hp_before": hp_before,
                    "hp_after": target_character.hp_current,
                    "temporary_hp_before": temporary_hp_before_damage,
                    "temporary_hp_after": damage_result.get("temporary_hp_after"),
                    "wild_shape_hp_before": wild_shape_hp_before_damage,
                    "wild_shape_hp_after": damage_result.get("wild_shape_hp_after"),
                    "class_resources_before": class_resources_before_damage,
                    "conditions_before": conditions_before_damage,
                    "condition_durations_before": condition_durations_before_damage,
                    "hit": True,
                })
        elif target_enemy:
            applied_damage, _resistance_applied = apply_enemy_damage_resistance(
                target_enemy,
                rolled_damage,
                damage_type,
            )
            target_enemy["hp_current"] = svc.apply_damage(
                int(target_enemy.get("hp_current", 0) or 0),
                applied_damage,
                int((target_enemy.get("derived") or {}).get("hp_max", target_enemy.get("hp_max", 10)) or 10),
            )
            target_state = _enemy_target_state(target_enemy)

    player_targeted = bool(target_character and target_character.is_player)
    player_can_react = False
    reaction_prompt = None
    if player_targeted and target_character:
        player_ts = _get_ts(combat, target_character.id)
        pending_reaction = build_pending_attack_reaction(
            attacker_id=str(actor.get("id") or ""),
            attacker_name=str(actor.get("name") or "Enemy"),
            target_id=target_character.id,
            attack_events=attack_events,
        )
        if pending_reaction:
            player_ts["pending_attack_reaction"] = pending_reaction
            _save_ts(combat, target_character.id, player_ts)
            player_can_react, has_prompt, reaction_prompt = build_reaction_prompt(
                target_character,
                player_ts,
                target_id,
                str(actor.get("name") or "Enemy"),
                str(actor.get("id") or ""),
                applied_damage if attack_roll.get("hit") else 0,
                SimpleNamespace(attack_roll=attack_roll),
            )
            if not has_prompt:
                reaction_prompt = None

    dice_result = {
        "resolution": "attack",
        "target_id": target_id,
        "target_name": target_name,
        "attack": attack_roll,
        "damage": rolled_damage if attack_roll.get("hit") else 0,
        "total_damage": applied_damage if attack_roll.get("hit") else 0,
        "damage_roll": damage_roll,
        "damage_dice": damage_dice,
        "damage_type": damage_type,
    }
    response = {
        "resolution": "attack",
        "hit": bool(attack_roll.get("hit")),
        "is_crit": bool(attack_roll.get("is_crit")),
        "damage": applied_damage if attack_roll.get("hit") else 0,
        "total_damage": applied_damage if attack_roll.get("hit") else 0,
        "damage_roll": damage_roll,
        "damage_dice": damage_dice,
        "damage_type": damage_type,
        "attack": attack_roll,
        "player_targeted": player_targeted,
        "player_can_react": player_can_react,
        "reaction_prompt": reaction_prompt,
    }
    if target_state:
        response["target_state"] = target_state
    if concentration_log and concentration_log.dice_result:
        response["concentration_check"] = concentration_log.dice_result
    if concentration_effect_updates:
        response["concentration_effect_updates"] = concentration_effect_updates
    return {
        "target_id": target_id,
        "target_name": target_name,
        "hp_before": hp_before,
        "target_new_hp": target_state.get("hp_current") if target_state else None,
        "target_state": target_state,
        "concentration_log": concentration_log,
        "dice_result": dice_result,
        "response": response,
    }


async def _resolve_legendary_save(
    db: AsyncSession,
    *,
    session,
    session_id: str,
    combat,
    actor: dict,
    enemies: list[dict],
    action: dict,
    target_id: str,
) -> dict:
    save_rule = _legendary_save_rule(action)
    damage_dice = _first_text(action, "damage_dice", "damage") or _first_text(actor, "damage_dice") or ""
    damage_type = _first_text(action, "damage_type", "type") or _first_text(actor, "damage_type") or ""
    half_on_save = _half_on_save(action)
    damage_roll = roll_dice(damage_dice) if damage_dice else None
    rolled_damage = int(damage_roll.get("total", 0) or 0) if damage_roll else 0

    return await _resolve_legendary_save_target(
        db,
        session=session,
        session_id=session_id,
        combat=combat,
        actor_id=str(actor.get("id") or ""),
        enemies=enemies,
        action=action,
        target_id=target_id,
        save_ability=save_rule["save_ability"],
        save_dc=save_rule["save_dc"],
        damage_dice=damage_dice,
        damage_type=damage_type,
        half_on_save=half_on_save,
        damage_roll=damage_roll,
        rolled_damage=rolled_damage,
    )


async def _resolve_legendary_save_many(
    db: AsyncSession,
    *,
    session,
    session_id: str,
    combat,
    actor: dict,
    enemies: list[dict],
    action: dict,
    target_ids: list[str],
) -> dict:
    target_ids = _normalize_target_ids(target_ids)
    if len(target_ids) < 2:
        return await _resolve_legendary_save(
            db,
            session=session,
            session_id=session_id,
            combat=combat,
            actor=actor,
            enemies=enemies,
            action=action,
            target_id=target_ids[0] if target_ids else "",
        )

    save_rule = _legendary_save_rule(action)
    damage_dice = _first_text(action, "damage_dice", "damage") or _first_text(actor, "damage_dice") or ""
    damage_type = _first_text(action, "damage_type", "type") or _first_text(actor, "damage_type") or ""
    half_on_save = _half_on_save(action)
    damage_roll = roll_dice(damage_dice) if damage_dice else None
    rolled_damage = int(damage_roll.get("total", 0) or 0) if damage_roll else 0

    target_results: list[dict[str, Any]] = []
    concentration_logs = []
    concentration_checks: list[dict[str, Any]] = []
    for item_target_id in target_ids:
        effect = await _resolve_legendary_save_target(
            db,
            session=session,
            session_id=session_id,
            combat=combat,
            actor_id=str(actor.get("id") or ""),
            enemies=enemies,
            action=action,
            target_id=item_target_id,
            save_ability=save_rule["save_ability"],
            save_dc=save_rule["save_dc"],
            damage_dice=damage_dice,
            damage_type=damage_type,
            half_on_save=half_on_save,
            damage_roll=damage_roll,
            rolled_damage=rolled_damage,
        )
        target_results.append(_legendary_target_result(effect))
        if effect.get("concentration_log"):
            concentration_logs.append(effect["concentration_log"])
        check = effect.get("response", {}).get("concentration_check")
        if isinstance(check, dict):
            concentration_checks.append(check)

    if not target_results:
        raise HTTPException(404, "Legendary Action targets not found")

    primary = target_results[0]
    total_damage = sum(int(result.get("total_damage", result.get("damage", 0)) or 0) for result in target_results)
    failed = sum(1 for result in target_results if not (result.get("save") or {}).get("success"))
    saved_count = len(target_results) - failed
    concentration_check = next(
        (check for check in concentration_checks if check.get("broke")),
        concentration_checks[0] if concentration_checks else None,
    )

    dice_result = {
        "resolution": "save",
        "target_id": primary.get("target_id"),
        "target_name": primary.get("target_name"),
        "target_results": target_results,
        "aoe": target_results,
        "targets": target_results,
        "target_count": len(target_results),
        "save_failed_count": failed,
        "save_succeeded_count": saved_count,
        "save_success": failed == 0,
        "base_damage": rolled_damage,
        "damage": total_damage,
        "total_damage": total_damage,
        "damage_roll": damage_roll,
        "damage_dice": damage_dice,
        "damage_type": damage_type,
        "half_on_save": half_on_save,
    }
    response = {
        "resolution": "save",
        "target_results": target_results,
        "aoe_results": target_results,
        "target_count": len(target_results),
        "save_failed_count": failed,
        "save_succeeded_count": saved_count,
        "save_success": failed == 0,
        "base_damage": rolled_damage,
        "damage": total_damage,
        "total_damage": total_damage,
        "damage_roll": damage_roll,
        "damage_dice": damage_dice,
        "damage_type": damage_type,
        "half_on_save": half_on_save,
    }
    if concentration_check:
        response["concentration_check"] = concentration_check
    if concentration_checks:
        response["concentration_checks"] = concentration_checks
    return {
        "target_id": primary.get("target_id"),
        "target_name": primary.get("target_name"),
        "hp_before": primary.get("hp_before"),
        "target_new_hp": primary.get("hp_current"),
        "target_state": primary.get("target_state") or primary,
        "concentration_log": concentration_logs[0] if concentration_logs else None,
        "concentration_logs": concentration_logs,
        "dice_result": dice_result,
        "response": response,
    }


async def _resolve_legendary_save_target(
    db: AsyncSession,
    *,
    session,
    session_id: str,
    combat,
    actor_id: str,
    enemies: list[dict],
    action: dict,
    target_id: str,
    save_ability: str,
    save_dc: int,
    damage_dice: str,
    damage_type: str,
    half_on_save: bool,
    damage_roll: dict | None,
    rolled_damage: int,
) -> dict:
    target_character = await db.get(Character, target_id)
    target_enemy = None
    if target_character:
        await assert_character_in_session(target_character, session, db)
        target_snapshot = entity_snapshot(target_character, is_enemy=False)
        target_name = target_character.name
        hp_before = int(target_character.hp_current or 0)
    else:
        target_enemy = next((enemy for enemy in enemies if str(enemy.get("id")) == str(target_id)), None)
        if not target_enemy:
            raise HTTPException(404, "Legendary Action target not found")
        target_snapshot = _enemy_attack_target_snapshot(target_enemy)
        target_name = str(target_enemy.get("name") or "target")
        hp_before = int(target_enemy.get("hp_current", 0) or 0)

    if hp_before <= 0:
        raise HTTPException(400, "Legendary Action target is already defeated")

    save_detail = roll_saving_throw(target_snapshot, save_ability, save_dc)
    saved = bool(save_detail.get("success"))
    damage_after_save = rolled_damage // 2 if saved and half_on_save else (0 if saved else rolled_damage)
    applied_damage = 0
    target_state = None
    concentration_log = None
    concentration_effect_updates: list[dict] = []
    condition_result = None
    forced_movement = None

    if damage_after_save > 0:
        if target_character:
            applied_damage = damage_after_save
            apply_character_damage(target_character, applied_damage)
            concentration_log = await do_concentration_check(target_character, applied_damage, session_id)
            if concentration_log and concentration_log.dice_result and concentration_log.dice_result.get("broke"):
                concentration_spell_name = concentration_log.dice_result.get("spell_name")
                concentration_effect_updates = await clear_concentration_effects_for_caster(
                    db,
                    session,
                    target_character.id,
                    spell_name=concentration_spell_name,
                )
                ready_spell_clear = await clear_ready_spell_for_lost_concentration(
                    db,
                    session,
                    target_character,
                    concentration_spell_name=concentration_spell_name,
                    triggered_by=actor_id,
                )
            else:
                ready_spell_clear = None
            target_state = build_character_target_state(target_character)
            target_state["target_name"] = target_name
            target_state["is_enemy"] = False
            target_state["is_player"] = bool(getattr(target_character, "is_player", False))
            target_state["is_companion"] = not bool(getattr(target_character, "is_player", False))
            if concentration_effect_updates:
                target_state["concentration_effect_updates"] = concentration_effect_updates
            if ready_spell_clear:
                target_state["ready_action_failed"] = ready_spell_clear.ready_action_failed
        elif target_enemy:
            applied_damage, _resistance_applied = apply_enemy_damage_resistance(
                target_enemy,
                damage_after_save,
                damage_type,
            )
            target_enemy["hp_current"] = svc.apply_damage(
                int(target_enemy.get("hp_current", 0) or 0),
                applied_damage,
                int((target_enemy.get("derived") or {}).get("hp_max", target_enemy.get("hp_max", 10)) or 10),
            )
            target_state = _enemy_target_state(target_enemy)
    elif target_character:
        target_state = build_character_target_state(target_character)
        target_state["target_name"] = target_name
        target_state["is_enemy"] = False
        target_state["is_player"] = bool(getattr(target_character, "is_player", False))
        target_state["is_companion"] = not bool(getattr(target_character, "is_player", False))
    elif target_enemy:
        target_state = _enemy_target_state(target_enemy)

    if target_character or target_enemy:
        condition_result = await _apply_legendary_condition_to_target(
            db,
            session=session,
            session_id=session_id,
            target=target_character or target_enemy,
            action=action,
            save_detail=save_detail,
        )
        if condition_result:
            condition_concentration_log = condition_result.pop("_concentration_log", None)
            if condition_concentration_log:
                concentration_log = condition_concentration_log
            if condition_result.get("concentration_effect_updates"):
                concentration_effect_updates = condition_result["concentration_effect_updates"]
            if target_character:
                target_state = build_character_target_state(target_character)
                target_state["target_name"] = target_name
                target_state["is_enemy"] = False
                target_state["is_player"] = bool(getattr(target_character, "is_player", False))
                target_state["is_companion"] = not bool(getattr(target_character, "is_player", False))
                if concentration_effect_updates:
                    target_state["concentration_effect_updates"] = concentration_effect_updates
                if condition_result.get("ready_action_failed"):
                    target_state["ready_action_failed"] = condition_result["ready_action_failed"]
            elif target_enemy:
                target_state = _enemy_target_state(target_enemy)

    forced_movement = _apply_legendary_forced_movement(
        combat=combat,
        actor_id=actor_id,
        target_id=target_id,
        target_name=target_name,
        action=action,
        save_detail=save_detail,
    )

    save_detail = {
        **save_detail,
        "target_id": target_id,
        "target_name": target_name,
    }
    if target_state is not None:
        target_state["save"] = save_detail

    dice_result = {
        "resolution": "save",
        "target_id": target_id,
        "target_name": target_name,
        "save": save_detail,
        "save_success": saved,
        "damage": rolled_damage,
        "damage_after_save": damage_after_save,
        "total_damage": applied_damage,
        "damage_roll": damage_roll,
        "damage_dice": damage_dice,
        "damage_type": damage_type,
        "half_on_save": half_on_save,
    }
    if condition_result:
        dice_result["condition_result"] = condition_result
    if forced_movement:
        dice_result["forced_movement"] = forced_movement
    if target_state:
        dice_result["target_state"] = target_state
    response = {
        "resolution": "save",
        "save": save_detail,
        "save_success": saved,
        "damage": applied_damage,
        "damage_after_save": damage_after_save,
        "total_damage": applied_damage,
        "damage_roll": damage_roll,
        "damage_dice": damage_dice,
        "damage_type": damage_type,
        "half_on_save": half_on_save,
    }
    if condition_result:
        response["condition_result"] = condition_result
    if forced_movement:
        response["forced_movement"] = forced_movement
    if target_state:
        response["target_state"] = target_state
    if concentration_log and concentration_log.dice_result:
        response["concentration_check"] = concentration_log.dice_result
    if concentration_effect_updates:
        response["concentration_effect_updates"] = concentration_effect_updates
    return {
        "target_id": target_id,
        "target_name": target_name,
        "hp_before": hp_before,
        "target_new_hp": target_state.get("hp_current") if target_state else None,
        "target_state": target_state,
        "concentration_log": concentration_log,
        "dice_result": dice_result,
        "response": response,
    }


def _legendary_save_rule(action: dict) -> dict[str, Any]:
    save_ability = _first_text(action, "saving_throw", "save", "save_ability", "saving_throw_ability")
    save_dc = _first_int(action, "save_dc", "dc", "saving_throw_dc")
    if not save_ability or save_dc is None:
        raise HTTPException(400, "Legendary Action save requires save ability and DC")
    return {"save_ability": save_ability, "save_dc": save_dc}


async def _apply_legendary_condition_to_target(
    db: AsyncSession,
    *,
    session,
    session_id: str,
    target: dict[str, Any] | Character,
    action: dict[str, Any],
    save_detail: dict[str, Any] | None,
) -> dict[str, Any] | None:
    condition = _legendary_condition(action)
    if not condition:
        return None

    save_succeeded = bool(save_detail and save_detail.get("success"))
    if save_succeeded:
        return {
            "condition": condition,
            "applied": False,
            "immune": False,
            "reason": "save_success",
        }

    if is_condition_immune(target, condition):
        return {
            "condition": condition,
            "applied": False,
            "immune": True,
            "reason": "condition_immunity",
        }

    duration_rounds = _legendary_condition_duration(action)
    if isinstance(target, dict):
        conditions = list(target.get("conditions", []) or [])
        if condition not in conditions:
            conditions.append(condition)
        target["conditions"] = conditions
        if duration_rounds is not None:
            durations = dict(target.get("condition_durations", {}) or {})
            durations[condition] = duration_rounds
            target["condition_durations"] = durations
        return {
            "condition": condition,
            "applied": True,
            "immune": False,
            "duration_rounds": duration_rounds,
        }

    conditions = list(target.conditions or [])
    if condition not in conditions:
        conditions.append(condition)
    target.conditions = conditions
    if duration_rounds is not None:
        durations = dict(target.condition_durations or {})
        durations[condition] = duration_rounds
        target.condition_durations = durations

    concentration_log = break_concentration_if_incapacitated(target, session_id)
    concentration_effect_updates = []
    ready_spell_clear = None
    if concentration_log:
        concentration_spell_name = (concentration_log.dice_result or {}).get("spell_name")
        concentration_effect_updates = await clear_concentration_effects_for_caster(
            db,
            session,
            target.id,
            spell_name=concentration_spell_name,
        )
        ready_spell_clear = await clear_ready_spell_for_lost_concentration(
            db,
            session,
            target,
            concentration_spell_name=concentration_spell_name,
            reason="concentration_lost",
        )

    return {
        "condition": condition,
        "applied": True,
        "immune": False,
        "duration_rounds": duration_rounds,
        "concentration_broken": bool(concentration_log),
        "concentration_check": concentration_log.dice_result if concentration_log else None,
        "concentration_effect_updates": concentration_effect_updates,
        "ready_action_failed": ready_spell_clear.ready_action_failed if ready_spell_clear else None,
        "_concentration_log": concentration_log,
    }


def _legendary_condition(action: dict[str, Any]) -> str | None:
    conditions = _legendary_conditions(action)
    return conditions[0] if conditions else None


def _legendary_conditions(action: dict[str, Any]) -> list[str]:
    conditions: list[str] = []
    for key in ("condition_on_failed_save", "condition_name", "condition"):
        condition = normalize_condition(action.get(key))
        if condition:
            conditions.append(condition)
    values = action.get("conditions_on_failed_save") or action.get("conditionsOnFailedSave")
    if isinstance(values, list):
        for value in values:
            condition = normalize_condition(value)
            if condition:
                conditions.append(condition)
    return list(dict.fromkeys(conditions))


def _legendary_condition_duration(action: dict[str, Any]) -> int | None:
    for key in (
        "condition_duration_rounds",
        "conditionDurationRounds",
        "duration_rounds",
        "durationRounds",
        "condition_duration",
        "conditionDuration",
    ):
        value = action.get(key)
        if value is None:
            continue
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            continue
    return None


def _legendary_push_tiles(action: dict[str, Any]) -> int:
    return _legendary_movement_tiles(
        action,
        feet_keys=("push_distance_ft", "pushDistanceFt", "push_ft", "pushFeet", "knockback_ft"),
        tile_keys=("push_tiles", "pushTiles"),
        distance_key="push_distance",
    )


def _legendary_pull_tiles(action: dict[str, Any]) -> int:
    return _legendary_movement_tiles(
        action,
        feet_keys=("pull_distance_ft", "pullDistanceFt", "pull_ft", "pullFeet"),
        tile_keys=("pull_tiles", "pullTiles"),
        distance_key="pull_distance",
    )


def _legendary_movement_tiles(
    action: dict[str, Any],
    *,
    feet_keys: tuple[str, ...],
    tile_keys: tuple[str, ...],
    distance_key: str,
) -> int:
    forced = action.get("forced_movement") if isinstance(action.get("forced_movement"), dict) else {}

    for key in feet_keys:
        value = action.get(key, forced.get(key))
        if value is None:
            continue
        try:
            return max(1, int(value) // 5)
        except (TypeError, ValueError):
            continue

    for key in tile_keys:
        value = action.get(key, forced.get(key))
        if value is None:
            continue
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            continue

    value = action.get(distance_key, forced.get(distance_key))
    if value is None:
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(1, number // 5) if number > 4 else max(1, number)


def _apply_legendary_forced_movement(
    *,
    combat,
    actor_id: str,
    target_id: str,
    target_name: str,
    action: dict[str, Any],
    save_detail: dict[str, Any] | None,
) -> dict[str, Any] | None:
    movement_type = "push"
    movement_tiles = _legendary_push_tiles(action)
    if movement_tiles <= 0:
        movement_type = "pull"
        movement_tiles = _legendary_pull_tiles(action)
    if movement_tiles <= 0:
        return None

    if save_detail and save_detail.get("success"):
        return {
            "type": movement_type,
            "applied": False,
            "reason": "save_success",
            "target_id": str(target_id),
            "target_name": target_name,
            "distance_ft": movement_tiles * 5,
            "steps": 0,
        }

    positions = dict(getattr(combat, "entity_positions", None) or {})
    actor_position = positions.get(str(actor_id))
    target_position = positions.get(str(target_id))
    if not actor_position or not target_position:
        return {
            "type": movement_type,
            "applied": False,
            "reason": "missing_position",
            "target_id": str(target_id),
            "target_name": target_name,
            "distance_ft": movement_tiles * 5,
            "steps": 0,
        }

    if movement_type == "pull":
        dx = int(actor_position.get("x", 0)) - int(target_position.get("x", 0))
        dy = int(actor_position.get("y", 0)) - int(target_position.get("y", 0))
    else:
        dx = int(target_position.get("x", 0)) - int(actor_position.get("x", 0))
        dy = int(target_position.get("y", 0)) - int(actor_position.get("y", 0))
    step_x = _sign(dx)
    step_y = _sign(dy)
    if step_x == 0 and step_y == 0:
        return {
            "type": movement_type,
            "applied": False,
            "reason": "same_position",
            "target_id": str(target_id),
            "target_name": target_name,
            "distance_ft": movement_tiles * 5,
            "steps": 0,
        }

    width, height = _combat_grid_dimensions(combat)
    occupied = {
        (int(position.get("x", -999)), int(position.get("y", -999)))
        for entity_id, position in positions.items()
        if str(entity_id) != str(target_id) and isinstance(position, dict)
    }
    grid_data = getattr(combat, "grid_data", None) or {}

    current = {"x": int(target_position.get("x", 0)), "y": int(target_position.get("y", 0))}
    steps = 0
    blocked_reason = ""
    for _ in range(movement_tiles):
        candidate = {"x": current["x"] + step_x, "y": current["y"] + step_y}
        if not (0 <= candidate["x"] < width and 0 <= candidate["y"] < height):
            blocked_reason = "out_of_bounds"
            break
        if (candidate["x"], candidate["y"]) in occupied:
            blocked_reason = "occupied"
            break
        if _is_forced_movement_blocked(grid_data, candidate):
            blocked_reason = "blocked_terrain"
            break
        current = candidate
        steps += 1

    result = {
        "type": movement_type,
        "applied": steps > 0,
        "target_id": str(target_id),
        "target_name": target_name,
        "distance_ft": steps * 5,
        "requested_distance_ft": movement_tiles * 5,
        "steps": steps,
        "from": {"x": int(target_position.get("x", 0)), "y": int(target_position.get("y", 0))},
        "to": dict(current),
    }
    if blocked_reason:
        result["blocked_reason"] = blocked_reason

    if steps > 0:
        positions[str(target_id)] = dict(current)
        combat.entity_positions = positions
        flag_modified(combat, "entity_positions")

    return result


def _combat_grid_dimensions(combat) -> tuple[int, int]:
    grid_data = getattr(combat, "grid_data", None) or {}
    try:
        width = int(grid_data.get("width") or 20)
        height = int(grid_data.get("height") or 12)
    except (TypeError, ValueError):
        return 20, 12
    return max(1, width), max(1, height)


def _is_forced_movement_blocked(grid_data: dict[str, Any], position: dict[str, int]) -> bool:
    cell = grid_data.get(f"{position['x']}_{position['y']}")
    if isinstance(cell, str):
        terrain = cell.lower()
    elif isinstance(cell, dict):
        terrain = str(cell.get("terrain") or cell.get("type") or "").lower()
    else:
        terrain = ""
    return terrain in {"wall", "total_cover", "blocked", "impassable"}


def _sign(value: int) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _legendary_target_result(effect: dict) -> dict[str, Any]:
    target_state = dict(effect.get("target_state") or {})
    response = effect.get("response") or {}
    result = {
        **target_state,
        "target_id": effect.get("target_id") or target_state.get("target_id"),
        "target_name": effect.get("target_name") or target_state.get("target_name"),
        "hp_before": effect.get("hp_before"),
        "target_new_hp": effect.get("target_new_hp"),
        "damage": response.get("total_damage", response.get("damage", 0)),
        "base_damage": response.get("damage"),
        "damage_after_save": response.get("damage_after_save"),
        "total_damage": response.get("total_damage", response.get("damage", 0)),
        "damage_type": response.get("damage_type"),
        "save": response.get("save") or target_state.get("save"),
        "condition_result": response.get("condition_result"),
        "forced_movement": response.get("forced_movement"),
        "target_state": target_state,
    }
    if response.get("concentration_check"):
        result["concentration_check"] = response["concentration_check"]
    if response.get("concentration_effect_updates"):
        result["concentration_effect_updates"] = response["concentration_effect_updates"]
    return result


def _build_legendary_action_narration(
    *,
    actor_name: str,
    action_name: str,
    cost: int,
    remaining: int,
    uses: int,
    description: str,
    effect: dict,
) -> str:
    base = (
        f"{actor_name} uses Legendary Action: {action_name} "
        f"(cost {cost}, remaining {remaining}/{uses})."
    )
    resolution = effect.get("response", {}).get("resolution")
    if resolution == "save":
        target_results = effect.get("response", {}).get("target_results") or []
        if len(target_results) > 1:
            failed = int(effect.get("response", {}).get("save_failed_count", 0) or 0)
            saved = int(effect.get("response", {}).get("save_succeeded_count", 0) or 0)
            damage = effect.get("response", {}).get("total_damage", 0)
            damage_type = effect.get("response", {}).get("damage_type") or "damage"
            names = _target_summary(target_results)
            conditions = sorted({
                str((result.get("condition_result") or {}).get("condition"))
                for result in target_results
                if (result.get("condition_result") or {}).get("applied")
            })
            condition_text = f" Conditions applied: {', '.join(conditions)}." if conditions else ""
            movements = [
                result.get("forced_movement") or {}
                for result in target_results
                if (result.get("forced_movement") or {}).get("applied")
            ]
            pushes = [movement for movement in movements if movement.get("type") != "pull"]
            pulls = [movement for movement in movements if movement.get("type") == "pull"]
            movement_text = ""
            if pushes:
                movement_text += f" {len(pushes)} target{'s' if len(pushes) != 1 else ''} pushed."
            if pulls:
                movement_text += f" {len(pulls)} target{'s' if len(pulls) != 1 else ''} pulled."
            return (
                f"{base} {len(target_results)} targets affected ({failed} failed, "
                f"{saved} succeeded saves): {names}. Total damage {damage} {damage_type}.{condition_text}{movement_text}"
            )
        save = effect.get("response", {}).get("save") or {}
        target_name = effect.get("target_name") or "target"
        outcome = "succeeds" if save.get("success") else "fails"
        damage = effect.get("response", {}).get("total_damage", 0)
        damage_type = effect.get("response", {}).get("damage_type") or "damage"
        condition_result = effect.get("response", {}).get("condition_result") or {}
        movement_sentence = _legendary_forced_movement_sentence(
            effect.get("response", {}).get("forced_movement"),
            target_name=target_name,
        )
        if condition_result.get("applied"):
            return (
                f"{base} {target_name} {outcome} the {save.get('ability', 'save')} save "
                f"(DC{save.get('dc')}, total {save.get('total')}) and is affected by "
                f"{condition_result.get('condition')}.{movement_sentence}"
            )
        if condition_result.get("immune"):
            return (
                f"{base} {target_name} {outcome} the {save.get('ability', 'save')} save "
                f"(DC{save.get('dc')}, total {save.get('total')}) but is immune to "
                f"{condition_result.get('condition')}.{movement_sentence}"
            )
        if movement_sentence and damage <= 0:
            return (
                f"{base} {target_name} {outcome} the {save.get('ability', 'save')} save "
                f"(DC{save.get('dc')}, total {save.get('total')}).{movement_sentence}"
            )
        return (
            f"{base} {target_name} {outcome} the {save.get('ability', 'save')} save "
            f"(DC{save.get('dc')}, total {save.get('total')}) and takes {damage} {damage_type} damage."
            f"{movement_sentence}"
        )
    if resolution != "attack":
        return f"{base} {description}".strip()

    attack = effect.get("response", {}).get("attack") or {}
    target_name = effect.get("target_name") or "target"
    compare = f"{attack.get('attack_total')} vs AC{attack.get('target_ac')}"
    if attack.get("hit"):
        damage = effect.get("response", {}).get("total_damage", 0)
        damage_type = effect.get("response", {}).get("damage_type") or "damage"
        crit = " critically" if attack.get("is_crit") else ""
        return f"{base} {actor_name}{crit} hits {target_name} ({compare}) for {damage} {damage_type} damage."
    return f"{base} {actor_name} misses {target_name} ({compare})."


def _legendary_forced_movement_sentence(movement: dict[str, Any] | None, *, target_name: str) -> str:
    if not movement or not isinstance(movement, dict):
        return ""
    if movement.get("applied"):
        verb = "pulled" if movement.get("type") == "pull" else "pushed"
        distance = movement.get("distance_ft") or movement.get("requested_distance_ft")
        distance_text = f" {distance} ft" if distance else ""
        return f" {target_name} is {verb}{distance_text}."
    if movement.get("blocked_reason"):
        return f" {target_name}'s forced movement is blocked."
    return ""


def _enemy_attack_target_snapshot(enemy: dict) -> dict:
    derived = enemy.get("derived") or {}
    hp_max = derived.get("hp_max", enemy.get("hp_max", 10))
    ac = derived.get("ac", enemy.get("ac", 10))
    return {
        "id": str(enemy.get("id") or ""),
        "name": enemy.get("name") or "Enemy",
        "hp_current": enemy.get("hp_current", 0),
        "conditions": enemy.get("conditions") or [],
        "condition_durations": enemy.get("condition_durations") or {},
        "derived": {**derived, "hp_max": hp_max, "ac": ac},
    }


def _enemy_target_state(enemy: dict) -> dict:
    return {
        "target_id": str(enemy.get("id") or ""),
        "target_name": enemy.get("name") or "Enemy",
        "hp_current": enemy.get("hp_current", 0),
        "new_hp": enemy.get("hp_current", 0),
        "conditions": enemy.get("conditions") or [],
        "condition_durations": enemy.get("condition_durations") or {},
        "life_state": "dead" if int(enemy.get("hp_current", 0) or 0) <= 0 else "alive",
        "is_enemy": True,
    }


def _legendary_action_target_ids(req: LegendaryActionRequest, action: dict[str, Any]) -> list[str]:
    requested = _normalize_target_ids(req.target_ids)
    if requested:
        return requested
    if req.target_id:
        return _normalize_target_ids([req.target_id])
    for key in ("target_ids", "targetIds"):
        values = _normalize_target_ids(action.get(key))
        if values:
            return values
    if isinstance(action.get("targets"), (list, tuple, set)):
        values = _normalize_target_ids(action.get("targets"))
        if values:
            return values
    action_target_id = action.get("target_id") or action.get("targetId")
    if action_target_id:
        return _normalize_target_ids([action_target_id])
    return []


def _normalize_target_ids(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, (list, tuple, set)) else [value]
    seen: set[str] = set()
    target_ids: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        target_ids.append(text)
    return target_ids


def _target_summary(target_results: list[dict[str, Any]]) -> str:
    names = [
        str(result.get("target_name") or result.get("target_id") or "target")
        for result in target_results
    ]
    if len(names) <= 3:
        return ", ".join(names)
    return f"{', '.join(names[:3])}, and {len(names) - 3} more"


def _is_attack_legendary_action(action: dict) -> bool:
    if _is_save_legendary_action(action):
        return False
    action_type = str(action.get("resolution") or action.get("kind") or action.get("type") or "").lower()
    if action_type == "attack":
        return True
    return any(key in action for key in ("attack_bonus", "to_hit", "hit_bonus", "attack_mod"))


def _is_save_legendary_action(action: dict) -> bool:
    action_type = str(action.get("resolution") or action.get("kind") or action.get("type") or "").lower()
    if action_type in {"save", "saving_throw", "saving throw"}:
        return True
    has_save_dc = any(key in action for key in ("save_dc", "dc", "saving_throw_dc"))
    has_save_ability = any(key in action for key in ("saving_throw", "save", "save_ability", "saving_throw_ability"))
    return has_save_dc and has_save_ability


def _half_on_save(action: dict) -> bool:
    if "half_on_save" in action:
        return bool(action.get("half_on_save"))
    text = " ".join(str(action.get(key) or "") for key in ("description", "effect", "name")).lower()
    return "half" in text or "save for half" in text or "successful save" in text


def _is_ranged_legendary_action(action: dict) -> bool:
    text = " ".join(str(action.get(key) or "") for key in ("range", "targeting", "description", "name")).lower()
    return any(token in text for token in ("ranged", "range", "射程", "远程"))


def _critical_damage_dice(damage_dice: str) -> str:
    import re

    text = str(damage_dice or "").strip().lower().replace(" ", "")
    terms = []
    for match in re.finditer(r"([+-]?)(\d*)d(\d+)", text):
        sign = "-" if match.group(1) == "-" else ""
        count = match.group(2) or "1"
        sides = match.group(3)
        terms.append(f"{sign}{count}d{sides}")
    if not terms:
        return ""
    expr = terms[0]
    for term in terms[1:]:
        expr += term if term.startswith("-") else f"+{term}"
    return expr


def _first_text(source: dict, *keys: str) -> str:
    for key in keys:
        value = source.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _first_int(source: dict, *keys: str) -> int | None:
    import re

    for key in keys:
        value = source.get(key)
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, (int, float)):
            return int(value)
        digits = re.findall(r"-?\d+", str(value))
        if digits:
            return int(digits[0])
    return None


def _legendary_action_error(result: dict) -> str:
    reason = result.get("reason")
    if reason == "no_legendary_actions":
        return "This enemy has no Legendary Actions"
    if reason == "unknown_action":
        return "Unknown Legendary Action"
    if reason == "insufficient_uses":
        return "Not enough Legendary Action uses remaining"
    return "Legendary Action could not be used"
