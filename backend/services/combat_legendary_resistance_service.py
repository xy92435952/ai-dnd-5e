"""Helpers for monster Legendary Resistance tracking."""

from __future__ import annotations

import re
from typing import Any


def normalize_legendary_resistance_uses(value: Any) -> int:
    """Return a non-negative Legendary Resistance use count from parsed monster data."""
    if value is None or isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return max(0, int(value))

    text = str(value).strip().lower()
    if not text:
        return 0

    match = re.search(r"\b(\d+)\s*/\s*day\b", text)
    if match:
        return max(0, int(match.group(1)))

    match = re.search(r"\b(\d+)\b", text)
    return max(0, int(match.group(1))) if match else 0


def legendary_resistance_max(enemy: dict[str, Any] | None) -> int:
    """Return the maximum Legendary Resistance uses for an enemy."""
    if not enemy:
        return 0

    for key in ("legendary_resistances", "legendary_resistance_uses", "legendary_resistance"):
        uses = normalize_legendary_resistance_uses(enemy.get(key))
        if uses > 0:
            return uses

    for ability in enemy.get("special_abilities") or []:
        if not isinstance(ability, dict):
            continue
        text = f"{ability.get('name', '')} {ability.get('description', '')}"
        if "legendary resistance" in text.lower():
            uses = normalize_legendary_resistance_uses(text)
            if uses > 0:
                return uses

    return 0


def legendary_resistance_remaining(enemy: dict[str, Any] | None) -> int:
    """Return remaining Legendary Resistance uses, defaulting to the max uses."""
    if not enemy:
        return 0
    if "legendary_resistances_remaining" in enemy:
        return normalize_legendary_resistance_uses(enemy.get("legendary_resistances_remaining"))
    return legendary_resistance_max(enemy)


def initialize_legendary_resistances(enemy: dict[str, Any]) -> dict[str, int]:
    """Write normalized Legendary Resistance fields onto an enemy combat state."""
    uses = legendary_resistance_max(enemy)
    raw_remaining = enemy.get("legendary_resistances_remaining")
    if raw_remaining is None:
        raw_remaining = uses
    remaining = normalize_legendary_resistance_uses(raw_remaining)
    remaining = min(remaining, uses) if uses else 0
    enemy["legendary_resistances"] = uses
    enemy["legendary_resistances_remaining"] = remaining
    return {"uses": uses, "remaining": remaining}


def maybe_use_legendary_resistance(
    enemy: dict[str, Any] | None,
    save_detail: dict[str, Any] | None,
    *,
    reason: str | None = None,
) -> dict[str, Any] | None:
    """Turn a failed enemy save into a success by consuming Legendary Resistance."""
    if not enemy or not save_detail or save_detail.get("success"):
        return save_detail

    remaining = legendary_resistance_remaining(enemy)
    if remaining <= 0:
        return save_detail

    uses = legendary_resistance_max(enemy)
    new_remaining = max(0, remaining - 1)
    enemy["legendary_resistances"] = uses
    enemy["legendary_resistances_remaining"] = new_remaining

    updated = dict(save_detail)
    updated.update({
        "success": True,
        "original_success": bool(save_detail.get("success")),
        "legendary_resistance_used": True,
        "legendary_resistance_remaining": new_remaining,
    })
    if reason:
        updated["legendary_resistance_reason"] = reason
    return updated
