from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm.attributes import flag_modified

from models import Character, GameLog
from services.combat_attack_damage_service import apply_attack_damage_to_target
from services.combat_attack_roll_service import CombatAttackRollError
from services.combat_attack_targeting_service import get_target_conditions, resolve_attack_target
from services.combat_ai_spell_service import resolve_ai_spell_action
from services.combat_direct_attack_service import (
    consume_direct_attack_turn,
    prepare_direct_attack,
)
from services.combat_direct_spell_service import CombatDirectSpellError, cast_direct_spell
from services.combat_hazard_service import apply_movement_hazard, hazard_result_to_log_text
from services.combat_movement_rules_service import MovementRuleError, validate_displacement_allowed
from services.combat_outcome_service import check_and_cleanup_combat_outcome
from services.combat_spell_confirm_service import confirm_pending_spell
from services.combat_spell_prepare_service import prepare_spell_roll
from services.combat_spell_resolution_service import CombatSpellResolutionError
from services.combat_spell_roll_service import CombatSpellRollError, spell_action_cost, spell_requires_attack_roll
from services.combat_ready_spell_concentration_service import (
    READY_SPELL_CONCENTRATION_PREFIX,
    build_ready_spell_actor_state,
    build_ready_spell_concentration_name,
    clear_expired_ready_spell_concentration_hold,
    clear_ready_spell_concentration_hold,
    is_ready_spell_concentration,
    ready_spell_concentration_matches,
    ready_spell_name_from_concentration,
    set_ready_spell_concentration_hold,
)
from services.combat_turn_state_service import DEFAULT_TURN_STATE, get_turn_state, save_turn_state
from services.combat_action_rules_service import can_take_reaction
from services.spell_service import spell_service


READY_TRIGGER_TARGET_MOVES = "target_moves"
READY_TRIGGER_MATCH_ANY = "any_movement"
READY_TRIGGER_MATCH_ENTERS_REACH = "enters_reach"
READY_TRIGGER_MATCH_LEAVES_REACH = "leaves_reach"
READY_TRIGGER_MATCHES = {
    READY_TRIGGER_MATCH_ANY,
    READY_TRIGGER_MATCH_ENTERS_REACH,
    READY_TRIGGER_MATCH_LEAVES_REACH,
}


def normalize_ready_trigger_match(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    return raw if raw in READY_TRIGGER_MATCHES else READY_TRIGGER_MATCH_ANY


def build_ready_attack_payload(
    *,
    actor_id: str,
    actor_name: str,
    target_id: str,
    target_name: str,
    is_ranged: bool = False,
    condition_text: str | None = None,
    trigger_match: str | None = None,
) -> dict[str, Any]:
    return {
        "type": "ready_action",
        "action_type": "attack",
        "trigger": READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(trigger_match),
        "actor_id": str(actor_id),
        "actor_name": actor_name,
        "target_id": str(target_id),
        "target_name": target_name,
        "is_ranged": bool(is_ranged),
        "condition_text": condition_text or f"当 {target_name} 移动时发动一次攻击",
    }


def build_ready_spell_payload(
    *,
    actor_id: str,
    actor_name: str,
    target_id: str,
    target_name: str,
    spell_name: str,
    spell_level: int = 0,
    condition_text: str | None = None,
    slot_already_consumed: bool = False,
    slot_key: str | None = None,
    slots_remaining: int | None = None,
    concentration_spell_name: str | None = None,
    trigger_match: str | None = None,
) -> dict[str, Any]:
    payload = {
        "type": "ready_action",
        "action_type": "spell",
        "trigger": READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(trigger_match),
        "actor_id": str(actor_id),
        "actor_name": actor_name,
        "target_id": str(target_id),
        "target_name": target_name,
        "spell_name": spell_name,
        "spell_level": int(spell_level or 0),
        "condition_text": condition_text or f"当 {target_name} 移动时施放 {spell_name}",
    }
    payload["requires_concentration"] = True
    payload["concentration_spell_name"] = concentration_spell_name or build_ready_spell_concentration_name(spell_name)
    if slot_already_consumed:
        payload["slot_already_consumed"] = True
        if slot_key:
            payload["slot_key"] = slot_key
        if slots_remaining is not None:
            payload["slots_remaining"] = int(slots_remaining)
    return payload


def build_ready_move_payload(
    *,
    actor_id: str,
    actor_name: str,
    target_id: str,
    target_name: str,
    move_from: dict[str, Any],
    move_to: dict[str, Any],
    move_distance: int,
    condition_text: str | None = None,
    trigger_match: str | None = None,
) -> dict[str, Any]:
    to_x = int(move_to.get("x", 0))
    to_y = int(move_to.get("y", 0))
    return {
        "type": "ready_action",
        "action_type": "move",
        "trigger": READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(trigger_match),
        "actor_id": str(actor_id),
        "actor_name": actor_name,
        "target_id": str(target_id),
        "target_name": target_name,
        "move_from": {"x": int(move_from.get("x", 0)), "y": int(move_from.get("y", 0))},
        "move_to": {"x": to_x, "y": to_y},
        "move_distance": int(move_distance),
        "condition_text": condition_text
        or f"\u5f53 {target_name} \u79fb\u52a8\u65f6\u79fb\u52a8\u5230 ({to_x}, {to_y})",
    }


def build_ready_action_expiry(combat, actor_id: str) -> dict[str, Any] | None:
    turn_state = get_turn_state(combat, str(actor_id))
    ready_action = turn_state.get("ready_action")
    if not isinstance(ready_action, dict) or not ready_action:
        return None

    expiry = {
        "type": "ready_action_expired",
        "applied": False,
        "reason": "next_turn_started",
        "trigger": ready_action.get("trigger") or READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(ready_action.get("trigger_match")),
        "actor_id": str(actor_id),
        "actor_name": ready_action.get("actor_name") or str(actor_id),
        "target_id": ready_action.get("target_id"),
        "target_name": ready_action.get("target_name"),
        "action_type": ready_action.get("action_type") or "attack",
    }
    for key in (
        "spell_name",
        "spell_level",
        "requires_concentration",
        "concentration_spell_name",
        "slot_already_consumed",
        "slot_key",
        "slots_remaining",
        "move_to",
        "move_distance",
        "trigger_match",
        "condition_text",
    ):
        if key in ready_action:
            expiry[key] = ready_action.get(key)
    return expiry


def apply_ready_action_expiry_to_turn_state(combat, actor_id: str, expiry: dict[str, Any] | None) -> None:
    if not expiry:
        return
    turn_state = get_turn_state(combat, str(actor_id))
    turn_state.pop("ready_action", None)
    turn_state["ready_action_expired"] = expiry
    save_turn_state(combat, str(actor_id), turn_state)


def format_ready_action_expiry_log(expiry: dict[str, Any]) -> str:
    actor_name = expiry.get("actor_name") or "目标"
    action_type = expiry.get("action_type") or "attack"
    target_name = expiry.get("target_name") or expiry.get("target_id") or "目标"
    condition_text = str(expiry.get("condition_text") or "").strip()
    if action_type == "spell":
        action_text = f"准备法术 {expiry.get('spell_name') or '法术'}"
    elif action_type == "move":
        action_text = "准备移动"
    else:
        action_text = "准备攻击"
    if condition_text:
        return f"{actor_name} 的{action_text}条件「{condition_text}」未触发，到下个回合开始时失效。"
    return f"{actor_name} 的{action_text}没有在 {target_name} 移动时触发，到下个回合开始时失效。"


def build_ready_action_expiry_log(session_id: str, expiry: dict[str, Any]) -> GameLog:
    return GameLog(
        session_id=session_id,
        role="system",
        content=format_ready_action_expiry_log(expiry),
        log_type="combat",
        dice_result=expiry,
    )


def validate_ready_spell(spell_name: str | None, spell_level: int) -> dict[str, Any]:
    if not spell_name:
        raise HTTPException(400, "准备法术需要指定法术")
    spell = spell_service.get(spell_name)
    if not spell:
        raise HTTPException(400, f"未知法术：{spell_name}")
    base_level = int(spell.get("level", 0) or 0)
    effective_spell_level = int(spell_level or base_level or 0)
    slot_error = spell_service.validate_slot_level(spell_name, effective_spell_level)
    if slot_error:
        raise HTTPException(400, slot_error)
    if spell_action_cost(spell) != "action":
        raise HTTPException(400, "当前准备法术仅支持施法时间为动作的法术")
    if spell.get("aoe"):
        raise HTTPException(400, "当前准备法术仅支持单体法术")
    return spell


def validate_ready_move_destination(
    *,
    combat,
    actor_id: str,
    to_x: int | None,
    to_y: int | None,
    turn_state: dict[str, Any],
    actor_conditions: list[str] | None = None,
) -> dict[str, Any]:
    if to_x is None or to_y is None:
        raise HTTPException(400, "Ready movement requires a destination cell")
    try:
        destination = {"x": int(to_x), "y": int(to_y)}
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, "Ready movement destination must be a grid cell") from exc
    if not (0 <= destination["x"] < 20 and 0 <= destination["y"] < 12):
        raise HTTPException(400, "Ready movement destination is out of bounds")

    positions = dict(getattr(combat, "entity_positions", None) or {})
    origin = positions.get(str(actor_id))
    if not origin:
        raise HTTPException(400, "Ready movement actor has no grid position")
    origin = {"x": int(origin.get("x", 0)), "y": int(origin.get("y", 0))}

    for entity_id, position in positions.items():
        if str(entity_id) == str(actor_id):
            continue
        if int(position.get("x", -1)) == destination["x"] and int(position.get("y", -1)) == destination["y"]:
            raise HTTPException(400, "Ready movement destination is occupied")

    distance = max(abs(origin["x"] - destination["x"]), abs(origin["y"] - destination["y"]))
    if distance <= 0:
        raise HTTPException(400, "Ready movement destination must be different from the current cell")

    try:
        validate_displacement_allowed(actor_conditions or [], distance)
    except MovementRuleError as exc:
        raise HTTPException(400, "Cannot ready movement while speed is 0") from exc

    movement_max = max(0, int(turn_state.get("movement_max", 0) or 0))
    movement_used = max(0, int(turn_state.get("movement_used", 0) or 0))
    remaining = movement_max - movement_used
    if distance > remaining:
        raise HTTPException(
            400,
            f"Ready movement costs {distance} squares but only {remaining} remain",
        )
    return {"from": origin, "to": destination, "distance": distance}


