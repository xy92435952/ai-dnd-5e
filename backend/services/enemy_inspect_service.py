"""Enemy inspect/reveal helpers for combat snapshots.

The combat client always receives public HP/AC. Detailed stat-block knowledge
is stored on the session enemy entry and exposed only after an inspect check
reveals the matching stat keys.
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any


ALL_STATS = "all"
INSPECT_STAT_KEYS = (
    "cr",
    "speed",
    "resistances",
    "immunities",
    "vulnerabilities",
    "condition_immunities",
    "actions",
    "special_abilities",
    "tactics",
)

SKILL_ALIASES = {
    "perception": "perception",
    "perceive": "perception",
    "spot": "perception",
    "observe": "perception",
    "察觉": "perception",
    "感知": "perception",
    "investigation": "investigation",
    "investigate": "investigation",
    "inspect": "investigation",
    "search": "investigation",
    "调查": "investigation",
    "侦查": "investigation",
    "arcana": "arcana",
    "奥秘": "arcana",
    "nature": "nature",
    "自然": "nature",
    "religion": "religion",
    "宗教": "religion",
    "insight": "insight",
    "洞察": "insight",
}

SKILL_REVEAL_STATS = {
    "perception": ("cr", "speed", "tactics"),
    "investigation": (
        "cr",
        "speed",
        "resistances",
        "immunities",
        "vulnerabilities",
        "condition_immunities",
        "actions",
        "special_abilities",
    ),
    "arcana": ("cr", "resistances", "immunities", "vulnerabilities", "special_abilities"),
    "nature": ("cr", "speed", "resistances", "vulnerabilities", "actions", "tactics"),
    "religion": ("cr", "resistances", "immunities", "vulnerabilities", "special_abilities"),
    "insight": ("actions", "tactics"),
}


def normalize_inspect_skill(skill: str | None) -> str:
    normalized = str(skill or "investigation").strip().lower()
    return SKILL_ALIASES.get(normalized, normalized if normalized in SKILL_REVEAL_STATS else "investigation")


def default_enemy_inspect_dc(enemy: dict[str, Any] | None) -> int:
    cr = _parse_cr((enemy or {}).get("cr", (enemy or {}).get("challenge_rating")))
    if cr is None:
        return 12
    return max(10, min(20, 10 + math.ceil(cr)))


def revealed_stats_for_check(skill: str, check_result: dict[str, Any], dc: int) -> list[str]:
    if not check_result.get("success"):
        return []
    total = int(check_result.get("total", 0) or 0)
    d20 = int(check_result.get("d20", 0) or 0)
    if total - dc >= 5 or d20 == 20:
        return [ALL_STATS]
    return list(SKILL_REVEAL_STATS.get(normalize_inspect_skill(skill), SKILL_REVEAL_STATS["investigation"]))


def apply_enemy_inspect_result(
    enemies: list[dict[str, Any]],
    target_id: str,
    *,
    skill: str,
    dc: int,
    check_result: dict[str, Any],
    character_id: str,
    character_name: str,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, list[str]]:
    revealed = revealed_stats_for_check(skill, check_result, dc)
    updated: list[dict[str, Any]] = []
    target: dict[str, Any] | None = None
    for enemy in enemies or []:
        if str(enemy.get("id")) != str(target_id):
            updated.append(enemy)
            continue
        patched = deepcopy(enemy)
        existing = _collect_revealed_stats(patched, character_id=character_id)
        merged = _merge_stats(existing, revealed)
        knowledge = dict(patched.get("knowledge_state") or {})
        by_character = {
            str(key): dict(value)
            for key, value in dict(knowledge.get("by_character") or {}).items()
            if isinstance(value, dict)
        }
        character_knowledge = dict(by_character.get(str(character_id)) or {})
        last_inspect = {
            "skill": normalize_inspect_skill(skill),
            "dc": dc,
            "total": check_result.get("total"),
            "success": bool(check_result.get("success")),
            "character_id": character_id,
            "character_name": character_name,
        }
        character_knowledge["inspected"] = True
        character_knowledge["last_inspect"] = last_inspect
        knowledge["last_inspect"] = last_inspect
        if merged:
            character_knowledge["revealed_stats"] = merged
        if ALL_STATS in merged:
            character_knowledge["identified"] = True
        by_character[str(character_id)] = character_knowledge
        knowledge["by_character"] = by_character
        patched["knowledge_state"] = knowledge
        target = patched
        updated.append(patched)
    return updated, target, revealed


def build_enemy_inspect_snapshot(
    enemy: dict[str, Any],
    *,
    viewer_character_id: str | None = None,
) -> dict[str, Any]:
    """Return only inspect fields currently visible to players."""
    knowledge = dict(enemy.get("knowledge_state") or {})
    character_knowledge = _character_knowledge(knowledge, viewer_character_id)
    revealed = _collect_revealed_stats(enemy, character_id=viewer_character_id)
    fully_visible = (
        ALL_STATS in revealed
        or enemy.get("identified") is True
        or enemy.get("inspected") is True
        or enemy.get("stats_revealed") is True
        or knowledge.get("identified") is True
        or knowledge.get("stats_revealed") is True
        or character_knowledge.get("identified") is True
        or character_knowledge.get("stats_revealed") is True
    )
    allowed = set(INSPECT_STAT_KEYS if fully_visible else revealed)
    if fully_visible:
        revealed = _merge_stats(revealed, [ALL_STATS])

    snapshot: dict[str, Any] = {}
    if revealed:
        snapshot["revealed_stats"] = revealed
    if knowledge and (character_knowledge or revealed or fully_visible):
        safe_knowledge = {
            key: value
            for key, value in knowledge.items()
            if key not in {"by_character", "last_inspect"}
        }
        if character_knowledge:
            safe_knowledge.update(character_knowledge)
            safe_knowledge["viewer_character_id"] = str(viewer_character_id)
        if revealed:
            safe_knowledge["revealed_stats"] = revealed
        if safe_knowledge:
            snapshot["knowledge_state"] = safe_knowledge
    for flag in ("identified", "inspected", "stats_revealed"):
        if enemy.get(flag) is True or (flag != "inspected" and character_knowledge.get(flag) is True):
            snapshot[flag] = True
    for key in INSPECT_STAT_KEYS:
        if key in allowed or ALL_STATS in allowed:
            snapshot[key] = deepcopy(enemy.get(key))
    return snapshot


def _character_knowledge(
    knowledge: dict[str, Any],
    character_id: str | None,
) -> dict[str, Any]:
    if not character_id:
        return {}
    by_character = knowledge.get("by_character")
    if not isinstance(by_character, dict):
        return {}
    value = by_character.get(str(character_id))
    return dict(value) if isinstance(value, dict) else {}


def _collect_revealed_stats(
    enemy: dict[str, Any],
    *,
    character_id: str | None = None,
) -> list[str]:
    knowledge = enemy.get("knowledge_state") or enemy.get("knowledge") or enemy.get("inspect") or {}
    character_knowledge = _character_knowledge(knowledge, character_id) if isinstance(knowledge, dict) else {}
    values = []
    for source in (
        enemy.get("revealed_stats"),
        enemy.get("known_stats"),
        knowledge.get("revealed_stats") if isinstance(knowledge, dict) else None,
        knowledge.get("known_stats") if isinstance(knowledge, dict) else None,
        character_knowledge.get("revealed_stats"),
        character_knowledge.get("known_stats"),
    ):
        if isinstance(source, list):
            values.extend(source)
    return _merge_stats([], values)


def _merge_stats(existing: list[str], incoming: list[str]) -> list[str]:
    merged: list[str] = []
    for value in [*existing, *incoming]:
        key = str(value or "").strip().lower()
        if not key or key in merged:
            continue
        if key == ALL_STATS:
            return [ALL_STATS]
        if key in INSPECT_STAT_KEYS:
            merged.append(key)
    return merged


def _parse_cr(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if "/" in text:
        num, _, den = text.partition("/")
        try:
            return float(num) / float(den)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None
