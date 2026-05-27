"""AI special action branch for monster Recharge abilities."""

from __future__ import annotations

import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from api.combat._shared import _get_ts, svc
from api.combat.ai_turn_utils import advance_ai_turn, tick_ai_actor_conditions
from models import Character, CombatState, GameLog
from services.combat_condition_immunity_service import is_condition_immune, normalize_condition
from services.combat_concentration_effect_service import clear_concentration_effects_for_caster
from services.combat_concentration_service import break_concentration_if_incapacitated
from services.combat_grid_service import chebyshev_distance
from services.combat_recharge_service import choose_recharge_ability, mark_recharge_ability_used
from services.combat_resistance_service import apply_character_damage_resistance
from services.combat_temporary_hp_service import build_character_target_state
from services.dnd_rules import apply_character_damage, get_life_state, roll_dice, roll_saving_throw


async def handle_ai_special_action(
    session_id: str,
    db,
    session,
    combat,
    turn_order,
    next_index: int,
    actor_id: str,
    actor_name: str,
    is_enemy: bool,
    enemy,
    enemies: list[dict[str, Any]],
    all_characters: list[dict[str, Any]],
    positions: dict[str, Any] | None,
    decided_target_id: str | None,
    decided_reason: str,
    decision: dict[str, Any],
):
    """Resolve enemy Recharge damage abilities before falling back to attack/spell."""
    if not is_enemy or not enemy:
        return None

    action_type = str(decision.get("action_type") or "").lower()
    action_name = decision.get("action_name")
    if action_type != "special" and not action_name:
        return None

    ability = choose_recharge_ability(enemy, action_name=action_name)
    if not ability:
        return None
    if action_name and _normalize_name(ability.get("name")) != _normalize_name(action_name):
        return None
    if not ability.get("damage_dice"):
        return None

    targets = _choose_special_targets(
        decided_target_id,
        all_characters,
        ability,
        actor_id=actor_id,
        positions=positions or {},
    )
    if not targets:
        return None

    damage_roll = roll_dice(str(ability.get("damage_dice") or "1d6"))
    base_damage = int(damage_roll.get("total") or 0)
    damage_type = ability.get("damage_type") or "bludgeoning"
    target_results: list[dict[str, Any]] = []

    for target in targets:
        applied = await _apply_recharge_damage_to_target(
            db,
            session_id=session_id,
            session=session,
            target=target,
            enemies=enemies,
            ability=ability,
            base_damage=base_damage,
            damage_type=damage_type,
        )
        if not applied:
            continue
        target_results.append(applied)

    if not target_results:
        return None

    primary_result = target_results[0]
    target_state = primary_result.get("target_state")
    target_new_hp = primary_result.get("target_new_hp")
    applied_damage = sum(result.get("damage", 0) for result in target_results)
    save_detail = primary_result.get("save")
    target_summary = _target_summary(target_results)

    mark_recharge_ability_used(enemy, str(ability.get("id")))
    state = session.game_state or {}
    state["enemies"] = enemies
    session.game_state = dict(state)
    _safe_flag_modified(session, "game_state")

    actor_ts = _get_ts(combat, actor_id)
    actor_ts["action_used"] = True
    _save_turn_state(combat, actor_id, actor_ts)

    narration = _special_narration(
        actor_name=actor_name,
        ability=ability,
        target_name=target_summary,
        damage=applied_damage,
        damage_type=damage_type,
        save_detail=save_detail,
        target_results=target_results,
        reason=decided_reason,
    )
    db.add(GameLog(
        session_id=session_id,
        role="enemy",
        content=narration,
        log_type="combat",
        dice_result={
            "special": {
                "ability": ability.get("name"),
                "damage": damage_roll,
                "save": save_detail,
                "targets": target_results,
            },
        },
    ))
    for log in tick_ai_actor_conditions(
        session_id=session_id,
        session=session,
        actor_name=actor_name,
        is_enemy=True,
        enemy=enemy,
        character=None,
        enemies=enemies,
    ):
        db.add(log)

    await advance_ai_turn(combat, session, db, turn_order, next_index)

    combat_over, outcome = await _check_party_combat_outcome(db, session, enemies, all_characters)
    if combat_over:
        session.combat_active = False
        old_combat = (
            await db.execute(select(CombatState).where(CombatState.session_id == session_id))
        ).scalars().first()
        if old_combat:
            await db.delete(old_combat)

    await db.commit()
    return {
        "actor_name": actor_name,
        "actor_id": actor_id,
        "narration": narration,
        "attack_result": {},
        "damage": applied_damage,
        "damage_roll": damage_roll,
        "damage_type": damage_type,
        "save": save_detail,
        "target_results": target_results,
        "aoe_results": target_results,
        "special_action": {
            "ability_id": ability.get("id"),
            "name": ability.get("name"),
            "recharge": ability.get("recharge"),
            "available": False,
        },
        "target_id": primary_result.get("target_id"),
        "target_new_hp": target_new_hp,
        "target_state": target_state,
        "next_turn_index": next_index,
        "round_number": combat.round_number,
        "combat_over": combat_over,
        "outcome": outcome,
        "entity_positions": dict(combat.entity_positions or {}),
    }


