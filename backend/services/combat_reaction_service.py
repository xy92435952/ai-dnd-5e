from __future__ import annotations

from typing import Any


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


def restore_prevented_damage(character, pending_reaction: dict[str, Any] | None, damage_prevented: int) -> dict[str, int]:
    """Retroactively restore HP without exceeding the pre-attack HP snapshot."""
    before_hp = int(character.hp_current or 0)
    hp_max = int((character.derived or {}).get("hp_max", before_hp))
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
