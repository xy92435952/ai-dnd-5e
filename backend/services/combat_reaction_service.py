from __future__ import annotations

from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from services.combat_damage_service import normalize_damage_type
from services.combat_tactical_service import terrain_kind
from services.dnd_rules import (
    _normalize_class,
    get_effective_hp_max,
    get_temporary_hp,
    get_wild_shape_hp,
    normalize_conditions,
    roll_saving_throw,
)


SLOT_LEVELS: dict[str, int] = {
    "1st": 1,
    "2nd": 2,
    "3rd": 3,
    "4th": 4,
    "5th": 5,
    "6th": 6,
    "7th": 7,
    "8th": 8,
    "9th": 9,
}

COUNTERSPELL_NAMES = {
    "counterspell",
    "counter-spell",
    "counter spell",
    "Counterspell",
    "Counter Spell",
    "反制法术",
    "反制法術",
}

COUNTERSPELL_RANGE_SQUARES = 12
SIGHT_BLOCKING_TERRAIN = {"wall", "opaque", "blocking", "blocker", "total_cover"}

ABSORB_ELEMENTS_NAMES = {
    "absorb elements",
    "absorb_elements",
    "Absorb Elements",
    "吸收元素",
}
ABSORB_ELEMENTS_DAMAGE_TYPES = {"acid", "cold", "fire", "lightning", "thunder"}


class CuttingWordsError(ValueError):
    pass


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _snapshot_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return dict(value)
    return None


def _snapshot_list(value: Any) -> list[Any] | None:
    if isinstance(value, list):
        return list(value)
    return None


def _flag_json_modified(character: Any, field: str) -> None:
    try:
        flag_modified(character, field)
    except Exception:
        pass


def _coerce_non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _parse_die_faces(die: Any) -> int:
    text = str(die or "").strip().lower()
    if text.startswith("d"):
        text = text[1:]
    try:
        faces = int(text)
    except (TypeError, ValueError) as exc:
        raise CuttingWordsError("Invalid Cutting Words die.") from exc
    if faces not in {6, 8, 10, 12}:
        raise CuttingWordsError("Invalid Cutting Words die.")
    return faces


def _normalize_cutting_words_roll(value: Any, die_faces: int) -> int:
    try:
        roll = int(value)
    except (TypeError, ValueError) as exc:
        raise CuttingWordsError("cutting_words_roll must be an integer.") from exc
    if roll < 1 or roll > die_faces:
        raise CuttingWordsError(f"cutting_words_roll must be between 1 and {die_faces}.")
    return roll


def get_cutting_words_die(character: Any) -> str | None:
    if not character_can_use_cutting_words(character):
        return None
    derived = dict(getattr(character, "derived", None) or {})
    subclass_effects = dict(derived.get("subclass_effects") or {})
    die = str(subclass_effects.get("inspiration_die") or "d6").strip().lower()
    try:
        _parse_die_faces(die)
    except CuttingWordsError:
        return "d6"
    return die


def character_can_use_cutting_words(character: Any) -> bool:
    if not character:
        return False
    if _normalize_class(getattr(character, "char_class", "")) != "Bard":
        return False
    if int(getattr(character, "level", 1) or 1) < 3:
        return False
    resources = dict(getattr(character, "class_resources", None) or {})
    if _coerce_non_negative_int(resources.get("bardic_inspiration_remaining", 0)) <= 0:
        return False

    derived = dict(getattr(character, "derived", None) or {})
    subclass_effects = dict(derived.get("subclass_effects") or {})
    if subclass_effects.get("cutting_words") or subclass_effects.get("lore_bard"):
        return True
    subclass = str(getattr(character, "subclass", "") or "").strip().lower()
    return "lore" in subclass or "知识" in subclass


