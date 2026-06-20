"""Helpers for DnD monster Recharge abilities.

Recharge abilities normally start available, become unavailable after use, and
roll a d6 at the start of the monster's turn until the roll meets the recharge
threshold.
"""

from __future__ import annotations

import random
import re
from typing import Any, Callable

RollD6 = Callable[[], int]


def parse_recharge_threshold(value: Any) -> int | None:
    """Return the lowest d6 value that recharges an ability, such as 5 for 5-6."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        threshold = int(value)
        return threshold if 2 <= threshold <= 6 else None

    text = str(value).strip().lower()
    if not text:
        return None

    if "recharge" in text:
        tail = text[text.find("recharge"):]
        digits = [int(match) for match in re.findall(r"\b([2-6])\b", tail)]
        return digits[0] if digits else None

    digits = [int(match) for match in re.findall(r"\b([2-6])\b", text)]
    if len(digits) >= 2 and digits[-1] == 6:
        return digits[0]
    if len(digits) == 1 and re.fullmatch(r"\s*[2-6]\s*", text):
        return digits[0]

    return None


def normalize_recharge_abilities(monster: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Collect and normalize recharge abilities from explicit data and actions."""
    if not monster:
        return []

    candidates: list[tuple[str, dict[str, Any]]] = []
    candidates.extend(("recharge_ability", ability) for ability in _as_dicts(monster.get("recharge_abilities")))
    candidates.extend(("action", action) for action in _as_dicts(monster.get("actions")))
    candidates.extend(("special_ability", ability) for ability in _as_dicts(monster.get("special_abilities")))

    abilities: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()

    for index, (source, candidate) in enumerate(candidates):
        threshold = _candidate_threshold(candidate)
        if threshold is None:
            continue

        name = str(candidate.get("name") or f"Recharge Ability {index + 1}").strip()
        key = (name.lower(), threshold)
        if key in seen:
            continue
        seen.add(key)

        ability = {
            "id": str(candidate.get("id") or _ability_id(name, source, index)),
            "name": name,
            "source": str(candidate.get("source") or source),
            "recharge": str(candidate.get("recharge") or candidate.get("threshold") or f"{threshold}-6"),
            "threshold": threshold,
            "available": bool(candidate.get("available", True)),
        }
        if "last_recharge_roll" in candidate:
            ability["last_recharge_roll"] = candidate.get("last_recharge_roll")

        for field in (
            "type",
            "description",
            "attack_bonus",
            "reach_or_range",
            "damage_dice",
            "damage_type",
            "extra_effects",
            "save",
            "save_dc",
            "saving_throw",
            "area",
            "targeting",
            "targets",
            "max_targets",
            "target_count",
            "aoe",
            "push_distance_ft",
            "pull_distance_ft",
            "half_on_save",
            "condition",
            "condition_name",
            "condition_on_failed_save",
            "conditions_on_failed_save",
            "condition_duration",
            "condition_duration_rounds",
            "duration_rounds",
        ):
            if field in candidate and candidate.get(field) is not None:
                ability[field] = candidate.get(field)

        abilities.append(ability)

    return abilities


def refresh_recharge_abilities_at_turn_start(
    enemy: dict[str, Any] | None,
    *,
    roll_d6: RollD6 | None = None,
) -> dict[str, Any]:
    """Roll unavailable recharge abilities at the start of an enemy turn."""
    if not enemy:
        return {"changed": False, "events": [], "abilities": []}

    before = list(enemy.get("recharge_abilities") or [])
    abilities = normalize_recharge_abilities(enemy)
    changed = abilities != before
    events: list[dict[str, Any]] = []

    if not abilities:
        if "recharge_abilities" not in enemy:
            enemy["recharge_abilities"] = []
            changed = True
        return {"changed": changed, "events": events, "abilities": []}

    roller = roll_d6 or (lambda: random.randint(1, 6))
    for ability in abilities:
        if ability.get("available", True):
            continue

        roll = max(1, min(6, int(roller())))
        threshold = int(ability.get("threshold") or 6)
        recharged = roll >= threshold
        ability["last_recharge_roll"] = roll
        ability["available"] = recharged
        changed = True
        events.append({
            "ability_id": ability.get("id"),
            "name": ability.get("name"),
            "roll": roll,
            "threshold": threshold,
            "recharged": recharged,
        })

    enemy["recharge_abilities"] = abilities
    return {"changed": changed, "events": events, "abilities": abilities}


def choose_recharge_ability(
    enemy: dict[str, Any] | None,
    *,
    action_name: str | None = None,
) -> dict[str, Any] | None:
    """Return an available recharge ability, preferring the requested action name."""
    if not enemy:
        return None
    abilities = normalize_recharge_abilities(enemy)
    if not abilities:
        enemy["recharge_abilities"] = []
        return None

    enemy["recharge_abilities"] = abilities
    available = [ability for ability in abilities if ability.get("available", True)]
    if not available:
        return None

    requested = _normalize_action_name(action_name)
    if requested:
        for ability in available:
            if _normalize_action_name(ability.get("name")) == requested:
                return ability
        return None
    return available[0]


def mark_recharge_ability_used(
    enemy: dict[str, Any] | None,
    ability_id: str | None,
) -> bool:
    """Mark a recharge ability unavailable after it has been used."""
    if not enemy or not ability_id:
        return False
    abilities = normalize_recharge_abilities(enemy)
    changed = False
    for ability in abilities:
        if str(ability.get("id")) != str(ability_id):
            continue
        if ability.get("available", True):
            ability["available"] = False
            ability.pop("last_recharge_roll", None)
            changed = True
        break
    enemy["recharge_abilities"] = abilities
    return changed


def _as_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            result.append(dict(item))
        elif isinstance(item, str):
            result.append({"name": item, "description": item})
    return result


def _candidate_threshold(candidate: dict[str, Any]) -> int | None:
    for key in ("threshold", "recharge"):
        threshold = parse_recharge_threshold(candidate.get(key))
        if threshold is not None:
            return threshold

    text = " ".join(
        str(candidate.get(key, ""))
        for key in ("name", "description", "extra_effects")
    )
    if "recharge" not in text.lower():
        return None
    return parse_recharge_threshold(text)


def _ability_id(name: str, source: str, index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"{source}_{slug or index + 1}"


def _normalize_action_name(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")
