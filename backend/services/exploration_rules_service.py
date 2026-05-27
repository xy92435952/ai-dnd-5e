"""Rule helpers for exploration procedures such as stealth and passive checks."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from services.dnd_rules import roll_dice, roll_saving_throw


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
    mods = dict(derived.get("ability_modifiers") or _read_mapping(character, "ability_modifiers"))
    score = 10 + _as_int(mods.get(ability), 0)

    prof = _as_int(
        derived.get("proficiency_bonus", _read_attr(character, "proficiency_bonus", 2)),
        2,
    )
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


def character_passive_summary(character: dict[str, Any] | object) -> dict[str, Any]:
    """Return passive exploration scores for a single character."""
    return {
        "character_id": str(_read_attr(character, "id", "")),
        "name": _read_attr(character, "name", ""),
        "passive_perception": passive_perception(character),
        "passive_investigation": passive_investigation(character),
        "passive_stealth": passive_score(character, "stealth"),
    }


def resolve_passive_discoveries(
    characters: list[dict[str, Any] | object],
    features: list[dict[str, Any]],
) -> dict[str, Any]:
    """Resolve which hidden scene features are noticed by passive scores."""
    party = list(characters or [])
    results = []
    for index, feature in enumerate(features or []):
        if not isinstance(feature, dict):
            continue
        skill = _feature_skill(feature)
        dc = _feature_dc(feature, skill)
        best = party_best_passive(party, skill)
        detected = bool(party) and best["score"] >= dc
        feature_id = str(
            feature.get("id")
            or feature.get("feature_id")
            or feature.get("trap_id")
            or feature.get("name")
            or f"feature_{index + 1}"
        )
        results.append({
            "feature_id": feature_id,
            "name": str(feature.get("name") or feature_id),
            "kind": str(feature.get("kind") or feature.get("type") or "hidden_feature"),
            "dc": dc,
            "skill": skill,
            "detected": detected,
            "detected_by": best if detected else None,
            "best_score": best["score"],
        })

    return {
        "rule": "party_best_passive_for_feature_skill_meets_dc",
        "features": results,
        "detected_feature_ids": [item["feature_id"] for item in results if item["detected"]],
        "hidden_feature_ids": [item["feature_id"] for item in results if not item["detected"]],
    }


def resolve_trap_trigger(
    trap: dict[str, Any],
    target: dict[str, Any] | object,
    *,
    d20_roller: Callable[[str], dict[str, Any]] | None = None,
    damage_roller: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve a triggered trap's save and damage without mutating character HP."""
    trap_data = trap if isinstance(trap, dict) else {}
    save_ability = _normalize_ability(
        trap_data.get("save_ability")
        or trap_data.get("saving_throw")
        or trap_data.get("ability")
        or "dex"
    )
    save_dc = _as_int(
        trap_data.get("save_dc", trap_data.get("dc", trap_data.get("trigger_dc", 10))),
        10,
    )
    target_dict = _character_dict(target)
    save_result = roll_saving_throw(
        target_dict,
        save_ability,
        save_dc,
        d20_roller=d20_roller,
    )

    damage_dice = str(trap_data.get("damage_dice") or trap_data.get("damage") or "0")
    roller = damage_roller or roll_dice
    damage_roll = roller(damage_dice)
    rolled_damage = max(0, _as_int(damage_roll.get("total"), 0))
    half_on_save = bool(trap_data.get("half_on_save", True))
    saved = bool(save_result.get("success"))
    final_damage = rolled_damage // 2 if saved and half_on_save else rolled_damage
    conditions_on_fail = _read_inline_list(
        trap_data.get("conditions_on_fail", trap_data.get("condition_on_fail", []))
    )
    applied_conditions = [] if saved else conditions_on_fail

    trap_id = str(
        trap_data.get("id")
        or trap_data.get("trap_id")
        or trap_data.get("feature_id")
        or trap_data.get("name")
        or "trap"
    )
    return {
        "trap_id": trap_id,
        "name": str(trap_data.get("name") or trap_id),
        "target_id": str(_read_attr(target, "id", "")),
        "target_name": _read_attr(target, "name", ""),
        "save_ability": save_ability,
        "save_dc": save_dc,
        "save": save_result,
        "saved": saved,
        "damage_dice": damage_dice,
        "damage_type": str(trap_data.get("damage_type") or ""),
        "damage_roll": damage_roll,
        "rolled_damage": rolled_damage,
        "half_on_save": half_on_save,
        "final_damage": final_damage,
        "conditions_applied": applied_conditions,
        "mutates_hp": False,
    }


def build_exploration_context(
    characters: list[dict[str, Any] | object],
    hidden_features: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a compact exploration rules summary for DM input context."""
    party = list(characters or [])
    return {
        "character_passives": [character_passive_summary(character) for character in party],
        "party_best_passive": {
            "perception": party_best_passive(party, "perception"),
            "investigation": party_best_passive(party, "investigation"),
            "stealth": party_best_passive(party, "stealth"),
        },
        "group_stealth": {
            "skill": "stealth",
            "success_rule": "at_least_half_members_meet_or_exceed_dc",
        },
        "passive_discovery": resolve_passive_discoveries(party, hidden_features or []),
        "trap_trigger": {
            "rule": "triggered_traps_roll_configured_save_then_apply_full_or_half_damage",
            "mutates_hp": False,
        },
    }


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


def _feature_skill(feature: dict[str, Any]) -> str:
    explicit = (
        feature.get("detection_skill")
        or feature.get("skill")
        or feature.get("check")
        or feature.get("ability")
    )
    if explicit:
        return _normalize_skill(str(explicit))

    kind = str(feature.get("kind") or feature.get("type") or "").strip().lower()
    if kind in {"clue", "evidence", "mechanism", "puzzle", "riddle", "secret_mechanism"}:
        return "investigation"
    return "perception"


def _feature_dc(feature: dict[str, Any], skill: str) -> int:
    candidates = [
        feature.get(f"{skill}_dc"),
        feature.get("detection_dc"),
        feature.get("passive_dc"),
        feature.get("dc"),
    ]
    for value in candidates:
        if value is not None:
            return _as_int(value, 10)
    return 10


def _normalize_ability(ability: Any) -> str:
    value = str(ability or "").strip().lower()
    aliases = {
        "strength": "str",
        "dexterity": "dex",
        "constitution": "con",
        "intelligence": "int",
        "wisdom": "wis",
        "charisma": "cha",
    }
    normalized = aliases.get(value, value[:3])
    return normalized if normalized in {"str", "dex", "con", "int", "wis", "cha"} else "dex"


def _character_dict(character: dict[str, Any] | object) -> dict[str, Any]:
    if isinstance(character, dict):
        return character
    return {
        "id": _read_attr(character, "id", ""),
        "name": _read_attr(character, "name", ""),
        "ability_scores": _read_mapping(character, "ability_scores"),
        "derived": _read_mapping(character, "derived"),
        "conditions": _read_list(character, "conditions"),
        "condition_durations": _read_mapping(character, "condition_durations"),
    }


def _read_inline_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


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