async def resolve_ready_actions_for_movement(
    *,
    db,
    session,
    combat,
    moving_id: str,
    old_pos: dict[str, Any] | None,
    new_pos: dict[str, Any] | None,
    combat_service,
    has_ally_adjacent_to,
    resolve_opportunity_attacks=None,
) -> list[dict[str, Any]]:
    if not old_pos or not new_pos or old_pos == new_pos:
        return []

    states = dict(combat.turn_states or {})
    if not states:
        return []

    state = session.game_state or {}
    enemies = list(state.get("enemies") or [])
    results: list[dict[str, Any]] = []

    for actor_id, raw_turn_state in list(states.items()):
        turn_state = dict(raw_turn_state or {})
        ready = turn_state.get("ready_action") or {}
        if not _ready_action_matches_movement(
            ready,
            actor_id,
            moving_id,
            old_pos=old_pos,
            new_pos=new_pos,
            positions=combat.entity_positions or {},
        ):
            continue

        if ready.get("action_type") == "spell":
            result = await _resolve_ready_spell(
                db=db,
                session=session,
                combat=combat,
                turn_state=turn_state,
                actor_id=str(actor_id),
                moving_id=str(moving_id),
                ready_action=ready,
                enemies=enemies,
                combat_service=combat_service,
            )
        elif ready.get("action_type") == "move":
            result = await _resolve_ready_move(
                db=db,
                session=session,
                combat=combat,
                turn_state=turn_state,
                actor_id=str(actor_id),
                moving_id=str(moving_id),
                ready_action=ready,
                combat_service=combat_service,
                resolve_opportunity_attacks=resolve_opportunity_attacks,
            )
        else:
            result = await _resolve_ready_attack(
                db=db,
                session=session,
                combat=combat,
                turn_state=turn_state,
                actor_id=str(actor_id),
                moving_id=str(moving_id),
                ready_action=ready,
                enemies=enemies,
                combat_service=combat_service,
                has_ally_adjacent_to=has_ally_adjacent_to,
                old_pos=old_pos,
            )
        if result:
            results.append(result)
            if result.get("target_is_enemy") or result.get("actor_is_enemy"):
                state["enemies"] = enemies
                session.game_state = dict(state)
                flag_modified(session, "game_state")
            if result.get("target_new_hp") is not None and result.get("target_new_hp") <= 0:
                break

    return results