async def _apply_recharge_damage_to_target(
    db,
    *,
    session_id: str,
    session,
    target: dict[str, Any],
    enemies: list[dict[str, Any]],
    ability: dict[str, Any],
    base_damage: int,
    damage_type: str,
) -> dict[str, Any] | None:
    save_detail = _roll_recharge_save(target, ability)
    saved = bool(save_detail and save_detail.get("success"))
    damage_after_save = base_damage // 2 if saved and _half_on_save(ability) else base_damage
    target_character = await db.get(Character, str(target.get("id")))
    target_name = target.get("name", "target")
    applied_damage = damage_after_save

    if target_character:
        target_name = target_character.name
        applied_damage, _resisted = apply_character_damage_resistance(
            target_character,
            damage_after_save,
            damage_type,
        )
        apply_character_damage(target_character, applied_damage)
        condition_result = await _apply_recharge_condition_to_target(
            db,
            session_id=session_id,
            session=session,
            target=target_character,
            ability=ability,
            save_detail=save_detail,
        )
        target_state = build_character_target_state(target_character)
        target_state["target_name"] = target_name
        if condition_result:
            target_state["conditions"] = target_character.conditions or []
            target_state["condition_durations"] = target_character.condition_durations or {}
            target_state["life_state"] = get_life_state(target_character)
            target_state["concentration"] = target_character.concentration
        return {
            "target_id": str(target_character.id),
            "target_name": target_name,
            "damage": applied_damage,
            "base_damage": base_damage,
            "damage_after_save": damage_after_save,
            "damage_type": damage_type,
            "save": save_detail,
            "condition_result": condition_result,
            "target_new_hp": target_character.hp_current,
            "target_state": target_state,
            **target_state,
        }

    target_enemy = next((item for item in enemies if str(item.get("id")) == str(target.get("id"))), None)
    if not target_enemy:
        return None

    target_name = target_enemy.get("name", target_name)
    applied_damage = svc.apply_damage_with_resistance(
        damage_after_save,
        damage_type,
        target_enemy.get("resistances", []),
        target_enemy.get("immunities", []),
        target_enemy.get("vulnerabilities", []),
    )
    target_enemy["hp_current"] = svc.apply_damage(
        target_enemy.get("hp_current", 0),
        applied_damage,
        target_enemy.get("derived", {}).get("hp_max", target_enemy.get("hp_max", 10)),
    )
    condition_result = await _apply_recharge_condition_to_target(
        db,
        session_id=session_id,
        session=session,
        target=target_enemy,
        ability=ability,
        save_detail=save_detail,
    )
    target_state = _enemy_target_state(target_enemy)
    return {
        "target_id": str(target_enemy.get("id")),
        "target_name": target_name,
        "damage": applied_damage,
        "base_damage": base_damage,
        "damage_after_save": damage_after_save,
        "damage_type": damage_type,
        "save": save_detail,
        "condition_result": condition_result,
        "target_new_hp": target_enemy["hp_current"],
        "target_state": target_state,
        **target_state,
    }


