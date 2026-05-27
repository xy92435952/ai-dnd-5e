"""Rule helpers for exploration procedures such as stealth and passive checks."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from services.dnd_rules import apply_character_damage, roll_attack, roll_dice, roll_saving_throw


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


def resolve_surprise(
    targets: list[dict[str, Any] | object],
    ambusher_stealth_results: list[dict[str, Any]],
    *,
    passive_skill: str = "perception",
) -> dict[str, Any]:
    """Resolve 5e-style surprise from ambusher Stealth totals vs passive Perception."""
    ambushers = [
        {
            "character_id": str(result.get("character_id") or result.get("id") or result.get("actor_id") or ""),
            "name": str(result.get("name") or result.get("actor_name") or ""),
            "total": _as_int(result.get("total"), 0),
        }
        for result in ambusher_stealth_results or []
        if isinstance(result, dict) and result.get("total") is not None
    ]
    target_results = []
    for target in targets or []:
        passive = passive_score(target, passive_skill)
        noticed = [
            ambusher["character_id"]
            for ambusher in ambushers
            if passive >= ambusher["total"]
        ]
        no_surprise = _has_no_surprise(target)
        surprised = bool(ambushers) and not noticed and not no_surprise
        target_results.append({
            "target_id": str(_read_attr(target, "id", "")),
            "name": _read_attr(target, "name", ""),
            "passive_skill": _normalize_skill(passive_skill),
            "passive_score": passive,
            "noticed_ambusher_ids": noticed,
            "no_surprise": no_surprise,
            "surprised": surprised,
        })

    return {
        "rule": "target_is_surprised_if_it_notices_no_ambusher_before_combat",
        "passive_skill": _normalize_skill(passive_skill),
        "ambushers": ambushers,
        "targets": target_results,
        "surprised_target_ids": [item["target_id"] for item in target_results if item["surprised"]],
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


def apply_trap_trigger_to_target(
    trap: dict[str, Any],
    target: dict[str, Any] | object,
    *,
    d20_roller: Callable[[str], dict[str, Any]] | None = None,
    damage_roller: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve and apply a triggered trap to a mutable character-like target."""
    resolution = resolve_trap_trigger(
        trap,
        target,
        d20_roller=d20_roller,
        damage_roller=damage_roller,
    )
    before_hp = _as_int(_read_attr(target, "hp_current", 0), 0)
    damage_result = _apply_damage_to_target(target, resolution["final_damage"])
    added_conditions = []
    for condition in resolution["conditions_applied"]:
        if _add_condition(target, str(condition)):
            added_conditions.append(str(condition))

    return {
        **resolution,
        "mutates_hp": True,
        "hp_before": before_hp,
        "hp_after": _as_int(_read_attr(target, "hp_current", 0), 0),
        "damage_application": damage_result,
        "conditions_added": added_conditions,
        "target_state": {
            "hp_current": _as_int(_read_attr(target, "hp_current", 0), 0),
            "conditions": _read_list(target, "conditions"),
            "condition_durations": _read_mapping(target, "condition_durations"),
            "death_saves": _read_attr(target, "death_saves", None),
        },
    }