async def _resolve_ready_attack(
    *,
    db,
    session,
    combat,
    turn_state: dict[str, Any],
    actor_id: str,
    moving_id: str,
    ready_action: dict[str, Any],
    enemies: list[dict[str, Any]],
    combat_service,
    has_ally_adjacent_to,
    old_pos: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if turn_state.get("reaction_used"):
        return _ready_action_reaction_already_used_result(
            db=db,
            session=session,
            combat=combat,
            turn_state=turn_state,
            actor_id=actor_id,
            moving_id=moving_id,
            ready_action=ready_action,
            enemies=enemies,
        )

    actor = await db.get(Character, actor_id)
    if not actor:
        enemy_actor = _ready_enemy_by_id(enemies, actor_id)
        if enemy_actor:
            return await _resolve_enemy_ready_attack(
                db=db,
                session=session,
                combat=combat,
                turn_state=turn_state,
                actor_id=actor_id,
                moving_id=moving_id,
                ready_action=ready_action,
                enemy_actor=enemy_actor,
                enemies=enemies,
                combat_service=combat_service,
                old_pos=old_pos,
            )
        return None
    if int(actor.hp_current or 0) <= 0:
        return None
    if not can_take_reaction(actor):
        turn_state.pop("ready_action", None)
        turn_state["ready_action_expired"] = {
            "reason": "reaction_blocked",
            "triggered_by": moving_id,
        }
        save_turn_state(combat, actor_id, turn_state)
        return None

    try:
        is_ranged = bool(ready_action.get("is_ranged"))
        positions_override = _ready_leaves_reach_positions_override(
            combat,
            moving_id,
            old_pos=old_pos,
            ready_action=ready_action,
            is_ranged=is_ranged,
        )
        prepared = await prepare_direct_attack(
            db,
            combat=combat,
            player=actor,
            player_id=actor_id,
            target_id=moving_id,
            enemies=enemies,
            is_ranged=is_ranged,
            session=session,
            combat_service=combat_service,
            has_ally_adjacent_to=has_ally_adjacent_to,
            positions_override=positions_override,
        )
    except CombatAttackRollError as exc:
        turn_state.pop("ready_action", None)
        turn_state["ready_action_failed"] = {
            "reason": exc.detail,
            "triggered_by": moving_id,
        }
        save_turn_state(combat, actor_id, turn_state)
        db.add(GameLog(
            session_id=str(session.id),
            role="system",
            content=f"{actor.name} 的准备动作触发失败：{exc.detail}",
            log_type="combat",
            dice_result={
                "type": "ready_action",
                "applied": False,
                "reason": exc.detail,
                "condition_text": ready_action.get("condition_text"),
                "actor_id": actor_id,
                "target_id": moving_id,
            },
        ))
        return {
            "type": "ready_action",
            "applied": False,
            "actor_id": actor_id,
            "actor_name": actor.name,
            "target_id": moving_id,
            "target_name": ready_action.get("target_name") or moving_id,
            "condition_text": ready_action.get("condition_text"),
            "reason": exc.detail,
        }

    target_new_hp = None
    target_state = None
    concentration_log = None
    if prepared.attack_result["hit"]:
        target_new_hp, concentration_log, target_state = await apply_attack_damage_to_target(
            db,
            session_id=str(session.id),
            enemies=enemies,
            target_id=prepared.target_id,
            target_is_enemy=prepared.target_is_enemy,
            damage=prepared.damage,
            session=session,
            is_critical=prepared.attack_result.get("is_crit", False),
            attacker_id=actor_id,
            attacker_is_enemy=False,
            is_melee=not bool(ready_action.get("is_ranged")),
        )
        if concentration_log:
            db.add(concentration_log)

    updated_turn_state = consume_direct_attack_turn(prepared.turn_state, attacks_max=prepared.attacks_max)
    updated_turn_state["reaction_used"] = True
    updated_turn_state.pop("ready_action", None)
    updated_turn_state["ready_action_resolved"] = {
        "trigger": READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(ready_action.get("trigger_match")),
        "action_type": "attack",
        "condition_text": ready_action.get("condition_text"),
        "target_id": prepared.target_id,
        "target_name": prepared.target_name,
        "hit": prepared.attack_result["hit"],
        "damage": prepared.damage if prepared.attack_result["hit"] else 0,
    }
    save_turn_state(combat, actor_id, updated_turn_state)

    damage = prepared.damage if prepared.attack_result["hit"] else 0
    outcome = "命中" if prepared.attack_result["hit"] else "未命中"
    narration = (
        f"{prepared.player_name} 的准备动作触发："
        f"{prepared.target_name} 移动时发动攻击，{outcome}"
        f"{f'，造成 {damage} 伤害' if damage else ''}。"
    )
    dice_result = {
        "type": "ready_action",
        "action_type": "attack",
        "applied": True,
        "trigger": READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(ready_action.get("trigger_match")),
        "condition_text": ready_action.get("condition_text"),
        "actor_id": actor_id,
        "actor_name": prepared.player_name,
        "target_id": prepared.target_id,
        "target_name": prepared.target_name,
        "attack": prepared.attack_result,
        "damage": prepared.damage_roll,
        "total_damage": damage,
        "reaction_used": True,
    }
    if target_state is not None:
        dice_result["target_state"] = target_state

    db.add(GameLog(
        session_id=str(session.id),
        role="player",
        content=narration,
        log_type="combat",
        dice_result=dice_result,
    ))

    return {
        "type": "ready_action",
        "action_type": "attack",
        "applied": True,
        "trigger": READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(ready_action.get("trigger_match")),
        "condition_text": ready_action.get("condition_text"),
        "actor_id": actor_id,
        "actor_name": prepared.player_name,
        "target_id": prepared.target_id,
        "target_name": prepared.target_name,
        "attack_result": prepared.attack_result,
        "damage": damage,
        "damage_roll": prepared.damage_roll,
        "target_new_hp": target_new_hp,
        "target_state": target_state,
        "target_is_enemy": prepared.target_is_enemy,
        "turn_state": updated_turn_state,
        "narration": narration,
    }


def _ready_enemy_by_id(enemies: list[dict[str, Any]], actor_id: str) -> dict[str, Any] | None:
    return next((enemy for enemy in enemies if str(enemy.get("id")) == str(actor_id)), None)


def _ready_enemy_actor_state(
    enemy_actor: dict[str, Any],
    actor_id: str,
    *,
    concentration: str | None | object = Ellipsis,
) -> dict[str, Any]:
    resolved_concentration = (
        enemy_actor.get("concentration")
        if concentration is Ellipsis
        else concentration
    )
    return {
        "target_id": str(actor_id),
        "entity_id": str(actor_id),
        "target_name": enemy_actor.get("name") or str(actor_id),
        "concentration": resolved_concentration,
    }


def _clear_enemy_ready_spell_concentration_hold(
    enemy_actor: dict[str, Any],
    actor_id: str,
    ready_action: dict[str, Any],
) -> dict[str, Any] | None:
    if not ready_spell_concentration_matches(ready_action, enemy_actor.get("concentration")):
        return None
    enemy_actor["concentration"] = None
    return _ready_enemy_actor_state(enemy_actor, actor_id, concentration=None)


def _character_ai_spell_snapshot(character: Character) -> dict[str, Any]:
    derived = dict(character.derived or {})
    return {
        "id": str(character.id),
        "name": character.name,
        "hp_current": character.hp_current,
        "hp_max": derived.get("hp_max"),
        "ac": derived.get("ac"),
        "conditions": list(character.conditions or []),
        "condition_durations": dict(character.condition_durations or {}),
        "derived": derived,
    }


def _ready_action_reaction_already_used_result(
    *,
    db,
    session,
    combat,
    turn_state: dict[str, Any],
    actor_id: str,
    moving_id: str,
    ready_action: dict[str, Any],
    enemies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    action_type = str(ready_action.get("action_type") or "attack")
    actor_name = ready_action.get("actor_name") or str(actor_id)
    target_id = ready_action.get("target_id") or moving_id
    target_name = ready_action.get("target_name") or moving_id
    actor_is_enemy = any(str(enemy.get("id")) == str(actor_id) for enemy in enemies or [])
    failure = {
        "type": "ready_action_failed",
        "action_type": action_type,
        "reason": "reaction_already_used",
        "trigger": READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(ready_action.get("trigger_match")),
        "triggered_by": moving_id,
        "actor_id": actor_id,
        "actor_name": actor_name,
        "target_id": str(target_id),
        "target_name": target_name,
        "condition_text": ready_action.get("condition_text"),
        "reaction_already_used": True,
    }
    if actor_is_enemy:
        failure["actor_is_enemy"] = True
    if action_type == "spell":
        failure["spell_name"] = ready_action.get("spell_name")
        failure["spell_level"] = ready_action.get("spell_level")
    elif action_type == "move":
        if isinstance(ready_action.get("move_to"), dict):
            failure["move_to"] = dict(ready_action["move_to"])
        if isinstance(ready_action.get("move_from"), dict):
            failure["move_from"] = dict(ready_action["move_from"])

    updated_turn_state = dict(turn_state)
    updated_turn_state.pop("ready_action", None)
    updated_turn_state["ready_action_failed"] = failure
    save_turn_state(combat, actor_id, updated_turn_state)

    dice_result = {
        **failure,
        "type": "ready_action",
        "applied": False,
        "reaction_used": False,
    }
    db.add(GameLog(
        session_id=str(session.id),
        role="system",
        content=f"{actor_name}'s ready action could not trigger because its reaction was already used.",
        log_type="combat",
        dice_result=dice_result,
    ))

    return {
        "type": "ready_action",
        "action_type": action_type,
        "applied": False,
        "reason": "reaction_already_used",
        "trigger": READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(ready_action.get("trigger_match")),
        "triggered_by": moving_id,
        "condition_text": ready_action.get("condition_text"),
        "actor_id": actor_id,
        "actor_name": actor_name,
        "target_id": str(target_id),
        "target_name": target_name,
        "turn_state": updated_turn_state,
        "reaction_used": False,
        "reaction_already_used": True,
        **({"actor_is_enemy": True} if actor_is_enemy else {}),
        **({
            "spell_name": ready_action.get("spell_name"),
            "spell_level": ready_action.get("spell_level"),
        } if action_type == "spell" else {}),
    }


def _ready_enemy_attack_action(enemy: dict[str, Any], ready_action: dict[str, Any], *, is_ranged: bool) -> dict[str, Any] | None:
    explicit = ready_action.get("enemy_action")
    if isinstance(explicit, dict):
        return explicit
    for action in enemy.get("actions") or []:
        action_type = str(action.get("type") or "").lower()
        if "attack" not in action_type:
            continue
        if is_ranged and "ranged" not in action_type:
            continue
        if not is_ranged and "ranged" in action_type:
            continue
        return action
    for action in enemy.get("actions") or []:
        if "attack" in str(action.get("type") or "").lower():
            return action
    return None


def _ready_enemy_attack_derived(enemy: dict[str, Any], ready_action: dict[str, Any], *, is_ranged: bool) -> tuple[dict[str, Any], dict[str, Any] | None]:
    derived = dict(enemy.get("derived") or {})
    derived.setdefault("name", enemy.get("name") or enemy.get("id") or "Enemy")
    action = _ready_enemy_attack_action(enemy, ready_action, is_ranged=is_ranged)
    if not action:
        return derived, None

    attack_bonus = action.get("attack_bonus")
    if attack_bonus is None:
        attack_bonus = action.get("to_hit")
    if attack_bonus is not None:
        try:
            if is_ranged:
                derived["ranged_attack_bonus"] = int(attack_bonus)
            else:
                derived["attack_bonus"] = int(attack_bonus)
        except (TypeError, ValueError):
            pass

    damage_dice = action.get("damage_dice") or action.get("damage")
    if damage_dice:
        derived["damage_dice"] = str(damage_dice)
    damage_type = action.get("damage_type") or action.get("type_damage")
    if damage_type:
        derived["damage_type"] = str(damage_type)

    metadata = {
        key: action.get(key)
        for key in ("id", "name", "type", "attack_bonus", "damage_dice", "damage_type")
        if action.get(key) is not None
    }
    metadata["is_ranged"] = bool(is_ranged)
    return derived, metadata


def _ready_leaves_reach_positions_override(
    combat,
    moving_id: str,
    *,
    old_pos: dict[str, Any] | None,
    ready_action: dict[str, Any],
    is_ranged: bool,
) -> dict[str, Any] | None:
    if is_ranged:
        return None
    if normalize_ready_trigger_match(ready_action.get("trigger_match")) != READY_TRIGGER_MATCH_LEAVES_REACH:
        return None
    if not old_pos:
        return None
    positions = dict(combat.entity_positions or {})
    positions[str(moving_id)] = dict(old_pos)
    return positions


async def _resolve_enemy_ready_attack(
    *,
    db,
    session,
    combat,
    turn_state: dict[str, Any],
    actor_id: str,
    moving_id: str,
    ready_action: dict[str, Any],
    enemy_actor: dict[str, Any],
    enemies: list[dict[str, Any]],
    combat_service,
    old_pos: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if int(enemy_actor.get("hp_current") or 0) <= 0:
        return None
    if not can_take_reaction(enemy_actor):
        turn_state.pop("ready_action", None)
        turn_state["ready_action_expired"] = {
            "reason": "reaction_blocked",
            "triggered_by": moving_id,
        }
        save_turn_state(combat, actor_id, turn_state)
        return None

    target = await resolve_attack_target(db, moving_id, enemies, allow_auto_enemy=False, session=session)
    if not target:
        turn_state.pop("ready_action", None)
        turn_state["ready_action_failed"] = {
            "reason": "target_not_found",
            "triggered_by": moving_id,
        }
        save_turn_state(combat, actor_id, turn_state)
        return {
            "type": "ready_action",
            "action_type": "attack",
            "applied": False,
            "actor_id": actor_id,
            "actor_name": enemy_actor.get("name") or actor_id,
            "target_id": moving_id,
            "target_name": ready_action.get("target_name") or moving_id,
            "condition_text": ready_action.get("condition_text"),
            "reason": "target_not_found",
            "actor_is_enemy": True,
        }

    is_ranged = bool(ready_action.get("is_ranged"))
    attacker_derived, enemy_action = _ready_enemy_attack_derived(enemy_actor, ready_action, is_ranged=is_ranged)
    actor_conditions = list(enemy_actor.get("conditions") or [])
    target_conditions = await get_target_conditions(db, target, enemies)
    target_turn_state = get_turn_state(combat, target.id)
    if target_turn_state.get("dodging") and "dodging" not in target_conditions:
        target_conditions.append("dodging")

    attack_advantage, attack_disadvantage = combat_service.get_attack_modifiers(actor_conditions, enemy_actor)
    defense_advantage, defense_disadvantage = combat_service.get_defense_modifiers(target_conditions)
    positions = _ready_leaves_reach_positions_override(
        combat,
        moving_id,
        old_pos=old_pos,
        ready_action=ready_action,
        is_ranged=is_ranged,
    ) or dict(combat.entity_positions or {})
    attacker_pos = positions.get(str(actor_id), {})
    target_pos = positions.get(str(target.id), {})
    distance = max(
        abs(int(attacker_pos.get("x", 0) or 0) - int(target_pos.get("x", 0) or 0)),
        abs(int(attacker_pos.get("y", 0) or 0) - int(target_pos.get("y", 0) or 0)),
    )
    attack_result_obj = combat_service.resolve_melee_attack(
        attacker_derived=attacker_derived,
        target_derived=dict(target.derived or {}),
        advantage=attack_advantage or defense_advantage,
        disadvantage=attack_disadvantage or defense_disadvantage,
        is_ranged=is_ranged,
        attacker_conditions=actor_conditions,
        target_conditions=target_conditions,
        distance=distance,
    )
    attack_result = {
        **attack_result_obj.attack_roll,
        "advantage": (attack_advantage or defense_advantage) and not (attack_disadvantage or defense_disadvantage),
        "disadvantage": (attack_disadvantage or defense_disadvantage) and not (attack_advantage or defense_advantage),
        "roll_state": (
            "cancelled"
            if (attack_advantage or defense_advantage) and (attack_disadvantage or defense_disadvantage)
            else "advantage"
            if (attack_advantage or defense_advantage)
            else "disadvantage"
            if (attack_disadvantage or defense_disadvantage)
            else "normal"
        ),
    }
    if enemy_action:
        attack_result["enemy_action"] = enemy_action

    target_new_hp = None
    target_state = None
    concentration_log = None
    if attack_result.get("hit"):
        target_new_hp, concentration_log, target_state = await apply_attack_damage_to_target(
            db,
            session_id=str(session.id),
            enemies=enemies,
            target_id=target.id,
            target_is_enemy=target.is_enemy,
            damage=int(attack_result_obj.damage or 0),
            session=session,
            is_critical=bool(attack_result.get("is_crit")),
            attacker_id=actor_id,
            attacker_is_enemy=True,
            is_melee=not is_ranged,
        )
        if concentration_log:
            db.add(concentration_log)

    damage = int(attack_result_obj.damage or 0) if attack_result.get("hit") else 0
    updated_turn_state = dict(turn_state)
    updated_turn_state["reaction_used"] = True
    updated_turn_state.pop("ready_action", None)
    updated_turn_state["ready_action_resolved"] = {
        "trigger": READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(ready_action.get("trigger_match")),
        "action_type": "attack",
        "condition_text": ready_action.get("condition_text"),
        "target_id": target.id,
        "target_name": target.name,
        "hit": bool(attack_result.get("hit")),
        "damage": damage,
        "actor_is_enemy": True,
    }
    save_turn_state(combat, actor_id, updated_turn_state)

    actor_name = enemy_actor.get("name") or str(actor_id)
    outcome = "hits" if attack_result.get("hit") else "misses"
    narration = f"{actor_name}'s ready action triggers as {target.name} moves and {outcome}."
    dice_result = {
        "type": "ready_action",
        "action_type": "attack",
        "applied": True,
        "trigger": READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(ready_action.get("trigger_match")),
        "condition_text": ready_action.get("condition_text"),
        "actor_id": actor_id,
        "actor_name": actor_name,
        "actor_is_enemy": True,
        "target_id": target.id,
        "target_name": target.name,
        "target_is_enemy": target.is_enemy,
        "attack": attack_result,
        "damage": attack_result_obj.damage_roll,
        "total_damage": damage,
        "reaction_used": True,
    }
    if target_state is not None:
        dice_result["target_state"] = target_state
    db.add(GameLog(
        session_id=str(session.id),
        role="system",
        content=narration,
        log_type="combat",
        dice_result=dice_result,
    ))

    return {
        "type": "ready_action",
        "action_type": "attack",
        "applied": True,
        "trigger": READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(ready_action.get("trigger_match")),
        "condition_text": ready_action.get("condition_text"),
        "actor_id": actor_id,
        "actor_name": actor_name,
        "actor_is_enemy": True,
        "target_id": target.id,
        "target_name": target.name,
        "target_is_enemy": target.is_enemy,
        "attack_result": attack_result,
        "damage": damage,
        "damage_roll": attack_result_obj.damage_roll,
        "target_new_hp": target_new_hp,
        "target_state": target_state,
        "turn_state": updated_turn_state,
        "narration": narration,
    }


def _hazard_actor_state(hazard: dict[str, Any] | None) -> dict[str, Any] | None:
    if not hazard or not hazard.get("target_id"):
        return None
    state = {
        "target_id": str(hazard.get("target_id")),
        "target_name": hazard.get("target_name"),
    }
    if hazard.get("hp_after") is not None:
        state["hp_current"] = hazard.get("hp_after")
        state["hp_after"] = hazard.get("hp_after")
    for key in (
        "hp_before",
        "temporary_hp_after",
        "wild_shape_hp_after",
        "death_saves",
        "conditions",
    ):
        if hazard.get(key) is not None:
            state[key] = hazard.get(key)
    return state


def _flatten_opportunity_results(opportunity_results: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for opportunity in opportunity_results or []:
        result = dict(opportunity.get("result") or {})
        flattened.append({
            "attacker": opportunity.get("attacker"),
            "target": opportunity.get("target"),
            **result,
        })
    return flattened


def _first_movement_stop(opportunity_results: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    for opportunity in opportunity_results or []:
        stop = (opportunity.get("result") or {}).get("movement_stop")
        if stop:
            return stop
    return None


async def _moving_actor_state(db, session, actor_id: str) -> dict[str, Any] | None:
    actor = await db.get(Character, actor_id)
    if actor:
        state = {
            "target_id": str(actor.id),
            "target_name": actor.name,
            "hp_current": actor.hp_current,
            "hp_after": actor.hp_current,
            "conditions": list(actor.conditions or []),
        }
        if actor.death_saves is not None:
            state["death_saves"] = actor.death_saves
        if actor.condition_durations is not None:
            state["condition_durations"] = actor.condition_durations
        return state

    game_state = session.game_state or {}
    for enemy in game_state.get("enemies") or []:
        if str(enemy.get("id")) != str(actor_id):
            continue
        return {
            "target_id": str(enemy.get("id")),
            "target_name": enemy.get("name"),
            "hp_current": enemy.get("hp_current"),
            "hp_after": enemy.get("hp_current"),
            "conditions": list(enemy.get("conditions") or []),
            "condition_durations": dict(enemy.get("condition_durations") or {}),
        }
    return None


async def _resolve_ready_move(
    *,
    db,
    session,
    combat,
    turn_state: dict[str, Any],
    actor_id: str,
    moving_id: str,
    ready_action: dict[str, Any],
    combat_service,
    resolve_opportunity_attacks=None,
) -> dict[str, Any] | None:
    if turn_state.get("reaction_used"):
        return _ready_action_reaction_already_used_result(
            db=db,
            session=session,
            combat=combat,
            turn_state=turn_state,
            actor_id=actor_id,
            moving_id=moving_id,
            ready_action=ready_action,
            enemies=(session.game_state or {}).get("enemies") or [],
        )

    actor = await db.get(Character, actor_id)
    enemy_actor = None
    actor_is_enemy = False
    if actor:
        actor_name = actor.name
        actor_hp = int(actor.hp_current or 0)
        actor_conditions = list(actor.conditions or [])
        reaction_actor = actor
    else:
        enemy_actor = _ready_enemy_by_id((session.game_state or {}).get("enemies") or [], actor_id)
        if not enemy_actor:
            return None
        actor_is_enemy = True
        actor_name = enemy_actor.get("name") or str(actor_id)
        actor_hp = int(enemy_actor.get("hp_current") or 0)
        actor_conditions = list(enemy_actor.get("conditions") or [])
        reaction_actor = enemy_actor
    if actor_hp <= 0:
        return None
    if not can_take_reaction(reaction_actor):
        turn_state.pop("ready_action", None)
        turn_state["ready_action_expired"] = {
            "reason": "reaction_blocked",
            "triggered_by": moving_id,
        }
        save_turn_state(combat, actor_id, turn_state)
        return None

    move_to = ready_action.get("move_to") if isinstance(ready_action.get("move_to"), dict) else {}
    try:
        move_validation = validate_ready_move_destination(
            combat=combat,
            actor_id=actor_id,
            to_x=move_to.get("x"),
            to_y=move_to.get("y"),
            turn_state=turn_state,
            actor_conditions=actor_conditions,
        )
    except HTTPException as exc:
        detail = getattr(exc, "detail", str(exc))
        turn_state.pop("ready_action", None)
        turn_state["ready_action_failed"] = {
            "reason": detail,
            "triggered_by": moving_id,
        }
        save_turn_state(combat, actor_id, turn_state)
        db.add(GameLog(
            session_id=str(session.id),
            role="system",
            content=f"{actor_name} ready movement failed: {detail}",
            log_type="combat",
            dice_result={
                "type": "ready_action",
                "action_type": "move",
                "applied": False,
                "reason": detail,
                "condition_text": ready_action.get("condition_text"),
                "actor_id": actor_id,
                "target_id": moving_id,
            },
        ))
        return {
            "type": "ready_action",
            "action_type": "move",
            "applied": False,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "target_id": moving_id,
            "target_name": ready_action.get("target_name") or moving_id,
            "condition_text": ready_action.get("condition_text"),
            "reason": detail,
            **({"actor_is_enemy": True} if actor_is_enemy else {}),
        }

    from_pos = move_validation["from"]
    attempted_to_pos = move_validation["to"]
    to_pos = dict(attempted_to_pos)
    steps = int(move_validation["distance"])
    positions = dict(combat.entity_positions or {})
    opportunity_results = []
    movement_stop = None
    if steps > 0 and resolve_opportunity_attacks is not None:
        opportunity_results = await resolve_opportunity_attacks(
            db=db,
            session=session,
            combat=combat,
            moving_id=str(actor_id),
            old_pos=from_pos,
            new_pos=attempted_to_pos,
            positions=positions,
        )
        for opportunity in opportunity_results:
            if opportunity.get("log"):
                log = opportunity["log"]
                if isinstance(getattr(log, "dice_result", None), dict):
                    log.dice_result = {
                        **log.dice_result,
                        "ready_action": True,
                        "ready_actor_id": str(actor_id),
                        "ready_target_id": str(moving_id),
                        "attacker": opportunity.get("attacker"),
                        "target": opportunity.get("target"),
                    }
                db.add(log)
        movement_stop = _first_movement_stop(opportunity_results)
        if movement_stop:
            to_pos = dict(movement_stop.get("to") or from_pos)
            steps = max(abs(int(from_pos.get("x", 0)) - int(to_pos.get("x", 0))),
                        abs(int(from_pos.get("y", 0)) - int(to_pos.get("y", 0))))

    positions[str(actor_id)] = dict(to_pos)
    combat.entity_positions = positions
    flag_modified(combat, "entity_positions")

    hazard_result = None
    if steps > 0:
        hazard_result = await apply_movement_hazard(
            db=db,
            session=session,
            combat_state=combat,
            entity_id=str(actor_id),
            position=to_pos,
            combat_service=combat_service,
        )
    if hazard_result:
        hazard_result["trigger"] = "movement_hazard"
        hazard_result["ready_action"] = True
        hazard_result["ready_actor_id"] = str(actor_id)
        hazard_result["ready_target_id"] = str(moving_id)
    hazard_actor_state = _hazard_actor_state(hazard_result)
    opportunity_actor_state = (
        await _moving_actor_state(db, session, str(actor_id))
        if opportunity_results and not hazard_actor_state
        else None
    )
    actor_state = hazard_actor_state or opportunity_actor_state
    flattened_opportunities = _flatten_opportunity_results(opportunity_results)
    for opportunity in flattened_opportunities:
        opportunity["ready_action"] = True
        opportunity["ready_actor_id"] = str(actor_id)
        opportunity["ready_target_id"] = str(moving_id)

    updated_turn_state = dict(turn_state)
    if movement_stop and movement_stop.get("movement_used_to_max"):
        updated_turn_state["movement_used"] = max(
            int(updated_turn_state.get("movement_used", 0) or 0),
            int(updated_turn_state.get("movement_max", 0) or 0),
        )
    else:
        updated_turn_state["movement_used"] = int(updated_turn_state.get("movement_used", 0) or 0) + steps
    updated_turn_state["reaction_used"] = True
    updated_turn_state.pop("ready_action", None)
    updated_turn_state["ready_action_resolved"] = {
        "trigger": READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(ready_action.get("trigger_match")),
        "action_type": "move",
        "condition_text": ready_action.get("condition_text"),
        "target_id": moving_id,
        "target_name": ready_action.get("target_name") or moving_id,
        "from": dict(from_pos),
        "to": dict(to_pos),
        "steps": steps,
        "distance_ft": steps * 5,
    }
    if actor_is_enemy:
        updated_turn_state["ready_action_resolved"]["actor_is_enemy"] = True
    if movement_stop:
        updated_turn_state["ready_action_resolved"]["attempted_to"] = dict(attempted_to_pos)
        updated_turn_state["ready_action_resolved"]["movement_stop"] = movement_stop
    if flattened_opportunities:
        updated_turn_state["ready_action_resolved"]["opportunity_attacks"] = flattened_opportunities
    if hazard_result:
        updated_turn_state["ready_action_resolved"]["hazard_result"] = hazard_result
    if actor_state:
        updated_turn_state["ready_action_resolved"]["actor_state"] = actor_state
    save_turn_state(combat, actor_id, updated_turn_state)

    narration = (
        f"\u51c6\u5907\u52a8\u4f5c\u89e6\u53d1\uff1a{actor_name} \u5728 "
        f"{ready_action.get('target_name') or moving_id} \u79fb\u52a8\u65f6"
        f"\u79fb\u52a8 {steps * 5}ft\u3002"
    )
    dice_result = {
        "type": "ready_action",
        "action_type": "move",
        "applied": True,
        "trigger": READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(ready_action.get("trigger_match")),
        "condition_text": ready_action.get("condition_text"),
        "actor_id": actor_id,
        "actor_name": actor_name,
        "target_id": moving_id,
        "target_name": ready_action.get("target_name") or moving_id,
        "from": dict(from_pos),
        "to": dict(to_pos),
        "steps": steps,
        "distance_ft": steps * 5,
        "reaction_used": True,
    }
    if actor_is_enemy:
        dice_result["actor_is_enemy"] = True
    if movement_stop:
        dice_result["attempted_to"] = dict(attempted_to_pos)
        dice_result["movement_stop"] = movement_stop
    if flattened_opportunities:
        dice_result["opportunity_attacks"] = flattened_opportunities
    if hazard_result:
        dice_result["hazard_result"] = hazard_result
    if actor_state:
        dice_result["actor_state"] = actor_state
    db.add(GameLog(
        session_id=str(session.id),
        role="player",
        content=narration,
        log_type="combat",
        dice_result=dice_result,
    ))
    hazard_log = hazard_result_to_log_text(hazard_result)
    if hazard_log:
        db.add(GameLog(
            session_id=str(session.id),
            role="system",
            content=hazard_log,
            log_type="combat",
            dice_result={"hazard": hazard_result},
        ))

    result = {
        "type": "ready_action",
        "action_type": "move",
        "applied": True,
        "trigger": READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(ready_action.get("trigger_match")),
        "condition_text": ready_action.get("condition_text"),
        "actor_id": actor_id,
        "actor_name": actor_name,
        "target_id": moving_id,
        "target_name": ready_action.get("target_name") or moving_id,
        "from": dict(from_pos),
        "to": dict(to_pos),
        "steps": steps,
        "distance_ft": steps * 5,
        "entity_positions": positions,
        "turn_state": updated_turn_state,
        "narration": narration,
    }
    if actor_is_enemy:
        result["actor_is_enemy"] = True
    if movement_stop:
        result["attempted_to"] = dict(attempted_to_pos)
        result["movement_stop"] = movement_stop
    if flattened_opportunities:
        result["opportunity_attacks"] = flattened_opportunities
    if hazard_result:
        result["hazard_result"] = hazard_result
    if actor_state:
        result["actor_state"] = actor_state
    return result


async def _resolve_enemy_ready_spell(
    *,
    db,
    session,
    combat,
    turn_state: dict[str, Any],
    actor_id: str,
    moving_id: str,
    ready_action: dict[str, Any],
    enemy_actor: dict[str, Any],
    enemies: list[dict[str, Any]],
    combat_service,
) -> dict[str, Any] | None:
    actor_name = enemy_actor.get("name") or str(actor_id)
    spell_name = str(ready_action.get("spell_name") or "")
    spell_level = int(ready_action.get("spell_level") or 0)
    concentration_marker = (
        ready_action.get("concentration_spell_name")
        or build_ready_spell_concentration_name(spell_name)
    )

    def fail_ready_spell(
        reason: Any,
        *,
        actor_state: dict[str, Any] | None = None,
        concentration_lost: bool = False,
    ) -> dict[str, Any]:
        updated_turn_state = dict(turn_state)
        updated_turn_state.pop("ready_action", None)
        failure = {
            "type": "ready_action_failed",
            "action_type": "spell",
            "reason": reason,
            "triggered_by": moving_id,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "actor_is_enemy": True,
            "target_id": moving_id,
            "target_name": ready_action.get("target_name") or moving_id,
            "spell_name": spell_name,
            "spell_level": spell_level,
            "concentration_spell_name": concentration_marker,
            "condition_text": ready_action.get("condition_text"),
        }
        if actor_state:
            failure["actor_state"] = actor_state
        if concentration_lost:
            failure["concentration_lost"] = True
        updated_turn_state["ready_action_failed"] = failure
        save_turn_state(combat, actor_id, updated_turn_state)
        dice_result = {
            "type": "ready_action",
            "action_type": "spell",
            "applied": False,
            "reason": reason,
            "trigger": READY_TRIGGER_TARGET_MOVES,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "actor_is_enemy": True,
            "target_id": moving_id,
            "target_name": ready_action.get("target_name") or moving_id,
            "spell_name": spell_name,
            "spell_level": spell_level,
            "concentration_spell_name": concentration_marker,
            "condition_text": ready_action.get("condition_text"),
            "reaction_used": False,
        }
        if actor_state:
            dice_result["actor_state"] = actor_state
        if concentration_lost:
            dice_result["concentration_lost"] = True
        db.add(GameLog(
            session_id=str(session.id),
            role="system",
            content=f"{actor_name}'s ready spell {spell_name} failed: {reason}",
            log_type="combat",
            dice_result=dice_result,
        ))
        return {
            "type": "ready_action",
            "action_type": "spell",
            "applied": False,
            "reason": reason,
            "trigger": READY_TRIGGER_TARGET_MOVES,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "actor_is_enemy": True,
            "target_id": moving_id,
            "target_name": ready_action.get("target_name") or moving_id,
            "spell_name": spell_name,
            "spell_level": spell_level,
            "concentration_spell_name": concentration_marker,
            "condition_text": ready_action.get("condition_text"),
            "turn_state": updated_turn_state,
            "reaction_used": False,
            **({"actor_state": actor_state} if actor_state else {}),
            **({"concentration_lost": True} if concentration_lost else {}),
        }

    if int(enemy_actor.get("hp_current") or 0) <= 0:
        return None
    if not can_take_reaction(enemy_actor):
        turn_state.pop("ready_action", None)
        turn_state["ready_action_expired"] = {
            "reason": "reaction_blocked",
            "triggered_by": moving_id,
        }
        save_turn_state(combat, actor_id, turn_state)
        return None

    if ready_action.get("requires_concentration", True) and not ready_spell_concentration_matches(
        ready_action,
        enemy_actor.get("concentration"),
    ):
        return fail_ready_spell(
            "concentration_lost",
            actor_state=_ready_enemy_actor_state(enemy_actor, actor_id),
            concentration_lost=True,
        )

    try:
        spell = validate_ready_spell(spell_name, spell_level)
    except HTTPException as exc:
        return fail_ready_spell(getattr(exc, "detail", str(exc)))

    effective_spell_level = int(spell_level or spell.get("level", 0) or 0)
    if effective_spell_level > 0:
        return fail_ready_spell("enemy_ready_spell_slots_not_supported")
    if spell_requires_attack_roll(spell_name, spell):
        return fail_ready_spell("enemy_ready_spell_attack_not_supported")

    target_character = await db.get(Character, moving_id)
    if not target_character or int(target_character.hp_current or 0) <= 0:
        return fail_ready_spell("target_not_found")

    state = session.game_state or {}
    actor_derived = dict(enemy_actor.get("derived") or {})
    resolution = await resolve_ai_spell_action(
        db,
        session=session,
        actor_name=actor_name,
        is_enemy=True,
        caster=enemy_actor,
        actor_derived=actor_derived,
        decided_target_id=moving_id,
        decided_reason="enemy ready spell trigger",
        decision={
            "action_type": "spell",
            "action_name": spell_name,
            "spell_level": effective_spell_level,
        },
        state=state,
        enemies=enemies,
        enemies_alive=[
            enemy
            for enemy in enemies
            if int(enemy.get("hp_current") or 0) > 0
        ],
        all_characters=[_character_ai_spell_snapshot(target_character)],
        spell_service_obj=spell_service,
        combat_service=combat_service,
        positions=dict(combat.entity_positions or {}),
        grid_data=dict(combat.grid_data or {}),
        turn_states=dict(combat.turn_states or {}),
    )
    if resolution is None:
        return fail_ready_spell("enemy_ready_spell_resolution_failed")

    actor_state = (
        _ready_enemy_actor_state(enemy_actor, actor_id)
        if spell.get("concentration")
        else _clear_enemy_ready_spell_concentration_hold(enemy_actor, actor_id, ready_action)
    )
    concentration_transition = {}
    if actor_state:
        if spell.get("concentration"):
            concentration_transition = {
                "concentration_started": True,
                "concentration_spell_name": enemy_actor.get("concentration"),
            }
        else:
            concentration_transition = {
                "concentration_ended": True,
                "concentration_spell_name": concentration_marker,
            }

    target_id = resolution.spell_target or moving_id
    target_name = resolution.target_name or target_character.name
    target_state = resolution.target_state
    save_result = resolution.save_result or (target_state or {}).get("save")
    updated_turn_state = dict(turn_state)
    updated_turn_state["reaction_used"] = True
    updated_turn_state.pop("ready_action", None)
    updated_turn_state["ready_action_resolved"] = {
        "trigger": READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(ready_action.get("trigger_match")),
        "action_type": "spell",
        "condition_text": ready_action.get("condition_text"),
        "spell_name": spell_name,
        "spell_level": effective_spell_level,
        "target_id": target_id,
        "target_name": target_name,
        "damage": resolution.damage,
        "heal": resolution.heal,
        "actor_is_enemy": True,
        "target_state": target_state,
        "save_result": save_result,
        **({"actor_state": actor_state} if actor_state else {}),
        **concentration_transition,
    }
    save_turn_state(combat, actor_id, updated_turn_state)

    damage_text = f", dealing {resolution.damage} damage" if resolution.damage else ""
    heal_text = f", healing {resolution.heal} HP" if resolution.heal else ""
    narration = (
        f"{actor_name}'s ready action triggers as "
        f"{ready_action.get('target_name') or target_name} moves: "
        f"{spell_name}{damage_text}{heal_text}."
    )
    dice_result = {
        "type": "ready_action",
        "action_type": "spell",
        "applied": True,
        "trigger": READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(ready_action.get("trigger_match")),
        "condition_text": ready_action.get("condition_text"),
        "actor_id": actor_id,
        "actor_name": actor_name,
        "actor_is_enemy": True,
        "target_id": target_id,
        "target_name": target_name,
        "target_is_enemy": False,
        "spell_name": spell_name,
        "spell_level": effective_spell_level,
        "dice": resolution.dice_detail,
        "damage": resolution.damage,
        "heal": resolution.heal,
        "target_state": target_state,
        "save_result": save_result,
        "reaction_used": True,
        **({"actor_state": actor_state} if actor_state else {}),
        **concentration_transition,
    }
    db.add(GameLog(
        session_id=str(session.id),
        role="system",
        content=narration,
        log_type="combat",
        dice_result=dice_result,
    ))

    return {
        "type": "ready_action",
        "action_type": "spell",
        "applied": True,
        "trigger": READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(ready_action.get("trigger_match")),
        "condition_text": ready_action.get("condition_text"),
        "actor_id": actor_id,
        "actor_name": actor_name,
        "actor_is_enemy": True,
        "target_id": target_id,
        "target_name": target_name,
        "target_is_enemy": False,
        "spell_name": spell_name,
        "spell_level": effective_spell_level,
        "damage": resolution.damage,
        "heal": resolution.heal,
        "dice_detail": resolution.dice_detail,
        "target_new_hp": resolution.target_new_hp,
        "target_state": target_state,
        "save_result": save_result,
        "turn_state": updated_turn_state,
        "narration": narration,
        **({"actor_state": actor_state} if actor_state else {}),
        **concentration_transition,
    }


async def _resolve_ready_spell(
    *,
    db,
    session,
    combat,
    turn_state: dict[str, Any],
    actor_id: str,
    moving_id: str,
    ready_action: dict[str, Any],
    enemies: list[dict[str, Any]],
    combat_service,
) -> dict[str, Any] | None:
    if turn_state.get("reaction_used"):
        return _ready_action_reaction_already_used_result(
            db=db,
            session=session,
            combat=combat,
            turn_state=turn_state,
            actor_id=actor_id,
            moving_id=moving_id,
            ready_action=ready_action,
            enemies=enemies,
        )

    actor = await db.get(Character, actor_id)
    if not actor:
        enemy_actor = _ready_enemy_by_id(enemies, actor_id)
        if enemy_actor:
            return await _resolve_enemy_ready_spell(
                db=db,
                session=session,
                combat=combat,
                turn_state=turn_state,
                actor_id=actor_id,
                moving_id=moving_id,
                ready_action=ready_action,
                enemy_actor=enemy_actor,
                enemies=enemies,
                combat_service=combat_service,
            )
        return None
    if int(actor.hp_current or 0) <= 0:
        return None
    if not can_take_reaction(actor):
        turn_state.pop("ready_action", None)
        turn_state["ready_action_expired"] = {
            "reason": "reaction_blocked",
            "triggered_by": moving_id,
        }
        save_turn_state(combat, actor_id, turn_state)
        return None

    spell_name = str(ready_action.get("spell_name") or "")
    spell_level = int(ready_action.get("spell_level") or 0)
    concentration_marker = ready_action.get("concentration_spell_name") or build_ready_spell_concentration_name(spell_name)
    if ready_action.get("requires_concentration", True) and not ready_spell_concentration_matches(ready_action, actor.concentration):
        actor_state = build_ready_spell_actor_state(actor)
        turn_state.pop("ready_action", None)
        turn_state["ready_action_failed"] = {
            "type": "ready_action_failed",
            "action_type": "spell",
            "reason": "concentration_lost",
            "triggered_by": moving_id,
            "spell_name": spell_name,
            "concentration_spell_name": concentration_marker,
            "condition_text": ready_action.get("condition_text"),
            "actor_state": actor_state,
        }
        save_turn_state(combat, actor_id, turn_state)
        narration = f"{actor.name} 的准备法术 {spell_name} 因专注中断而消散。"
        dice_result = {
            "type": "ready_action",
            "action_type": "spell",
            "applied": False,
            "reason": "concentration_lost",
            "concentration_lost": True,
            "trigger": READY_TRIGGER_TARGET_MOVES,
            "actor_id": actor_id,
            "actor_name": actor.name,
            "target_id": moving_id,
            "target_name": ready_action.get("target_name") or moving_id,
            "spell_name": spell_name,
            "spell_level": spell_level,
            "concentration_spell_name": concentration_marker,
            "condition_text": ready_action.get("condition_text"),
            "actor_state": actor_state,
            "reaction_used": False,
        }
        db.add(GameLog(
            session_id=str(session.id),
            role="system",
            content=narration,
            log_type="combat",
            dice_result=dice_result,
        ))
        return {
            "type": "ready_action",
            "action_type": "spell",
            "applied": False,
            "reason": "concentration_lost",
            "concentration_lost": True,
            "actor_id": actor_id,
            "actor_name": actor.name,
            "target_id": moving_id,
            "target_name": ready_action.get("target_name") or moving_id,
            "spell_name": spell_name,
            "spell_level": spell_level,
            "concentration_spell_name": concentration_marker,
            "condition_text": ready_action.get("condition_text"),
            "actor_state": actor_state,
            "turn_state": turn_state,
            "narration": narration,
            "reaction_used": False,
        }

    try:
        spell = validate_ready_spell(spell_name, spell_level)
        if spell_requires_attack_roll(spell_name, spell):
            result = await _resolve_ready_spell_attack(
                db=db,
                session=session,
                combat=combat,
                actor=actor,
                actor_id=actor_id,
                spell_name=spell_name,
                spell_level=spell_level,
                spell=spell,
                target_id=moving_id,
                enemies=enemies,
                slot_already_consumed=bool(ready_action.get("slot_already_consumed")),
            )
        else:
            result = await cast_direct_spell(
                db,
                session_id=str(session.id),
                session=session,
                combat_obj=combat,
                caster=actor,
                caster_id=actor_id,
                spell_name=spell_name,
                spell_level=spell_level,
                target_id=moving_id,
                target_ids=[moving_id],
                skip_turn_state_validation=True,
                skip_turn_state_consumption=True,
                skip_slot_consumption=bool(ready_action.get("slot_already_consumed")),
            )
    except (CombatDirectSpellError, CombatSpellRollError, CombatSpellResolutionError, HTTPException) as exc:
        detail = getattr(exc, "detail", str(exc))
        turn_state.pop("ready_action", None)
        turn_state["ready_action_failed"] = {
            "reason": detail,
            "triggered_by": moving_id,
        }
        save_turn_state(combat, actor_id, turn_state)
        db.add(GameLog(
            session_id=str(session.id),
            role="system",
            content=f"{actor.name} 的准备法术触发失败：{detail}",
            log_type="combat",
            dice_result={
                "type": "ready_action",
                "action_type": "spell",
                "applied": False,
                "reason": detail,
                "condition_text": ready_action.get("condition_text"),
                "actor_id": actor_id,
                "target_id": moving_id,
                "spell_name": spell_name,
            },
        ))
        return {
            "type": "ready_action",
            "action_type": "spell",
            "applied": False,
            "actor_id": actor_id,
            "actor_name": actor.name,
            "target_id": moving_id,
            "target_name": ready_action.get("target_name") or moving_id,
            "spell_name": spell_name,
            "condition_text": ready_action.get("condition_text"),
            "reason": detail,
        }

    for concentration_log in result.concentration_logs:
        db.add(concentration_log)
    for wild_magic_log in getattr(result, "wild_magic_logs", []):
        db.add(wild_magic_log)

    actor_state = build_ready_spell_actor_state(actor) if spell.get("concentration") else clear_ready_spell_concentration_hold(actor, ready_action)
    concentration_transition = {}
    if actor_state:
        if spell.get("concentration"):
            concentration_transition = {
                "concentration_started": True,
                "concentration_spell_name": actor.concentration,
            }
        else:
            concentration_transition = {
                "concentration_ended": True,
                "concentration_spell_name": concentration_marker,
            }

    updated_turn_state = dict(result.turn_state or turn_state)
    updated_turn_state["reaction_used"] = True
    updated_turn_state.pop("ready_action", None)
    attack_roll = (getattr(result, "log_dice_result", None) or {}).get("attack")
    updated_turn_state["ready_action_resolved"] = {
        "trigger": READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(ready_action.get("trigger_match")),
        "action_type": "spell",
        "condition_text": ready_action.get("condition_text"),
        "spell_name": spell_name,
        "target_id": result.target_id or moving_id,
        "target_name": ready_action.get("target_name") or moving_id,
        "damage": result.damage,
        "heal": result.heal,
        **({"hit": bool(attack_roll.get("hit")), "attack": attack_roll} if attack_roll else {}),
        **({"actor_state": actor_state} if actor_state else {}),
        **concentration_transition,
        **({
            "slot_already_consumed": True,
            "slot_key": ready_action.get("slot_key"),
            "slots_remaining": ready_action.get("slots_remaining"),
        } if ready_action.get("slot_already_consumed") else {}),
    }
    save_turn_state(combat, actor_id, updated_turn_state)

    damage_text = f"，造成 {result.damage} 伤害" if result.damage else ""
    heal_text = f"，恢复 {result.heal} HP" if result.heal else ""
    narration = (
        f"{actor.name} 的准备动作触发："
        f"{ready_action.get('target_name') or moving_id} 移动时施放 {spell_name}"
        f"{damage_text}{heal_text}。"
    )
    target_state = result.target_state
    dice_result = {
        "type": "ready_action",
        "action_type": "spell",
        "applied": True,
        "trigger": READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(ready_action.get("trigger_match")),
        "condition_text": ready_action.get("condition_text"),
        "actor_id": actor_id,
        "actor_name": actor.name,
        "target_id": result.target_id or moving_id,
        "target_name": ready_action.get("target_name") or moving_id,
        "spell_name": spell_name,
        "spell_level": spell_level,
        "dice": result.dice_detail,
        "attack": attack_roll,
        "damage": result.damage,
        "heal": result.heal,
        "target_state": target_state,
        "save_result": (target_state or {}).get("save"),
        "aoe": result.aoe_results,
        "reaction_used": True,
        **({"actor_state": actor_state} if actor_state else {}),
        **concentration_transition,
        **({
            "slot_already_consumed": True,
            "slot_key": ready_action.get("slot_key"),
            "slots_remaining": ready_action.get("slots_remaining"),
        } if ready_action.get("slot_already_consumed") else {}),
    }

    db.add(GameLog(
        session_id=str(session.id),
        role="player",
        content=narration,
        log_type="combat",
        dice_result=dice_result,
    ))

    target_is_enemy = any(str(enemy.get("id")) == str(result.target_id or moving_id) for enemy in enemies)
    return {
        "type": "ready_action",
        "action_type": "spell",
        "applied": True,
        "trigger": READY_TRIGGER_TARGET_MOVES,
        "trigger_match": normalize_ready_trigger_match(ready_action.get("trigger_match")),
        "condition_text": ready_action.get("condition_text"),
        "actor_id": actor_id,
        "actor_name": actor.name,
        "target_id": result.target_id or moving_id,
        "target_name": ready_action.get("target_name") or moving_id,
        "spell_name": spell_name,
        "spell_level": spell_level,
        "damage": result.damage,
        "heal": result.heal,
        "attack_result": attack_roll,
        "hit": attack_roll.get("hit") if attack_roll else None,
        "dice_detail": result.dice_detail,
        "target_new_hp": result.target_new_hp,
        "target_state": target_state,
        "target_is_enemy": target_is_enemy,
        "turn_state": updated_turn_state,
        "narration": narration,
        **({"actor_state": actor_state} if actor_state else {}),
        **concentration_transition,
        **({
            "slot_already_consumed": True,
            "slot_key": ready_action.get("slot_key"),
            "slots_remaining": ready_action.get("slots_remaining"),
        } if ready_action.get("slot_already_consumed") else {}),
    }


async def _resolve_ready_spell_attack(
    *,
    db,
    session,
    combat,
    actor,
    actor_id: str,
    spell_name: str,
    spell_level: int,
    spell: dict[str, Any],
    target_id: str,
    enemies: list[dict[str, Any]],
    slot_already_consumed: bool = False,
):
    prepared = await prepare_spell_roll(
        db,
        combat_obj=combat,
        session=session,
        caster=actor,
        caster_id=actor_id,
        spell_name=spell_name,
        spell_level=spell_level,
        spell=spell,
        target_id=target_id,
        target_ids=[target_id],
        enemies=enemies,
        default_turn_state=DEFAULT_TURN_STATE,
        get_turn_state=get_turn_state,
        consume_slot=spell_service.consume_slot,
        calc_upcast_dice=spell_service.calc_upcast_dice,
        skip_turn_state_validation=True,
        store_pending_spell_result=False,
    )
    pending_spell = dict(prepared.pending_spell)
    if slot_already_consumed:
        pending_spell["slot_already_consumed"] = True
    return await confirm_pending_spell(
        db,
        session_id=str(session.id),
        combat_obj=combat,
        caster=actor,
        caster_entity_id=actor_id,
        pending=pending_spell,
        spell=spell,
        state=session.game_state or {},
        enemies=enemies,
        damage_values=None,
        session=session,
        spell_service_obj=spell_service,
        check_combat_outcome_func=check_and_cleanup_combat_outcome,
    )


def _ready_grid_distance(a: dict[str, Any] | None, b: dict[str, Any] | None) -> int | None:
    if not a or not b:
        return None
    try:
        return max(
            abs(int(a.get("x", 0)) - int(b.get("x", 0))),
            abs(int(a.get("y", 0)) - int(b.get("y", 0))),
        )
    except (TypeError, ValueError):
        return None


def _ready_action_matches_movement(
    ready_action: dict[str, Any],
    actor_id: str,
    moving_id: str,
    *,
    old_pos: dict[str, Any] | None = None,
    new_pos: dict[str, Any] | None = None,
    positions: dict[str, Any] | None = None,
) -> bool:
    if not ready_action or ready_action.get("action_type") not in {"attack", "spell", "move"}:
        return False
    if ready_action.get("trigger") != READY_TRIGGER_TARGET_MOVES:
        return False
    if str(actor_id) == str(moving_id):
        return False
    target_id = ready_action.get("target_id")
    if target_id is None or str(target_id) != str(moving_id):
        return False

    trigger_match = normalize_ready_trigger_match(ready_action.get("trigger_match"))
    if trigger_match == READY_TRIGGER_MATCH_ANY:
        return True

    actor_pos = (positions or {}).get(str(actor_id))
    old_distance = _ready_grid_distance(actor_pos, old_pos)
    new_distance = _ready_grid_distance(actor_pos, new_pos)
    if old_distance is None or new_distance is None:
        return False

    if trigger_match == READY_TRIGGER_MATCH_ENTERS_REACH:
        return old_distance > 1 and new_distance <= 1
    if trigger_match == READY_TRIGGER_MATCH_LEAVES_REACH:
        return old_distance <= 1 and new_distance > 1
    return True


def matching_ready_action_actor_ids_for_movement(
    combat,
    *,
    moving_id: str,
    old_pos: dict[str, Any] | None,
    new_pos: dict[str, Any] | None,
) -> set[str]:
    if not old_pos or not new_pos or old_pos == new_pos:
        return set()
    states = dict(getattr(combat, "turn_states", None) or {})
    if not states:
        return set()
    positions = dict(getattr(combat, "entity_positions", None) or {})
    return {
        str(actor_id)
        for actor_id, raw_turn_state in states.items()
        if _ready_action_matches_movement(
            (raw_turn_state or {}).get("ready_action") or {},
            str(actor_id),
            str(moving_id),
            old_pos=old_pos,
            new_pos=new_pos,
            positions=positions,
        )
    }
