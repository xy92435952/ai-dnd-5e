from __future__ import annotations

import random
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from models import Character
from services.combat_attack_damage_service import apply_attack_damage_to_target
from services.combat_concentration_effect_service import discard_condition_sources
from services.combat_grid_service import chebyshev_distance
from services.combat_service import CombatService
from services.combat_turn_state_service import get_turn_state, save_turn_state
from services.dnd_rules import normalize_conditions, roll_saving_throw


GRID_WIDTH = 20
GRID_HEIGHT = 12
svc = CombatService()
CONFUSION_DIRECTIONS: tuple[tuple[int, int, str], ...] = (
    (0, -1, "north"),
    (1, -1, "north_east"),
    (1, 0, "east"),
    (1, 1, "south_east"),
    (0, 1, "south"),
    (-1, 1, "south_west"),
    (-1, 0, "west"),
    (-1, -1, "north_west"),
)


def is_confused(actor: dict | object | None) -> bool:
    return "confused" in _actor_conditions(actor)


def apply_confusion_turn_start(
    combat,
    entity_id: str,
    actor: dict | object | None,
    *,
    d10_value: int | None = None,
    direction_index: int | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any] | None:
    """Roll and apply the start-of-turn Confusion table to a combat actor."""
    if not is_confused(actor):
        return None

    rng = rng or random
    metadata = _confusion_metadata(actor)
    if d10_value is None:
        d10_value = metadata.get("next_roll") or metadata.get("roll")
    if direction_index is None:
        direction_index = metadata.get("direction_index")
    entity_id = str(entity_id)
    turn_state = get_turn_state(combat, entity_id)
    turn_token = _turn_token(combat, entity_id)
    existing = turn_state.get("confusion_turn")
    if isinstance(existing, dict) and existing.get("turn_token") == turn_token:
        return existing

    roll = _coerce_roll(d10_value, rng)
    outcome = _outcome_for_roll(roll)
    result: dict[str, Any] = {
        "type": "confusion_turn_start",
        "condition": "confused",
        "roll": roll,
        "outcome": outcome,
        "turn_token": turn_token,
        "reaction_blocked": True,
    }

    turn_state["reaction_blocked"] = True
    turn_state["reaction_blocked_reason"] = "confused"
    turn_state["confusion_turn"] = result

    if outcome == "random_move":
        movement = _apply_random_movement(
            combat,
            entity_id,
            turn_state,
            direction_index=direction_index,
            rng=rng,
        )
        result["movement"] = movement
        _spend_turn_control(turn_state)
    elif outcome == "no_action":
        result["action_blocked"] = True
        result["movement_blocked"] = True
        _spend_turn_control(turn_state)
    elif outcome == "random_melee_attack":
        result["action_blocked"] = True
        result["movement_blocked"] = True
        result["forced_action"] = "random_melee_attack"
        result["adjacent_target_ids"] = _adjacent_entity_ids(combat, entity_id)
        forced_target_id = metadata.get("target_id")
        if forced_target_id:
            result["forced_target_id"] = str(forced_target_id)
        target_index = metadata.get("target_index")
        if target_index is not None:
            result["target_index"] = target_index
        _spend_turn_control(turn_state)
    else:
        result["action_blocked"] = False
        result["movement_blocked"] = False

    turn_state["confusion_turn"] = result
    save_turn_state(combat, entity_id, turn_state)
    return result