def resolve_trap_attack(
    trap: dict[str, Any],
    target: dict[str, Any] | object,
    *,
    d20_roller: Callable[[str], dict[str, Any]] | None = None,
    damage_roller: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve an attack-roll trap against a target without mutating HP."""
    trap_data = trap if isinstance(trap, dict) else {}
    trap_id = _trap_id(trap_data)
    attack_bonus = _as_int(
        trap_data.get(
            "attack_bonus",
            trap_data.get("to_hit_bonus", trap_data.get("to_hit", trap_data.get("attack", 0))),
        ),
        0,
    )
    crit_threshold = _as_int(trap_data.get("crit_threshold", 20), 20)
    target_dict = _character_dict(target)
    target_derived = dict(target_dict.get("derived") or {})
    if "ac" not in target_derived:
        target_derived["ac"] = _as_int(
            _read_attr(target, "ac", trap_data.get("target_ac", 13)),
            13,
        )
    target_dict["derived"] = target_derived

    attack_result = roll_attack(
        {
            "id": trap_id,
            "name": str(trap_data.get("name") or trap_id),
            "derived": {"attack_bonus": attack_bonus, "ranged_attack_bonus": attack_bonus},
        },
        target_dict,
        is_ranged=bool(trap_data.get("ranged", True)),
        crit_threshold=crit_threshold,
        d20_roller=d20_roller,
    )
    hit = bool(attack_result.get("hit"))
    damage_dice = str(trap_data.get("damage_dice") or trap_data.get("damage") or "0")
    damage_roll = (damage_roller or roll_dice)(damage_dice) if hit else {
        "notation": damage_dice,
        "rolls": [],
        "total": 0,
    }
    rolled_damage = max(0, _as_int(damage_roll.get("total"), 0))
    conditions_on_hit = _read_inline_list(
        trap_data.get("conditions_on_hit", trap_data.get("condition_on_hit", []))
    )

    return {
        "trap_id": trap_id,
        "name": str(trap_data.get("name") or trap_id),
        "target_id": str(_read_attr(target, "id", "")),
        "target_name": _read_attr(target, "name", ""),
        "attack_bonus": attack_bonus,
        "attack": attack_result,
        "hit": hit,
        "damage_dice": damage_dice,
        "damage_type": str(trap_data.get("damage_type") or ""),
        "damage_roll": damage_roll,
        "rolled_damage": rolled_damage,
        "final_damage": rolled_damage if hit else 0,
        "conditions_applied": conditions_on_hit if hit else [],
        "mutates_hp": False,
    }


def apply_trap_attack_to_target(
    trap: dict[str, Any],
    target: dict[str, Any] | object,
    *,
    d20_roller: Callable[[str], dict[str, Any]] | None = None,
    damage_roller: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve and apply an attack-roll trap to a mutable character-like target."""
    resolution = resolve_trap_attack(
        trap,
        target,
        d20_roller=d20_roller,
        damage_roller=damage_roller,
    )
    before_hp = _as_int(_read_attr(target, "hp_current", 0), 0)
    damage_result = _apply_damage_to_target(target, resolution["final_damage"])
    added_conditions = []
    for condition in resolution["conditions_applied"]:
        if _add_condition(target, str(condition)):
            added_conditions.append(str(condition))

    return {
        **resolution,
        "mutates_hp": True,
        "hp_before": before_hp,
        "hp_after": _as_int(_read_attr(target, "hp_current", 0), 0),
        "damage_application": damage_result,
        "conditions_added": added_conditions,
        "target_state": {
            "hp_current": _as_int(_read_attr(target, "hp_current", 0), 0),
            "conditions": _read_list(target, "conditions"),
            "condition_durations": _read_mapping(target, "condition_durations"),
            "death_saves": _read_attr(target, "death_saves", None),
        },
    }


def resolve_trap_disarm(
    trap: dict[str, Any],
    actor: dict[str, Any] | object,
    *,
    d20_roller: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve an attempt to disarm a trap without mutating persistent state."""
    trap_data = trap if isinstance(trap, dict) else {}
    ability = _normalize_ability(
        trap_data.get("disarm_ability")
        or trap_data.get("disable_ability")
        or trap_data.get("ability")
        or "dex"
    )
    dc = _as_int(
        trap_data.get(
            "disarm_dc",
            trap_data.get("disable_dc", trap_data.get("dc", trap_data.get("detection_dc", 10))),
        ),
        10,
    )
    tool = str(
        trap_data.get("disarm_tool")
        or trap_data.get("tool")
        or "thieves' tools"
    )
    actor_dict = _character_dict(actor)
    derived = _read_mapping(actor, "derived")
    mods = dict(derived.get("ability_modifiers") or _read_mapping(actor, "ability_modifiers"))
    proficiency_bonus = _as_int(
        derived.get("proficiency_bonus", _read_attr(actor, "proficiency_bonus", 2)),
        2,
    )
    ability_modifier = _as_int(mods.get(ability), 0)
    proficient = _has_tool_proficiency(actor, tool)
    d20_result = (d20_roller or roll_dice)("1d20")
    d20 = _as_int((d20_result.get("rolls") or [0])[0], 0)
    total_modifier = ability_modifier + (proficiency_bonus if proficient else 0)
    total = d20 + total_modifier
    success = total >= dc
    failure_triggers = bool(trap_data.get("trigger_on_failed_disarm", True))
    triggered = (not success) and failure_triggers
    trap_id = _trap_id(trap_data)

    return {
        "trap_id": trap_id,
        "name": str(trap_data.get("name") or trap_id),
        "actor_id": str(_read_attr(actor, "id", "")),
        "actor_name": _read_attr(actor, "name", ""),
        "ability": ability,
        "tool": tool,
        "dc": dc,
        "d20": d20,
        "roll": d20_result,
        "ability_modifier": ability_modifier,
        "proficiency_bonus": proficiency_bonus if proficient else 0,
        "tool_proficient": proficient,
        "modifier": total_modifier,
        "total": total,
        "success": success,
        "triggered": triggered,
        "trigger_on_failed_disarm": failure_triggers,
        "mutates_state": False,
        "actor_snapshot": actor_dict,
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
        "surprise": {
            "rule": "compare_each_ambusher_stealth_total_to_each_target_passive_perception",
            "no_surprise_source": "Alert feat or equivalent no_surprise effect",
        },
        "passive_discovery": resolve_passive_discoveries(party, hidden_features or []),
        "trap_trigger": {
            "rule": "triggered_traps_roll_configured_save_then_apply_full_or_half_damage",
            "mutates_hp": False,
            "apply_rule": "apply_trap_trigger_to_target_mutates_hp_and_conditions",
            "attack_rule": "attack_roll_traps_compare_configured_attack_bonus_to_target_ac",
            "disarm_rule": "resolve_trap_disarm_rolls_configured_ability_plus_tool_proficiency",
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


def _has_no_surprise(character: dict[str, Any] | object) -> bool:
    for feat in _read_list(character, "feats"):
        if isinstance(feat, dict):
            name = str(feat.get("name") or "").strip().lower()
            effects = feat.get("effects") if isinstance(feat.get("effects"), dict) else {}
            if effects.get("no_surprise"):
                return True
        else:
            name = str(feat or "").strip().lower()
        if name in {"alert", "\u8b66\u89c9"}:
            return True
    return False


def _has_tool_proficiency(character: dict[str, Any] | object, tool: str) -> bool:
    target = _normalize_tool_name(tool)
    proficiencies = (
        _read_list(character, "tool_proficiencies")
        + _read_list(character, "proficient_tools")
        + _read_list(character, "proficiencies")
    )
    for item in proficiencies:
        if _normalize_tool_name(item) == target:
            return True
    return False


def _trap_id(trap_data: dict[str, Any]) -> str:
    return str(
        trap_data.get("id")
        or trap_data.get("trap_id")
        or trap_data.get("feature_id")
        or trap_data.get("name")
        or "trap"
    )


def _normalize_tool_name(tool: Any) -> str:
    value = (
        str(tool or "")
        .strip()
        .lower()
        .replace("\u2019", "'")
        .replace("'", "")
        .replace("-", " ")
    )
    return " ".join(value.split())


def _add_condition(character: dict[str, Any] | object, condition: str) -> bool:
    normalized = str(condition or "").strip().lower()
    if not normalized:
        return False
    conditions = _read_list(character, "conditions")
    normalized_existing = {str(item).strip().lower() for item in conditions}
    if normalized in normalized_existing:
        return False
    conditions.append(normalized)
    if isinstance(character, dict):
        character["conditions"] = conditions
    else:
        setattr(character, "conditions", conditions)
    return True


def _apply_damage_to_target(character: dict[str, Any] | object, damage: int) -> dict[str, Any]:
    if not isinstance(character, dict):
        return apply_character_damage(character, damage)

    before_hp = _as_int(character.get("hp_current"), 0)
    dealt = max(0, int(damage or 0))
    after_hp = max(0, before_hp - dealt)
    character["hp_current"] = after_hp
    dropped_to_zero = before_hp > 0 and after_hp == 0 and dealt > 0
    if after_hp == 0 and dealt > 0:
        _add_condition(character, "unconscious")
        if character.get("death_saves") is None:
            character["death_saves"] = {"successes": 0, "failures": 0, "stable": False}
    return {
        "hp_before": before_hp,
        "hp_after": after_hp,
        "damage": dealt,
        "damage_to_hp": dealt,
        "dropped_to_zero": dropped_to_zero,
        "death_save_failures_added": 0,
        "instant_death": False,
        "dead": False,
        "death_saves": character.get("death_saves"),
        "conditions": _read_list(character, "conditions"),
    }


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