async def _apply_recharge_condition_to_target(
    db,
    *,
    session_id: str,
    session,
    target: dict[str, Any] | Character,
    ability: dict[str, Any],
    save_detail: dict[str, Any] | None,
) -> dict[str, Any] | None:
    condition = _recharge_condition(ability)
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

    duration_rounds = _recharge_condition_duration(ability)
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
    if concentration_log:
        await clear_concentration_effects_for_caster(
            db,
            session,
            target.id,
            spell_name=(concentration_log.dice_result or {}).get("spell_name"),
        )
        db.add(concentration_log)
    return {
        "condition": condition,
        "applied": True,
        "immune": False,
        "duration_rounds": duration_rounds,
        "concentration_broken": bool(concentration_log),
    }


def _recharge_condition(ability: dict[str, Any]) -> str | None:
    for key in ("condition_on_failed_save", "condition_name", "condition"):
        condition = normalize_condition(ability.get(key))
        if condition:
            return condition
    values = ability.get("conditions_on_failed_save")
    if isinstance(values, list):
        for value in values:
            condition = normalize_condition(value)
            if condition:
                return condition
    return None


def _recharge_condition_duration(ability: dict[str, Any]) -> int | None:
    for key in ("condition_duration_rounds", "duration_rounds", "condition_duration"):
        value = ability.get(key)
        if value is None:
            continue
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            continue
    return None


def _choose_special_targets(
    target_id: str | None,
    all_characters: list[dict[str, Any]],
    ability: dict[str, Any],
    *,
    actor_id: str,
    positions: dict[str, Any],
) -> list[dict[str, Any]]:
    alive = [item for item in all_characters if item.get("hp_current", 0) > 0]
    if _is_area_recharge_ability(ability):
        targets = _area_special_targets(
            alive,
            target_id=target_id,
            ability=ability,
            actor_id=actor_id,
            positions=positions,
        )
        if targets:
            return targets

    if target_id:
        for item in alive:
            if str(item.get("id")) == str(target_id):
                return [item]
    if alive:
        return [min(alive, key=lambda item: item.get("hp_current", 999))]
    return []


def _is_area_recharge_ability(ability: dict[str, Any]) -> bool:
    if ability.get("targets") == "multiple":
        return True
    if ability.get("aoe") is True:
        return True
    text = " ".join(
        str(ability.get(key, ""))
        for key in ("area", "targeting", "description", "extra_effects", "reach_or_range")
    ).lower()
    return any(
        marker in text
        for marker in (
            "cone",
            "line",
            "radius",
            "sphere",
            "cube",
            "each creature",
            "all creatures",
            "area",
        )
    )


def _area_special_targets(
    alive: list[dict[str, Any]],
    *,
    target_id: str | None,
    ability: dict[str, Any],
    actor_id: str,
    positions: dict[str, Any],
) -> list[dict[str, Any]]:
    if not alive:
        return []

    max_targets = _max_area_targets(ability, default=min(4, len(alive)))
    if not positions:
        return alive[:max_targets]

    actor_position = positions.get(str(actor_id))
    ranked = []
    for target in alive:
        target_position = positions.get(str(target.get("id")))
        if not target_position:
            continue
        distance = chebyshev_distance(actor_position, target_position)
        ranked.append((distance, 0 if str(target.get("id")) == str(target_id) else 1, target))

    if not ranked:
        return alive[:max_targets]

    range_tiles = _area_range_tiles(ability)
    template_targets = _template_area_targets(
        ranked,
        target_id=target_id,
        template_type=_area_template_type(ability),
        range_tiles=range_tiles,
        actor_position=actor_position,
        positions=positions,
    )
    if template_targets:
        return template_targets[:max_targets]

    in_range = [item for item in ranked if item[0] <= range_tiles]
    candidates = in_range or ranked
    candidates.sort(key=lambda item: (item[1], item[0], str(item[2].get("id"))))
    return [item[2] for item in candidates[:max_targets]]