async def resolve_confusion_random_melee_attack(
    db,
    *,
    session,
    combat,
    entity_id: str,
    actor: dict | object | None,
    enemies: list[dict[str, Any]],
    confusion_turn: dict[str, Any],
    rng: random.Random | None = None,
    combat_service: CombatService = svc,
) -> dict[str, Any] | None:
    """Resolve the Confusion roll 7-8 random melee attack, if applicable."""
    if not confusion_turn or confusion_turn.get("outcome") != "random_melee_attack":
        return None
    if confusion_turn.get("attack"):
        return confusion_turn.get("attack")

    rng = rng or random
    entity_id = str(entity_id)
    candidates = await _adjacent_target_candidates(
        db,
        combat=combat,
        entity_id=entity_id,
        enemies=enemies,
    )
    if not candidates:
        attack_summary = {
            "type": "confusion_random_melee_attack",
            "applied": False,
            "reason": "no_adjacent_target",
            "actor_id": entity_id,
            "actor_name": _actor_name(actor, entity_id),
        }
        _store_confusion_attack(combat, entity_id, confusion_turn, attack_summary)
        return attack_summary

    target = _choose_confusion_target(candidates, confusion_turn, rng)
    metadata = _confusion_metadata(actor)
    actor_derived = _actor_derived(actor)
    target_derived = dict(target["derived"] or {})
    actor_name = _actor_name(actor, entity_id)
    target_name = target["name"]
    actor_derived.setdefault("name", actor_name)
    target_derived.setdefault("name", target_name)
    d20_roller = _fixed_d20_roller(metadata.get("attack_d20"))
    attack_kwargs = {
        "d20_roller": d20_roller,
    } if d20_roller else {}
    attack_result = combat_service.resolve_melee_attack(
        attacker_derived=actor_derived,
        target_derived=target_derived,
        attacker_conditions=_actor_conditions(actor),
        target_conditions=target["conditions"],
        distance=1,
        is_ranged=False,
        **attack_kwargs,
    )

    target_new_hp = target.get("hp_current")
    target_state = None
    concentration_log = None
    if attack_result.attack_roll.get("hit"):
        target_new_hp, concentration_log, target_state = await apply_attack_damage_to_target(
            db,
            session_id=str(session.id),
            enemies=enemies,
            target_id=target["id"],
            target_is_enemy=bool(target["is_enemy"]),
            damage=int(attack_result.damage or 0),
            session=session,
            is_critical=bool(attack_result.attack_roll.get("is_crit")),
            attacker_id=entity_id,
            attacker_is_enemy=_actor_is_enemy(actor, enemies, entity_id),
            is_melee=True,
        )
        if target["is_enemy"]:
            state = session.game_state or {}
            state["enemies"] = enemies
            session.game_state = dict(state)
            _flag_modified(session, "game_state")

    attack_summary = {
        "type": "confusion_random_melee_attack",
        "applied": True,
        "actor_id": entity_id,
        "actor_name": actor_name,
        "target_id": target["id"],
        "target_name": target_name,
        "target_is_enemy": bool(target["is_enemy"]),
        "attack": attack_result.attack_roll,
        "damage": int(attack_result.damage or 0),
        "damage_roll": attack_result.damage_roll,
        "hit": bool(attack_result.attack_roll.get("hit")),
        "target_new_hp": target_new_hp,
        "target_state": target_state,
        "concentration_check": concentration_log.dice_result if concentration_log else None,
    }
    if concentration_log:
        db.add(concentration_log)
    _store_confusion_attack(combat, entity_id, confusion_turn, attack_summary)
    return attack_summary


def resolve_confusion_end_of_turn_save(
    actor: dict | object | None,
    *,
    entity_id: str | None = None,
    actor_name: str | None = None,
    d20_value: int | None = None,
    spell_save_dc: int | None = None,
    save_ability: str | None = None,
) -> dict[str, Any] | None:
    """Resolve Confusion's end-of-turn Wisdom save and clear the condition on success."""
    if not is_confused(actor):
        return None

    metadata = _confusion_metadata(actor)
    d20_override = d20_value if d20_value is not None else metadata.get("end_save_d20")
    resolved_ability = str(save_ability or metadata.get("save_ability") or "wis").strip().lower()
    resolved_dc = _read_int(
        spell_save_dc
        if spell_save_dc is not None
        else metadata.get("save_dc", metadata.get("dc", 13)),
        13,
    )
    save_detail = roll_saving_throw(
        _saving_throw_actor(actor),
        resolved_ability or "wis",
        resolved_dc,
        d20_roller=_fixed_d20_roller(d20_override),
    )
    ended = bool(save_detail.get("success"))
    if ended:
        _remove_confused_condition(actor)

    result = {
        "type": "confusion_end_save",
        "condition": "confused",
        "actor_id": str(entity_id) if entity_id is not None else _actor_id(actor),
        "actor_name": actor_name or _actor_name(actor, str(entity_id or "actor")),
        "save": save_detail,
        "ended": ended,
        "removed_conditions": ["confused"] if ended else [],
        "conditions": _actor_conditions(actor),
        "condition_durations": _condition_durations(actor),
        "target_state": {
            "target_id": str(entity_id) if entity_id is not None else _actor_id(actor),
            "target_name": actor_name or _actor_name(actor, str(entity_id or "actor")),
            "conditions": _actor_conditions(actor),
            "condition_durations": _condition_durations(actor),
            "save": save_detail,
        },
    }
    return result


