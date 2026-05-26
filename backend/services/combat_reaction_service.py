from __future__ import annotations

from typing import Any

from services.dnd_rules import get_effective_hp_max


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
        normalized_events.append({
            "attack_total": int(event.get("attack_total") or 0),
            "target_ac": int(event.get("target_ac") or 10),
            "damage": damage,
            "hp_before": event.get("hp_before"),
            "hp_after": event.get("hp_after"),
            "hit": bool(event.get("hit", True)),
        })

    if not normalized_events:
        return None

    hp_before_values = [
        event.get("hp_before")
        for event in normalized_events
        if isinstance(event.get("hp_before"), int)
    ]

    return {
        "trigger": "incoming_attack",
        "attacker_id": str(attacker_id),
        "attacker_name": attacker_name,
        "target_id": str(target_id),
        "incoming_damage": sum(event["damage"] for event in normalized_events),
        "target_hp_before_damage": max(hp_before_values) if hp_before_values else None,
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
) -> dict[str, Any]:
    """Resolve a saving throw detail for reaction spells such as Hellish Rebuke."""
    derived = target_derived or {}
    saves = derived.get("saving_throws", {}) or {}
    modifiers = derived.get("ability_modifiers", {}) or {}
    modifier = int(saves.get(ability, modifiers.get(ability, 0)) or 0)
    total = int(d20) + modifier
    return {
        "ability": ability,
        "dc": int(dc),
        "d20": int(d20),
        "modifier": modifier,
        "total": total,
        "success": total >= int(dc),
    }


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


def restore_prevented_damage(character, pending_reaction: dict[str, Any] | None, damage_prevented: int) -> dict[str, int]:
    """Retroactively restore HP without exceeding the pre-attack HP snapshot."""
    before_hp = int(character.hp_current or 0)
    hp_max = get_effective_hp_max(character, (character.derived or {}).get("hp_max", before_hp))
    pre_attack_cap = (pending_reaction or {}).get("target_hp_before_damage")
    if not isinstance(pre_attack_cap, int):
        pre_attack_cap = hp_max
    cap = min(hp_max, pre_attack_cap)
    after_hp = min(cap, before_hp + max(int(damage_prevented or 0), 0))
    character.hp_current = after_hp
    return {
        "hp_before_reaction": before_hp,
        "hp_after_reaction": after_hp,
        "hp_restored": after_hp - before_hp,
    }