def spend_cutting_words_resource(character: Any, *, cutting_words_roll: Any) -> dict[str, Any]:
    die = get_cutting_words_die(character)
    if not die:
        raise CuttingWordsError("Cutting Words is not available.")
    faces = _parse_die_faces(die)
    roll = _normalize_cutting_words_roll(cutting_words_roll, faces)
    resources = dict(getattr(character, "class_resources", None) or {})
    remaining = _coerce_non_negative_int(resources.get("bardic_inspiration_remaining", 0))
    if remaining <= 0:
        raise CuttingWordsError("No Bardic Inspiration uses remaining.")
    resources["bardic_inspiration_remaining"] = remaining - 1
    character.class_resources = resources
    _flag_json_modified(character, "class_resources")
    return {
        "type": "cutting_words",
        "spent": True,
        "die": die,
        "roll": roll,
        "uses_remaining": remaining - 1,
    }


def calculate_cutting_words_prevention(
    pending_reaction: dict[str, Any] | None,
    *,
    cutting_words_roll: int,
) -> dict[str, Any]:
    events = list((pending_reaction or {}).get("events") or [])
    event = next(
        (
            item for item in events
            if bool(item.get("hit", True)) and _coerce_non_negative_int(item.get("damage", 0)) > 0
        ),
        None,
    )
    if not event:
        return {
            "attack_total_before": None,
            "attack_total_after": None,
            "target_ac": None,
            "blocked_attack": False,
            "hit_after": True,
            "original_damage": 0,
            "reduced_damage": 0,
            "damage_prevented": 0,
        }

    attack_total_before = int(event.get("attack_total") or 0)
    target_ac = int(event.get("target_ac") or 10)
    attack_total_after = attack_total_before - int(cutting_words_roll)
    is_crit = bool(event.get("is_crit"))
    blocked = (not is_crit) and attack_total_after < target_ac
    original_damage = _coerce_non_negative_int(event.get("damage", 0))
    reduced_damage = 0 if blocked else original_damage
    return {
        "attack_total_before": attack_total_before,
        "attack_total_after": attack_total_after,
        "target_ac": target_ac,
        "blocked_attack": blocked,
        "hit_after": not blocked,
        "original_damage": original_damage,
        "reduced_damage": reduced_damage,
        "damage_prevented": original_damage - reduced_damage,
    }


def calculate_cutting_words_damage_prevention(
    pending_reaction: dict[str, Any] | None,
    *,
    cutting_words_roll: int,
) -> dict[str, Any]:
    for index, event in enumerate((pending_reaction or {}).get("events") or []):
        original_damage = _coerce_non_negative_int(event.get("damage", 0))
        if not event.get("hit", True) or original_damage <= 0:
            continue
        roll = max(0, int(cutting_words_roll or 0))
        reduced_damage = max(0, original_damage - roll)
        return {
            "damage_type": normalize_damage_type(event.get("damage_type")) or None,
            "original_damage": original_damage,
            "reduced_damage": reduced_damage,
            "damage_roll_before": original_damage,
            "damage_roll_after": reduced_damage,
            "damage_prevented": original_damage - reduced_damage,
            "affected_attack_index": index,
        }
    return {
        "damage_type": None,
        "original_damage": 0,
        "reduced_damage": 0,
        "damage_roll_before": 0,
        "damage_roll_after": 0,
        "damage_prevented": 0,
        "affected_attack_index": None,
    }


def calculate_cutting_words_ability_check_prevention(
    check_roll: dict[str, Any] | None,
    *,
    cutting_words_roll: int,
) -> dict[str, Any]:
    total_before = int((check_roll or {}).get("total") or 0)
    roll = max(0, int(cutting_words_roll or 0))
    total_after = total_before - roll
    return {
        "check_total_before": total_before,
        "check_total_after": total_after,
        "check_prevented": roll,
    }