def build_confusion_turn_log(actor_name: str, result: dict[str, Any] | None) -> str:
    if not result:
        return ""
    roll = result.get("roll")
    outcome = result.get("outcome")
    if outcome == "random_move":
        movement = result.get("movement") or {}
        direction = movement.get("direction_label") or "random"
        steps = int(movement.get("steps") or 0)
        return f"{actor_name} is confused (d10={roll}) and moves {steps} cells {direction}."
    if outcome == "no_action":
        return f"{actor_name} is confused (d10={roll}) and cannot move or act this turn."
    if outcome == "random_melee_attack":
        targets = result.get("adjacent_target_ids") or []
        if targets:
            return f"{actor_name} is confused (d10={roll}) and loses control to a random melee impulse."
        return f"{actor_name} is confused (d10={roll}) but has no adjacent creature to attack."
    return f"{actor_name} is confused (d10={roll}) but can act normally this turn."


def build_confusion_attack_log(actor_name: str, result: dict[str, Any] | None) -> str:
    if not result:
        return ""
    if not result.get("applied"):
        return f"{actor_name}'s confused melee impulse has no adjacent target."
    target_name = result.get("target_name") or "target"
    attack = result.get("attack") or {}
    if result.get("hit"):
        return f"{actor_name}'s confused melee impulse hits {target_name} for {result.get('damage', 0)} damage."
    return f"{actor_name}'s confused melee impulse misses {target_name} ({attack.get('attack_total')} vs AC {attack.get('target_ac')})."


def build_confusion_end_save_log(actor_name: str, result: dict[str, Any] | None) -> str:
    if not result:
        return ""
    save = result.get("save") or {}
    total = save.get("total")
    dc = save.get("dc")
    ability = str(save.get("ability") or "wis").upper()
    outcome = "succeeds" if result.get("ended") else "fails"
    suffix = "and is no longer confused" if result.get("ended") else "and remains confused"
    return f"{actor_name} {outcome} the Confusion end-of-turn {ability} save ({total} vs DC {dc}) {suffix}."


def _actor_conditions(actor: dict | object | None) -> list[str]:
    if not actor:
        return []
    if isinstance(actor, dict):
        return normalize_conditions(actor.get("conditions") or [])
    return normalize_conditions(getattr(actor, "conditions", None) or [])


def _actor_id(actor: dict | object | None) -> str | None:
    if not actor:
        return None
    if isinstance(actor, dict):
        value = actor.get("id") or actor.get("character_id")
    else:
        value = getattr(actor, "id", None)
    return str(value) if value is not None else None


def _actor_derived(actor: dict | object | None) -> dict[str, Any]:
    if not actor:
        return {}
    if isinstance(actor, dict):
        return dict(actor.get("derived") or {})
    return dict(getattr(actor, "derived", None) or {})


def _actor_name(actor: dict | object | None, fallback: str) -> str:
    if isinstance(actor, dict):
        return str(actor.get("name") or fallback)
    return str(getattr(actor, "name", None) or fallback)


def _actor_is_enemy(actor: dict | object | None, enemies: list[dict[str, Any]], entity_id: str) -> bool:
    if isinstance(actor, dict):
        if actor.get("is_enemy") is True:
            return True
        return any(str(enemy.get("id")) == str(entity_id) for enemy in enemies)
    return False


def _condition_durations(actor: dict | object | None) -> dict[str, Any]:
    if not actor:
        return {}
    if isinstance(actor, dict):
        return dict(actor.get("condition_durations") or {})
    return dict(getattr(actor, "condition_durations", None) or {})


def _set_actor_conditions(actor: dict | object | None, conditions: list[str]) -> None:
    if not actor:
        return
    if isinstance(actor, dict):
        actor["conditions"] = conditions
        return
    actor.conditions = conditions
    _flag_modified(actor, "conditions")


def _set_condition_durations(actor: dict | object | None, durations: dict[str, Any]) -> None:
    if not actor:
        return
    if isinstance(actor, dict):
        actor["condition_durations"] = durations
        return
    actor.condition_durations = durations
    _flag_modified(actor, "condition_durations")


