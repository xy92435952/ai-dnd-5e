"""Rule helpers for exploration procedures such as stealth and passive checks."""

from __future__ import annotations

from typing import Any


SKILL_ALIASES = {
    "perception": "perception",
    "\u5bdf\u89c9": "perception",
    "\u611f\u77e5": "perception",
    "perceive": "perception",
    "investigation": "investigation",
    "investigate": "investigation",
    "\u8c03\u67e5": "investigation",
    "\u4fa6\u67e5": "investigation",
    "stealth": "stealth",
    "\u9690\u533f": "stealth",
    "\u6f5c\u884c": "stealth",
}


PASSIVE_SKILL_ABILITIES = {
    "perception": "wis",
    "investigation": "int",
    "stealth": "dex",
}


def passive_score(character: dict[str, Any] | object, skill: str = "perception") -> int:
    """Return 10 + relevant modifier + proficiency for a passive exploration skill."""
    skill_key = _normalize_skill(skill)
    derived = _read_mapping(character, "derived")
    ability = PASSIVE_SKILL_ABILITIES.get(skill_key, "wis")
    mods = dict(derived.get("ability_modifiers") or {})
    score = 10 + _as_int(mods.get(ability), 0)

    prof = _as_int(derived.get("proficiency_bonus"), 2)
    proficient_skills = _normalize_skill_names(_read_list(character, "proficient_skills"))
    if skill_key in proficient_skills:
        score += prof

    feats = _read_list(character, "feats")
    if skill_key in {"perception", "investigation"} and _has_feat(feats, "observant"):
        score += 5
    return score


def passive_perception(character: dict[str, Any] | object) -> int:
    return passive_score(character, "perception")


def passive_investigation(character: dict[str, Any] | object) -> int:
    return passive_score(character, "investigation")


def passive_detects(character: dict[str, Any] | object, dc: int, skill: str = "perception") -> bool:
    return passive_score(character, skill) >= int(dc)


def group_stealth_result(roll_results: list[dict[str, Any]], dc: int) -> dict[str, Any]:
    """Resolve 5e-style group stealth: at least half the group must succeed."""
    members = [result for result in roll_results or [] if isinstance(result, dict)]
    successes = [result for result in members if _roll_succeeds(result, dc)]
    needed = (len(members) + 1) // 2
    return {
        "dc": int(dc),
        "members": len(members),
        "successes": len(successes),
        "needed": needed,
        "success": bool(members) and len(successes) >= needed,
        "failed_member_ids": [
            str(result.get("character_id") or result.get("id"))
            for result in members
            if not _roll_succeeds(result, dc)
        ],
    }


def party_best_passive(
    characters: list[dict[str, Any] | object],
    skill: str = "perception",
) -> dict[str, Any]:
    """Return the highest passive score in a party with the owning character id."""
    best: dict[str, Any] | None = None
    for character in characters or []:
        score = passive_score(character, skill)
        current = {
            "character_id": str(_read_attr(character, "id", "")),
            "name": _read_attr(character, "name", ""),
            "score": score,
            "skill": _normalize_skill(skill),
        }
        if best is None or current["score"] > best["score"]:
            best = current
    return best or {"character_id": "", "name": "", "score": 0, "skill": _normalize_skill(skill)}


def _normalize_skill(skill: str | None) -> str:
    value = str(skill or "").strip().lower().replace("-", "_").replace(" ", "_")
    return SKILL_ALIASES.get(value, SKILL_ALIASES.get(str(skill or "").strip(), value))


def _normalize_skill_names(values: list[Any]) -> set[str]:
    return {
        normalized
        for normalized in (_normalize_skill(value) for value in values)
        if normalized
    }


def _has_feat(feats: list[Any], feat_name: str) -> bool:
    target = feat_name.strip().lower()
    for feat in feats or []:
        name = feat.get("name", "") if isinstance(feat, dict) else str(feat)
        if name.strip().lower() == target:
            return True
    return False


def _roll_succeeds(result: dict[str, Any], dc: int) -> bool:
    if "success" in result and result["success"] is not None:
        return bool(result["success"])
    return _as_int(result.get("total"), 0) >= int(dc)


def _read_mapping(source: dict[str, Any] | object, key: str) -> dict[str, Any]:
    value = _read_attr(source, key, {})
    return dict(value or {}) if isinstance(value, dict) else {}


def _read_list(source: dict[str, Any] | object, key: str) -> list[Any]:
    value = _read_attr(source, key, [])
    return list(value or []) if isinstance(value, (list, tuple, set)) else []


def _read_attr(source: dict[str, Any] | object, key: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
