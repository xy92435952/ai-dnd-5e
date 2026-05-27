"""Helpers for monster Legendary Action resources."""

from __future__ import annotations

import re
from typing import Any


def normalize_legendary_actions(value: Any) -> list[dict[str, Any]]:
    """Return a clean list of legendary action definitions."""
    if not isinstance(value, list):
        return []

    actions: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if isinstance(item, dict):
            name = str(item.get("name") or f"Legendary Action {index + 1}").strip()
            action = dict(item)
        elif isinstance(item, str):
            name = item.strip() or f"Legendary Action {index + 1}"
            action = {"name": name, "description": item}
        else:
            continue

        action["id"] = str(action.get("id") or _legendary_action_id(name, index))
        action["name"] = name
        action["cost"] = _normalize_action_cost(action.get("cost", action.get("points", 1)))
        actions.append(action)
    return actions


def normalize_legendary_action_uses(value: Any, *, actions: list[dict[str, Any]] | None = None) -> int:
    """Read the per-round Legendary Action pool, defaulting to 3 when actions exist."""
    if isinstance(value, bool) or value is None:
        return 3 if actions else 0
    if isinstance(value, (int, float)):
        return max(0, int(value))

    text = str(value).strip()
    digits = re.findall(r"\d+", text)
    if digits:
        return max(0, int(digits[0]))
    return 3 if actions else 0


def initialize_legendary_actions(enemy: dict[str, Any]) -> dict[str, int]:
    """Normalize legendary actions and ensure max/remaining resource fields exist."""
    actions = normalize_legendary_actions(enemy.get("legendary_actions"))
    uses = normalize_legendary_action_uses(
        enemy.get("legendary_action_uses", enemy.get("legendary_actions_per_round")),
        actions=actions,
    )
    raw_remaining = enemy.get("legendary_action_uses_remaining")
    if raw_remaining is None:
        remaining = uses
    else:
        remaining = min(uses, normalize_legendary_action_uses(raw_remaining, actions=actions))

    enemy["legendary_actions"] = actions
    enemy["legendary_action_uses"] = uses
    enemy["legendary_action_uses_remaining"] = remaining
    return {"uses": uses, "remaining": remaining}


def refresh_legendary_actions_for_turn_start(enemy: dict[str, Any] | None) -> dict[str, Any]:
    """Refresh one surviving monster's Legendary Action pool at the start of its turn."""
    if not enemy:
        return {"changed": False, "refreshed": None}

    before_remaining = enemy.get("legendary_action_uses_remaining")
    state = initialize_legendary_actions(enemy)
    if not enemy.get("legendary_actions") or enemy.get("hp_current", 0) <= 0:
        return {"changed": False, "refreshed": None}

    changed = before_remaining != state["uses"]
    if changed:
        enemy["legendary_action_uses_remaining"] = state["uses"]
    return {
        "changed": changed,
        "refreshed": {
            "enemy_id": enemy.get("id"),
            "name": enemy.get("name"),
            "uses": state["uses"],
        } if changed else None,
    }


def refresh_legendary_actions_for_new_round(enemies: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Refresh each surviving monster's Legendary Action pool at the start of a round."""
    changed = False
    refreshed: list[dict[str, Any]] = []
    for enemy in enemies or []:
        result = refresh_legendary_actions_for_turn_start(enemy)
        if result["changed"]:
            changed = True
            refreshed.append(result["refreshed"])
    return {"changed": changed, "refreshed": refreshed}


def spend_legendary_action(enemy: dict[str, Any] | None, action_id: str | None = None) -> dict[str, Any]:
    """Spend one legendary action definition if the monster has enough remaining uses."""
    if not enemy:
        return {"spent": False, "reason": "missing_enemy"}

    state = initialize_legendary_actions(enemy)
    actions = list(enemy.get("legendary_actions") or [])
    if not actions:
        return {"spent": False, "reason": "no_legendary_actions"}

    action = _choose_action(actions, action_id)
    if not action:
        return {"spent": False, "reason": "unknown_action"}

    cost = _normalize_action_cost(action.get("cost", 1))
    remaining = state["remaining"]
    if remaining < cost:
        return {"spent": False, "reason": "insufficient_uses", "remaining": remaining, "cost": cost}

    enemy["legendary_action_uses_remaining"] = remaining - cost
    return {
        "spent": True,
        "action": action,
        "cost": cost,
        "remaining": enemy["legendary_action_uses_remaining"],
    }


def _choose_action(actions: list[dict[str, Any]], action_id: str | None) -> dict[str, Any] | None:
    if action_id:
        for action in actions:
            if str(action.get("id")) == str(action_id) or _normalize_name(action.get("name")) == _normalize_name(action_id):
                return action
        return None
    return actions[0] if actions else None


def _legendary_action_id(name: str, index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"legendary_{slug or index + 1}"


def _normalize_action_cost(value: Any) -> int:
    try:
        return max(1, int(value or 1))
    except (TypeError, ValueError):
        digits = re.findall(r"\d+", str(value or ""))
        return max(1, int(digits[0])) if digits else 1


def _normalize_name(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")
