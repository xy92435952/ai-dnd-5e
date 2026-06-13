from __future__ import annotations

from typing import Any

from services.combat_attack_roll_service import CombatAttackRollError
from services.dnd_rules import _normalize_class, proficiency_bonus

MARTIAL_ARTS_SHIELD_MESSAGE = "Martial Arts cannot be used while an equipped shield is worn"
MARTIAL_ARTS_CLASS_MESSAGE = "Only Monks can use Martial Arts"
MARTIAL_ARTS_LEVEL_MESSAGE = "Martial Arts requires Monk level 1"


def is_martial_arts_attack(action_type: str | None) -> bool:
    return str(action_type or "").strip().lower() in {
        "martial_arts",
        "monk_martial_arts",
        "unarmed",
        "unarmed_strike",
    }


def martial_arts_die(level: int) -> int:
    if level >= 17:
        return 10
    if level >= 11:
        return 8
    if level >= 5:
        return 6
    return 4


def get_martial_arts_error(actor: Any | None) -> str | None:
    if not actor or _normalize_class(getattr(actor, "char_class", "")) != "Monk":
        return MARTIAL_ARTS_CLASS_MESSAGE
    if int(getattr(actor, "level", 0) or 0) < 1:
        return MARTIAL_ARTS_LEVEL_MESSAGE
    if _has_equipped_shield(getattr(actor, "equipment", None) or {}):
        return MARTIAL_ARTS_SHIELD_MESSAGE
    return None


def validate_martial_arts(actor: Any | None) -> None:
    error = get_martial_arts_error(actor)
    if error:
        raise CombatAttackRollError(400, error)


def build_martial_arts_damage_dice(actor: Any) -> tuple[str, int, int]:
    """Return damage_dice, hit_die, and modifier for a Monk Martial Arts strike."""
    validate_martial_arts(actor)
    die = martial_arts_die(int(getattr(actor, "level", 1) or 1))
    dmg_mod = _martial_arts_ability_modifier(actor)
    damage_dice = f"1d{die}+{dmg_mod}" if dmg_mod >= 0 else f"1d{die}{dmg_mod}"
    return damage_dice, die, dmg_mod


def build_martial_arts_attack_derived(actor: Any, derived: dict[str, Any]) -> dict[str, Any]:
    """Return derived stats adjusted for a Martial Arts unarmed strike."""
    validate_martial_arts(actor)
    updated = dict(derived or {})
    fallback_proficiency = proficiency_bonus(int(getattr(actor, "level", 1) or 1))
    proficiency = max(int(updated.get("proficiency_bonus", 0) or 0), fallback_proficiency)
    updated["attack_bonus"] = proficiency + _martial_arts_ability_modifier(actor)
    return updated


def _martial_arts_ability_modifier(actor: Any) -> int:
    modifiers = (getattr(actor, "derived", None) or {}).get("ability_modifiers", {}) or {}
    return max(int(modifiers.get("str", 0) or 0), int(modifiers.get("dex", 0) or 0))


def _has_equipped_shield(equipment: dict[str, Any]) -> bool:
    shield = equipment.get("shield")
    return isinstance(shield, dict) and shield.get("equipped") is not False