def _saving_throw_actor(actor: dict | object | None) -> dict[str, Any]:
    if isinstance(actor, dict):
        return dict(actor)
    return {
        "derived": dict(getattr(actor, "derived", None) or {}),
        "ability_scores": dict(getattr(actor, "ability_scores", None) or {}),
        "conditions": list(getattr(actor, "conditions", None) or []),
        "condition_durations": dict(getattr(actor, "condition_durations", None) or {}),
    }


def _remove_confused_condition(actor: dict | object | None) -> None:
    conditions = [condition for condition in _actor_conditions(actor) if condition != "confused"]
    durations = _condition_durations(actor)
    durations.pop("confused", None)
    for key in (
        "confusion_next_roll",
        "confusion_roll",
        "confusion_direction_index",
        "confusion_target_id",
        "confusion_target_index",
        "confusion_attack_d20",
        "confusion_save_dc",
        "confusion_save_ability",
        "confusion_end_save_d20",
    ):
        durations.pop(key, None)
    _set_actor_conditions(actor, conditions)
    _set_condition_durations(actor, durations)
    discard_condition_sources(actor, "confused")


def _confusion_metadata(actor: dict | object | None) -> dict[str, Any]:
    durations = _condition_durations(actor)
    metadata: dict[str, Any] = {}
    nested = durations.get("confused")
    if isinstance(nested, dict):
        metadata.update(nested)
    for source_key, target_key in (
        ("confusion_next_roll", "next_roll"),
        ("confusion_roll", "roll"),
        ("confusion_direction_index", "direction_index"),
        ("confusion_target_id", "target_id"),
        ("confusion_target_index", "target_index"),
        ("confusion_attack_d20", "attack_d20"),
        ("confusion_save_dc", "save_dc"),
        ("confusion_save_ability", "save_ability"),
        ("confusion_end_save_d20", "end_save_d20"),
    ):
        if source_key in durations:
            metadata[target_key] = durations[source_key]
    return metadata


def _fixed_d20_roller(value: Any):
    if value is None:
        return None
    try:
        d20 = min(20, max(1, int(value)))
    except (TypeError, ValueError):
        return None

    def roller(_dice: str) -> dict[str, Any]:
        return {"rolls": [d20], "total": d20}

    return roller


def _coerce_roll(d10_value: int | None, rng: random.Random) -> int:
    if d10_value is None:
        return rng.randint(1, 10)
    try:
        return min(10, max(1, int(d10_value)))
    except (TypeError, ValueError):
        return rng.randint(1, 10)


def _outcome_for_roll(roll: int) -> str:
    if roll == 1:
        return "random_move"
    if 2 <= roll <= 6:
        return "no_action"
    if 7 <= roll <= 8:
        return "random_melee_attack"
    return "act_normally"


def _turn_token(combat, entity_id: str) -> str:
    return f"{getattr(combat, 'round_number', 1) or 1}:{getattr(combat, 'current_turn_index', 0) or 0}:{entity_id}"


def _spend_turn_control(turn_state: dict[str, Any]) -> None:
    movement_max = _read_int(turn_state.get("movement_max"), 0)
    turn_state["action_used"] = True
    turn_state["bonus_action_used"] = True
    turn_state["movement_used"] = max(_read_int(turn_state.get("movement_used"), 0), movement_max)


def _apply_random_movement(
    combat,
    entity_id: str,
    turn_state: dict[str, Any],
    *,
    direction_index: int | None,
    rng: random.Random,
) -> dict[str, Any]:
    positions = dict(getattr(combat, "entity_positions", None) or {})
    start = positions.get(entity_id)
    if not isinstance(start, dict):
        return {"applied": False, "reason": "missing_position", "steps": 0}

    index = _direction_index(direction_index, rng)
    dx, dy, label = CONFUSION_DIRECTIONS[index]
    movement_max = _read_int(turn_state.get("movement_max"), 0)
    occupied = {
        (int(pos.get("x", -999)), int(pos.get("y", -999)))
        for other_id, pos in positions.items()
        if str(other_id) != entity_id and isinstance(pos, dict)
    }
    x = _read_int(start.get("x"), 0)
    y = _read_int(start.get("y"), 0)
    path: list[dict[str, int]] = []

    for _step in range(max(0, movement_max)):
        nx = x + dx
        ny = y + dy
        if not (0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT):
            break
        if (nx, ny) in occupied:
            break
        x, y = nx, ny
        path.append({"x": x, "y": y})

    destination = {"x": x, "y": y}
    positions[entity_id] = destination
    combat.entity_positions = positions
    _flag_modified(combat, "entity_positions")
    return {
        "applied": bool(path),
        "direction_index": index,
        "direction_label": label,
        "from": {"x": _read_int(start.get("x"), 0), "y": _read_int(start.get("y"), 0)},
        "to": destination,
        "steps": len(path),
        "path": path,
    }