def build_pending_attack_reaction(
    *,
    attacker_id: str,
    attacker_name: str,
    target_id: str,
    attack_events: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """Capture server-side attack facts for reactions resolved after AI damage."""
    normalized_events = []
    for event in attack_events or []:
        damage = int(event.get("damage") or 0)
        if damage <= 0:
            continue
        normalized = {
            "attack_total": int(event.get("attack_total") or 0),
            "target_ac": int(event.get("target_ac") or 10),
            "damage": damage,
            "damage_type": normalize_damage_type(event.get("damage_type")) or None,
            "hp_before": event.get("hp_before"),
            "hp_after": event.get("hp_after"),
            "hit": bool(event.get("hit", True)),
            "is_crit": bool(event.get("is_crit", False)),
            "is_fumble": bool(event.get("is_fumble", False)),
        }
        for key in (
            "temporary_hp_before",
            "temporary_hp_after",
            "wild_shape_hp_before",
            "wild_shape_hp_after",
        ):
            value = _optional_int(event.get(key))
            if value is not None:
                normalized[key] = value
        for key in ("class_resources_before", "condition_durations_before"):
            value = _snapshot_dict(event.get(key))
            if value is not None:
                normalized[key] = value
        conditions_before = _snapshot_list(event.get("conditions_before"))
        if conditions_before is not None:
            normalized["conditions_before"] = conditions_before
        normalized_events.append(normalized)

    if not normalized_events:
        return None

    hp_before_values = [
        _optional_int(event.get("hp_before"))
        for event in normalized_events
        if _optional_int(event.get("hp_before")) is not None
    ]
    temporary_hp_before_values = [
        event["temporary_hp_before"]
        for event in normalized_events
        if "temporary_hp_before" in event
    ]
    wild_shape_hp_before_values = [
        event["wild_shape_hp_before"]
        for event in normalized_events
        if "wild_shape_hp_before" in event
    ]
    first_resource_snapshot = next(
        (event["class_resources_before"] for event in normalized_events if "class_resources_before" in event),
        None,
    )
    first_conditions_snapshot = next(
        (event["conditions_before"] for event in normalized_events if "conditions_before" in event),
        None,
    )
    first_durations_snapshot = next(
        (
            event["condition_durations_before"]
            for event in normalized_events
            if "condition_durations_before" in event
        ),
        None,
    )

    return {
        "trigger": "incoming_attack",
        "attacker_id": str(attacker_id),
        "attacker_name": attacker_name,
        "target_id": str(target_id),
        "incoming_damage": sum(event["damage"] for event in normalized_events),
        "target_hp_before_damage": max(hp_before_values) if hp_before_values else None,
        "target_temporary_hp_before_damage": (
            max(temporary_hp_before_values) if temporary_hp_before_values else None
        ),
        "target_wild_shape_hp_before_damage": (
            max(wild_shape_hp_before_values) if wild_shape_hp_before_values else None
        ),
        "target_class_resources_before_damage": first_resource_snapshot,
        "target_conditions_before_damage": first_conditions_snapshot,
        "target_condition_durations_before_damage": first_durations_snapshot,
        "events": normalized_events,
    }


def _normalized_spell_key(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


def _character_spells(character: Any) -> set[str]:
    known = set(getattr(character, "known_spells", None) or [])
    known |= set(getattr(character, "prepared_spells", None) or [])
    return {_normalized_spell_key(spell) for spell in known}


def character_knows_counterspell(character: Any) -> bool:
    normalized_known = _character_spells(character)
    return any(_normalized_spell_key(name) in normalized_known for name in COUNTERSPELL_NAMES)


def character_knows_absorb_elements(character: Any) -> bool:
    normalized_known = _character_spells(character)
    return any(_normalized_spell_key(name) in normalized_known for name in ABSORB_ELEMENTS_NAMES)


def choose_counterspell_slot(
    spell_slots: dict[str, Any] | None,
    countered_spell_level: int,
) -> tuple[str, int] | None:
    """Choose the lowest useful Counterspell slot, preferring automatic counters."""
    slots = dict(spell_slots or {})
    target_level = max(int(countered_spell_level or 0), 3)
    available = [
        (key, level)
        for key, level in SLOT_LEVELS.items()
        if level >= 3 and int(slots.get(key) or 0) > 0
    ]
    if not available:
        return None

    auto_slots = [(key, level) for key, level in available if level >= target_level]
    if auto_slots:
        return min(auto_slots, key=lambda item: item[1])
    return min(available, key=lambda item: item[1])


def choose_absorb_elements_slot(spell_slots: dict[str, Any] | None) -> tuple[str, int] | None:
    slots = dict(spell_slots or {})
    available = [
        (key, level)
        for key, level in SLOT_LEVELS.items()
        if level >= 1 and int(slots.get(key) or 0) > 0
    ]
    if not available:
        return None
    return min(available, key=lambda item: item[1])


def build_pending_spell_reaction(
    *,
    caster_id: str,
    caster_name: str,
    reactor_id: str,
    spell_name: str,
    spell_level: int,
    spell_target_id: str | None,
    decision: dict[str, Any],
    decided_reason: str,
) -> dict[str, Any]:
    return {
        "trigger": "spell_cast",
        "caster_id": str(caster_id),
        "caster_name": caster_name,
        "reactor_id": str(reactor_id),
        "spell_name": spell_name,
        "spell_level": int(spell_level or 0),
        "spell_target_id": str(spell_target_id) if spell_target_id is not None else None,
        "decision": dict(decision or {}),
        "decided_reason": decided_reason or "",
    }


def _position(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if "x" not in value or "y" not in value:
        return None
    return value


def _distance_squares(pos_a: dict[str, Any], pos_b: dict[str, Any]) -> int:
    return max(
        abs(int(pos_a.get("x", 0)) - int(pos_b.get("x", 0))),
        abs(int(pos_a.get("y", 0)) - int(pos_b.get("y", 0))),
    )


def _line_cells_between(pos_a: dict[str, Any], pos_b: dict[str, Any]) -> list[str]:
    ax, ay = int(pos_a.get("x", 0)), int(pos_a.get("y", 0))
    bx, by = int(pos_b.get("x", 0)), int(pos_b.get("y", 0))
    dx = bx - ax
    dy = by - ay
    steps = max(abs(dx), abs(dy))
    if steps <= 1:
        return []

    cells = []
    for step in range(1, steps):
        cx = ax + round(dx * step / steps)
        cy = ay + round(dy * step / steps)
        cells.append(f"{cx}_{cy}")
    return cells


def _conditions(value: Any) -> list[str]:
    if isinstance(value, dict):
        raw = value.get("conditions") or []
    else:
        raw = getattr(value, "conditions", None) or []
    return normalize_conditions(raw)


def resolve_counterspell_eligibility(
    *,
    reactor: Any,
    caster_id: str | None,
    combat: Any | None = None,
    caster_conditions: list[str] | None = None,
    range_squares: int = COUNTERSPELL_RANGE_SQUARES,
) -> dict[str, Any]:
    """Return whether a reactor can see a spellcaster within Counterspell range."""
    result = {
        "can_counterspell": True,
        "reason": None,
        "distance_squares": None,
        "distance_ft": None,
        "range_squares": int(range_squares),
        "range_ft": int(range_squares) * 5,
        "visible": True,
    }
    if not reactor or not caster_id:
        result.update({
            "can_counterspell": False,
            "reason": "missing_reactor_or_caster",
        })
        return result

    reactor_conditions = _conditions(reactor)
    normalized_caster_conditions = normalize_conditions(caster_conditions or [])
    if "blinded" in reactor_conditions:
        result.update({
            "can_counterspell": False,
            "reason": "reactor_blinded",
            "visible": False,
        })
        return result
    if {"invisible", "hidden"} & set(normalized_caster_conditions):
        result.update({
            "can_counterspell": False,
            "reason": "caster_not_visible",
            "visible": False,
        })
        return result

    positions = dict(getattr(combat, "entity_positions", None) or {}) if combat else {}
    reactor_pos = _position(positions.get(str(getattr(reactor, "id", ""))))
    caster_pos = _position(positions.get(str(caster_id)))
    if not reactor_pos or not caster_pos:
        return result

    distance = _distance_squares(reactor_pos, caster_pos)
    result["distance_squares"] = distance
    result["distance_ft"] = distance * 5
    if distance > int(range_squares):
        result.update({
            "can_counterspell": False,
            "reason": "out_of_range",
        })
        return result

    grid_data = dict(getattr(combat, "grid_data", None) or {})
    for cell in _line_cells_between(reactor_pos, caster_pos):
        if terrain_kind(grid_data.get(cell, "")) in SIGHT_BLOCKING_TERRAIN:
            result.update({
                "can_counterspell": False,
                "reason": "caster_not_visible",
                "visible": False,
            })
            return result

    return result


def calculate_counterspell_result(
    *,
    countered_spell_level: int,
    counterspell_slot_level: int,
    caster_derived: dict[str, Any] | None,
    roll_dice_func,
) -> dict[str, Any]:
    """Resolve the DnD 5e Counterspell check for spells above the slot used."""
    spell_level = int(countered_spell_level or 0)
    slot_level = int(counterspell_slot_level or 3)
    if spell_level <= slot_level:
        return {
            "success": True,
            "automatic": True,
            "dc": None,
            "d20": None,
            "modifier": 0,
            "total": None,
        }

    derived = caster_derived or {}
    spell_ability = derived.get("spell_ability")
    modifier = 0
    if spell_ability:
        modifier = int((derived.get("ability_modifiers") or {}).get(spell_ability, 0) or 0)
    d20 = int((roll_dice_func("1d20").get("rolls") or [0])[0])
    dc = 10 + spell_level
    total = d20 + modifier
    return {
        "success": total >= dc,
        "automatic": False,
        "dc": dc,
        "d20": d20,
        "modifier": modifier,
        "total": total,
    }


def calculate_shield_prevention(pending_reaction: dict[str, Any] | None) -> dict[str, Any]:
    """Return how much already-applied damage Shield turns back into a miss."""
    events = (pending_reaction or {}).get("events") or []
    blocked = [
        event
        for event in events
        if event.get("hit") and int(event.get("attack_total") or 0) < int(event.get("target_ac") or 10) + 5
    ]
    prevented = sum(int(event.get("damage") or 0) for event in blocked)
    return {
        "damage_prevented": prevented,
        "blocked_attacks": len(blocked),
    }


def calculate_uncanny_dodge_prevention(pending_reaction: dict[str, Any] | None) -> dict[str, Any]:
    """Return the damage prevented by halving the first qualifying attack."""
    for event in (pending_reaction or {}).get("events") or []:
        damage = int(event.get("damage") or 0)
        if event.get("hit") and damage > 0:
            reduced_damage = damage // 2
            return {
                "original_damage": damage,
                "reduced_damage": reduced_damage,
                "damage_prevented": damage - reduced_damage,
            }
    return {
        "original_damage": 0,
        "reduced_damage": 0,
        "damage_prevented": 0,
    }


def calculate_absorb_elements_prevention(pending_reaction: dict[str, Any] | None) -> dict[str, Any]:
    """Return the damage prevented by Absorb Elements on matching elemental damage."""
    for index, event in enumerate((pending_reaction or {}).get("events") or []):
        damage = int(event.get("damage") or 0)
        damage_type = normalize_damage_type(event.get("damage_type"))
        if not event.get("hit") or damage <= 0 or damage_type not in ABSORB_ELEMENTS_DAMAGE_TYPES:
            continue
        reduced_damage = damage // 2
        return {
            "damage_type": damage_type,
            "original_damage": damage,
            "reduced_damage": reduced_damage,
            "damage_prevented": damage - reduced_damage,
            "affected_attack_index": index,
        }
    return {
        "damage_type": None,
        "original_damage": 0,
        "reduced_damage": 0,
        "damage_prevented": 0,
        "affected_attack_index": None,
    }


def apply_absorb_elements_state(character: Any, damage_type: str, slot_level: int) -> dict[str, Any]:
    """Track Absorb Elements resistance and its next-melee-hit damage rider."""
    normalized_type = normalize_damage_type(damage_type)
    level = max(1, int(slot_level or 1))
    resources = dict(getattr(character, "class_resources", None) or {})
    resources["absorb_elements"] = {
        "damage_type": normalized_type,
        "damage_dice": f"{level}d6",
        "slot_level": level,
    }
    character.class_resources = resources
    _flag_json_modified(character, "class_resources")

    resistance_condition = f"{normalized_type}_resistance"
    conditions = list(getattr(character, "conditions", None) or [])
    already_resistant = resistance_condition in conditions
    if resistance_condition not in conditions:
        conditions.append(resistance_condition)
    character.conditions = conditions
    _flag_json_modified(character, "conditions")

    durations = dict(getattr(character, "condition_durations", None) or {})
    if not already_resistant:
        durations[resistance_condition] = 1
        character.condition_durations = durations
        _flag_json_modified(character, "condition_durations")
    elif resistance_condition in durations:
        durations[resistance_condition] = max(int(durations.get(resistance_condition) or 0), 1)
        character.condition_durations = durations
        _flag_json_modified(character, "condition_durations")

    return {
        "damage_type": normalized_type,
        "damage_dice": f"{level}d6",
        "slot_level": level,
        "resistance_condition": resistance_condition,
    }


def calculate_reaction_save(
    target_derived: dict[str, Any] | None,
    *,
    ability: str,
    dc: int,
    d20: int,
    conditions: list[str] | None = None,
    condition_durations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve a saving throw detail for reaction spells such as Hellish Rebuke."""
    return roll_saving_throw(
        {
            "derived": target_derived or {},
            "conditions": conditions or [],
            "condition_durations": condition_durations or {},
        },
        ability,
        int(dc),
        d20_roller=lambda _expr: {"rolls": [int(d20)], "total": int(d20)},
    )


def calculate_hellish_rebuke_damage(base_damage: int, save_detail: dict[str, Any] | None) -> dict[str, int | bool]:
    """Hellish Rebuke deals half fire damage on a successful DEX save."""
    rolled_damage = max(int(base_damage or 0), 0)
    saved = bool((save_detail or {}).get("success"))
    damage_dealt = rolled_damage // 2 if saved else rolled_damage
    return {
        "rolled_damage": rolled_damage,
        "damage_dealt": damage_dealt,
        "save_success": saved,
    }


def _restore_temporary_hp_snapshot(
    character: Any,
    *,
    amount: int,
    pending_reaction: dict[str, Any] | None,
) -> None:
    snapshot = _snapshot_dict((pending_reaction or {}).get("target_class_resources_before_damage")) or {}
    resources = dict(getattr(character, "class_resources", None) or {})
    resources["temporary_hp"] = amount
    resources.pop("temp_hp", None)
    source = snapshot.get("temporary_hp_source", resources.get("temporary_hp_source", "generic"))
    resources["temporary_hp_source"] = source
    for key in (
        "armor_of_agathys_active",
        "armor_of_agathys_damage",
        "armor_of_agathys_spell_level",
    ):
        if key in snapshot:
            resources[key] = snapshot[key]
    character.class_resources = resources
    _flag_json_modified(character, "class_resources")

    if source == "armor_of_agathys":
        before_conditions = _snapshot_list(
            (pending_reaction or {}).get("target_conditions_before_damage")
        ) or []
        if "armor_of_agathys" in before_conditions:
            conditions = list(getattr(character, "conditions", None) or [])
            if "armor_of_agathys" not in conditions:
                conditions.append("armor_of_agathys")
            character.conditions = conditions
            _flag_json_modified(character, "conditions")

        before_durations = _snapshot_dict(
            (pending_reaction or {}).get("target_condition_durations_before_damage")
        ) or {}
        if "armor_of_agathys" in before_durations:
            durations = dict(getattr(character, "condition_durations", None) or {})
            durations["armor_of_agathys"] = before_durations["armor_of_agathys"]
            character.condition_durations = durations
            _flag_json_modified(character, "condition_durations")


def _restore_wild_shape_hp_snapshot(
    character: Any,
    *,
    amount: int,
    pending_reaction: dict[str, Any] | None,
) -> None:
    snapshot = _snapshot_dict((pending_reaction or {}).get("target_class_resources_before_damage")) or {}
    resources = dict(getattr(character, "class_resources", None) or {})
    active_form = snapshot.get("wild_shape_active") or resources.get("wild_shape_active")
    if active_form and amount > 0:
        resources["wild_shape_active"] = active_form
        resources["wild_shape_hp"] = amount
    character.class_resources = resources
    _flag_json_modified(character, "class_resources")


def restore_prevented_damage(character, pending_reaction: dict[str, Any] | None, damage_prevented: int) -> dict[str, int]:
    """Retroactively restore HP without exceeding the pre-attack HP snapshot."""
    before_hp = int(character.hp_current or 0)
    before_temporary_hp = get_temporary_hp(character)
    before_wild_shape_hp = get_wild_shape_hp(character)
    hp_max = get_effective_hp_max(character, (character.derived or {}).get("hp_max", before_hp))
    pre_attack_cap = (pending_reaction or {}).get("target_hp_before_damage")
    if not isinstance(pre_attack_cap, int):
        pre_attack_cap = hp_max
    cap = min(hp_max, pre_attack_cap)
    remaining_restore = max(int(damage_prevented or 0), 0)

    hp_restored = min(max(0, cap - before_hp), remaining_restore)
    after_hp = before_hp + hp_restored
    character.hp_current = after_hp

    if after_hp > 0 and pre_attack_cap > 0:
        if getattr(character, "death_saves", None) is not None:
            character.death_saves = None
        conditions = list(getattr(character, "conditions", None) or [])
        if "unconscious" in conditions:
            character.conditions = [condition for condition in conditions if condition != "unconscious"]
            _flag_json_modified(character, "conditions")

    remaining_restore -= hp_restored

    temporary_hp_restored = 0
    temporary_hp_cap = _optional_int(
        (pending_reaction or {}).get("target_temporary_hp_before_damage")
    )
    if remaining_restore > 0 and temporary_hp_cap is not None:
        temporary_hp_restored = min(
            max(0, temporary_hp_cap - before_temporary_hp),
            remaining_restore,
        )
        if temporary_hp_restored > 0:
            _restore_temporary_hp_snapshot(
                character,
                amount=before_temporary_hp + temporary_hp_restored,
                pending_reaction=pending_reaction,
            )
            remaining_restore -= temporary_hp_restored

    wild_shape_hp_restored = 0
    wild_shape_hp_cap = _optional_int(
        (pending_reaction or {}).get("target_wild_shape_hp_before_damage")
    )
    if remaining_restore > 0 and wild_shape_hp_cap is not None:
        wild_shape_hp_restored = min(
            max(0, wild_shape_hp_cap - before_wild_shape_hp),
            remaining_restore,
        )
        if wild_shape_hp_restored > 0:
            _restore_wild_shape_hp_snapshot(
                character,
                amount=before_wild_shape_hp + wild_shape_hp_restored,
                pending_reaction=pending_reaction,
            )

    result = {
        "hp_before_reaction": before_hp,
        "hp_after_reaction": after_hp,
        "hp_restored": hp_restored,
    }
    if temporary_hp_cap is not None or before_temporary_hp > 0:
        result.update({
            "temporary_hp_before_reaction": before_temporary_hp,
            "temporary_hp_after_reaction": get_temporary_hp(character),
            "temporary_hp_restored": temporary_hp_restored,
        })
    if wild_shape_hp_cap is not None or before_wild_shape_hp > 0:
        result.update({
            "wild_shape_hp_before_reaction": before_wild_shape_hp,
            "wild_shape_hp_after_reaction": get_wild_shape_hp(character),
            "wild_shape_hp_restored": wild_shape_hp_restored,
        })
    return result
