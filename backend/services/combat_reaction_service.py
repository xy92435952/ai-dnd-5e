from __future__ import annotations

from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from services.dnd_rules import (
    get_effective_hp_max,
    get_temporary_hp,
    get_wild_shape_hp,
    roll_saving_throw,
)


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
            "hp_before": event.get("hp_before"),
            "hp_after": event.get("hp_after"),
            "hit": bool(event.get("hit", True)),
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