def _direction_index(direction_index: int | None, rng: random.Random) -> int:
    if direction_index is None:
        return rng.randrange(len(CONFUSION_DIRECTIONS))
    try:
        return int(direction_index) % len(CONFUSION_DIRECTIONS)
    except (TypeError, ValueError):
        return rng.randrange(len(CONFUSION_DIRECTIONS))


def _adjacent_entity_ids(combat, entity_id: str) -> list[str]:
    positions = dict(getattr(combat, "entity_positions", None) or {})
    actor_pos = positions.get(entity_id)
    if not isinstance(actor_pos, dict):
        return []
    ax = _read_int(actor_pos.get("x"), 0)
    ay = _read_int(actor_pos.get("y"), 0)
    adjacent: list[str] = []
    for other_id, pos in positions.items():
        if str(other_id) == entity_id or not isinstance(pos, dict):
            continue
        distance = max(
            abs(ax - _read_int(pos.get("x"), 0)),
            abs(ay - _read_int(pos.get("y"), 0)),
        )
        if distance <= 1:
            adjacent.append(str(other_id))
    return adjacent


async def _adjacent_target_candidates(
    db,
    *,
    combat,
    entity_id: str,
    enemies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    positions = dict(getattr(combat, "entity_positions", None) or {})
    actor_pos = positions.get(str(entity_id))
    if not isinstance(actor_pos, dict):
        return []

    enemy_by_id = {str(enemy.get("id")): enemy for enemy in enemies if enemy.get("id")}
    candidates: list[dict[str, Any]] = []
    for other_id, pos in positions.items():
        other_id = str(other_id)
        if other_id == str(entity_id) or not isinstance(pos, dict):
            continue
        if chebyshev_distance(actor_pos, pos) > 1:
            continue

        enemy = enemy_by_id.get(other_id)
        if enemy is not None:
            if int(enemy.get("hp_current", 0) or 0) <= 0:
                continue
            candidates.append({
                "id": other_id,
                "name": enemy.get("name") or other_id,
                "is_enemy": True,
                "hp_current": enemy.get("hp_current"),
                "derived": dict(enemy.get("derived") or {}),
                "conditions": normalize_conditions(enemy.get("conditions") or []),
            })
            continue

        character = await db.get(Character, other_id)
        if not character or int(getattr(character, "hp_current", 0) or 0) <= 0:
            continue
        candidates.append({
            "id": other_id,
            "name": character.name,
            "is_enemy": False,
            "hp_current": character.hp_current,
            "derived": dict(character.derived or {}),
            "conditions": normalize_conditions(character.conditions or []),
        })

    candidates.sort(key=lambda item: (item["name"], item["id"]))
    return candidates


def _choose_confusion_target(
    candidates: list[dict[str, Any]],
    confusion_turn: dict[str, Any],
    rng: random.Random,
) -> dict[str, Any]:
    forced_target_id = str(confusion_turn.get("forced_target_id") or "")
    if forced_target_id:
        forced = next((candidate for candidate in candidates if candidate["id"] == forced_target_id), None)
        if forced:
            return forced
    try:
        raw_index = confusion_turn.get("target_index")
        if raw_index is None:
            return candidates[rng.randrange(len(candidates))]
        index = int(raw_index)
    except (TypeError, ValueError):
        index = rng.randrange(len(candidates))
    return candidates[index % len(candidates)]


def _store_confusion_attack(
    combat,
    entity_id: str,
    confusion_turn: dict[str, Any],
    attack_summary: dict[str, Any],
) -> None:
    turn_state = get_turn_state(combat, entity_id)
    stored = dict(turn_state.get("confusion_turn") or confusion_turn or {})
    stored["attack"] = attack_summary
    turn_state["confusion_turn"] = stored
    save_turn_state(combat, entity_id, turn_state)
    confusion_turn["attack"] = attack_summary


def _read_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _flag_modified(model: Any, key: str) -> None:
    try:
        flag_modified(model, key)
    except Exception:
        pass