def _area_range_tiles(ability: dict[str, Any]) -> int:
    text = " ".join(
        str(ability.get(key, ""))
        for key in ("area", "targeting", "description", "extra_effects", "reach_or_range")
    )
    distances = [int(match) for match in __import__("re").findall(r"(\d+)\s*(?:ft|feet|foot|灏?)", text)]
    if distances:
        return max(1, max(distances) // 5)
    return 6


def _area_template_type(ability: dict[str, Any]) -> str:
    text = " ".join(
        str(ability.get(key, ""))
        for key in ("area", "targeting", "description", "extra_effects", "reach_or_range")
    ).lower()
    if "cone" in text:
        return "cone"
    if "line" in text:
        return "line"
    if any(marker in text for marker in ("radius", "sphere", "burst", "aura")):
        return "radius"
    return "range"


def _template_area_targets(
    ranked: list[tuple[int, int, dict[str, Any]]],
    *,
    target_id: str | None,
    template_type: str,
    range_tiles: int,
    actor_position: dict[str, Any] | None,
    positions: dict[str, Any],
) -> list[dict[str, Any]]:
    if template_type not in {"cone", "line", "radius"} or not actor_position:
        return []

    anchor_position = positions.get(str(target_id)) if target_id else None
    if not anchor_position and ranked:
        anchor_position = positions.get(str(ranked[0][2].get("id")))
    if not anchor_position:
        return []

    selected = []
    for item in ranked:
        if template_type in {"cone", "line"} and item[0] > range_tiles:
            continue
        if _point_in_area_template(
            actor_position=actor_position,
            anchor_position=anchor_position,
            target_position=positions.get(str(item[2].get("id"))),
            template_type=template_type,
            range_tiles=range_tiles,
        ):
            selected.append(item)
    selected.sort(key=lambda item: (item[1], item[0], str(item[2].get("id"))))
    return [item[2] for item in selected]


def _point_in_area_template(
    *,
    actor_position: dict[str, Any],
    anchor_position: dict[str, Any],
    target_position: dict[str, Any] | None,
    template_type: str,
    range_tiles: int,
) -> bool:
    if not target_position:
        return False

    dx = int(target_position.get("x", 0)) - int(actor_position.get("x", 0))
    dy = int(target_position.get("y", 0)) - int(actor_position.get("y", 0))
    distance = max(abs(dx), abs(dy))
    if distance <= 0:
        return False

    if template_type == "radius":
        anchor_dx = int(target_position.get("x", 0)) - int(anchor_position.get("x", 0))
        anchor_dy = int(target_position.get("y", 0)) - int(anchor_position.get("y", 0))
        return max(abs(anchor_dx), abs(anchor_dy)) <= range_tiles

    if distance > range_tiles:
        return False

    direction = _template_direction(actor_position, anchor_position)
    if direction == (0, 0):
        return False

    if template_type == "line":
        return _point_on_line_template(dx, dy, direction, range_tiles)
    if template_type == "cone":
        return _point_in_cone_template(dx, dy, direction, range_tiles)
    return False


def _template_direction(
    actor_position: dict[str, Any],
    anchor_position: dict[str, Any],
) -> tuple[int, int]:
    dx = int(anchor_position.get("x", 0)) - int(actor_position.get("x", 0))
    dy = int(anchor_position.get("y", 0)) - int(actor_position.get("y", 0))
    return (_sign(dx), _sign(dy))


def _point_on_line_template(
    dx: int,
    dy: int,
    direction: tuple[int, int],
    range_tiles: int,
) -> bool:
    step_x, step_y = direction
    if step_x == 0:
        return dx == 0 and _same_direction(dy, step_y) and abs(dy) <= range_tiles
    if step_y == 0:
        return dy == 0 and _same_direction(dx, step_x) and abs(dx) <= range_tiles
    return (
        abs(dx) == abs(dy)
        and _same_direction(dx, step_x)
        and _same_direction(dy, step_y)
        and abs(dx) <= range_tiles
    )


def _point_in_cone_template(
    dx: int,
    dy: int,
    direction: tuple[int, int],
    range_tiles: int,
) -> bool:
    distance = max(abs(dx), abs(dy))
    if distance <= 0 or distance > range_tiles:
        return False

    dir_x, dir_y = direction
    magnitude = math.hypot(dx, dy)
    dir_magnitude = math.hypot(dir_x, dir_y)
    if not magnitude or not dir_magnitude:
        return False
    cosine = ((dx * dir_x) + (dy * dir_y)) / (magnitude * dir_magnitude)
    return cosine >= math.cos(math.radians(45))


def _same_direction(value: int, direction: int) -> bool:
    return direction == 0 or (value != 0 and _sign(value) == direction)


def _sign(value: int) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _max_area_targets(ability: dict[str, Any], *, default: int) -> int:
    for key in ("max_targets", "target_count"):
        value = ability.get(key)
        if value is None:
            continue
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            continue
    return max(1, default)


def _roll_recharge_save(target: dict[str, Any], ability: dict[str, Any]) -> dict[str, Any] | None:
    save_ability = ability.get("saving_throw") or ability.get("save")
    save_dc = ability.get("save_dc")
    if not save_ability or save_dc is None:
        return None
    return roll_saving_throw(target, str(save_ability), int(save_dc))


def _half_on_save(ability: dict[str, Any]) -> bool:
    if "half_on_save" in ability:
        return bool(ability.get("half_on_save"))
    text = f"{ability.get('description', '')} {ability.get('extra_effects', '')}".lower()
    return "half" in text or "save for half" in text or "successful save" in text


def _enemy_target_state(enemy: dict[str, Any]) -> dict[str, Any]:
    hp = enemy.get("hp_current", 0)
    return {
        "target_id": enemy.get("id"),
        "target_name": enemy.get("name", "Enemy"),
        "hp_current": hp,
        "new_hp": hp,
        "conditions": enemy.get("conditions", []),
        "condition_durations": enemy.get("condition_durations", {}),
        "life_state": "dead" if hp <= 0 else "alive",
    }


def _target_summary(target_results: list[dict[str, Any]]) -> str:
    names = [str(result.get("target_name") or result.get("target_id")) for result in target_results]
    if len(names) <= 3:
        return ", ".join(names)
    return f"{', '.join(names[:3])}, and {len(names) - 3} more"


async def _check_party_combat_outcome(db, session, enemies: list[dict[str, Any]], all_characters: list[dict[str, Any]]):
    party_hps = []
    for character in all_characters:
        character_id = character.get("id")
        if not character_id:
            continue
        db_character = await db.get(Character, str(character_id))
        party_hps.append(db_character.hp_current if db_character else int(character.get("hp_current") or 0))
    return svc.check_combat_over(enemies, max(party_hps, default=0))


def _special_narration(
    *,
    actor_name: str,
    ability: dict[str, Any],
    target_name: str,
    damage: int,
    damage_type: str,
    save_detail: dict[str, Any] | None,
    target_results: list[dict[str, Any]] | None = None,
    reason: str = "",
) -> str:
    save_text = ""
    if target_results and len(target_results) > 1:
        failed = sum(1 for result in target_results if not (result.get("save") or {}).get("success"))
        saved = len(target_results) - failed
        save_text = f" {len(target_results)} targets affected"
        if saved or failed:
            save_text += f" ({failed} failed, {saved} succeeded saves)"
        save_text += "."
    elif save_detail:
        outcome = "succeeds" if save_detail.get("success") else "fails"
        save_text = f" {target_name} {outcome} a DC {save_detail.get('dc')} {save_detail.get('ability')} save."
    conditions = [
        str((result.get("condition_result") or {}).get("condition"))
        for result in target_results or []
        if (result.get("condition_result") or {}).get("applied")
    ]
    condition_text = f" Conditions applied: {', '.join(sorted(set(conditions)))}." if conditions else ""
    reason_text = f" ({reason})" if reason else ""
    return (
        f"{actor_name} uses {ability.get('name', 'a special ability')} on {target_name}, "
        f"dealing {damage} {damage_type} damage.{save_text}{condition_text}{reason_text}"
    )


def _normalize_name(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


def _safe_flag_modified(instance: Any, field: str) -> None:
    try:
        flag_modified(instance, field)
    except Exception:
        pass


def _save_turn_state(combat: Any, entity_id: str, turn_state: dict[str, Any]) -> None:
    states = dict(getattr(combat, "turn_states", None) or {})
    states[str(entity_id)] = turn_state
    combat.turn_states = states
    _safe_flag_modified(combat, "turn_states")
