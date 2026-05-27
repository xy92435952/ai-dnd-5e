from typing import Any

from services.combat_damage_service import normalize_damage_type
from services.dnd_character_rules import _normalize_class


PHYSICAL_DAMAGE_TYPES = {"bludgeoning", "piercing", "slashing"}


def is_fire_damage(damage_type: str | None) -> bool:
    return normalize_damage_type(damage_type) == "fire"


def _character_damage_types(character: Any, key: str) -> list[str]:
    derived = getattr(character, "derived", None) or {}
    values = derived.get(key, [])
    return list(values or [])


def _condition_resistances(character: Any) -> set[str]:
    conditions = {
        str(condition).strip().lower().replace(" ", "_").replace("-", "_")
        for condition in (getattr(character, "conditions", None) or [])
        if condition
    }
    resistances: set[str] = set()
    for condition in conditions:
        if not condition.endswith("_resistance"):
            continue
        damage_type = condition.removesuffix("_resistance")
        normalized = normalize_damage_type(damage_type)
        if normalized:
            resistances.add(normalized)
    return resistances


def apply_character_damage_resistance(
    target_character,
    damage: int,
    damage_type: str | None,
) -> tuple[int, bool]:
    """Apply character-side damage resistance, immunity, and vulnerability rules."""
    final_damage = max(0, int(damage or 0))
    normalized_type = normalize_damage_type(damage_type)
    if not normalized_type or not target_character:
        return final_damage, False

    immunities = {
        normalize_damage_type(value)
        for value in _character_damage_types(target_character, "immunities")
    }
    vulnerabilities = {
        normalize_damage_type(value)
        for value in _character_damage_types(target_character, "vulnerabilities")
    }
    resistances = {
        normalize_damage_type(value)
        for value in _character_damage_types(target_character, "resistances")
    }
    resistances |= _condition_resistances(target_character)

    if normalized_type in immunities:
        return 0, final_damage != 0
    if normalized_type in vulnerabilities:
        return final_damage * 2, final_damage != final_damage * 2
    if normalized_type in resistances:
        return final_damage // 2, final_damage != final_damage // 2

    class_key = _normalize_class(getattr(target_character, "char_class", "") or "")
    class_resources = dict(getattr(target_character, "class_resources", None) or {})
    if class_key == "Barbarian" and class_resources.get("raging", False):
        subclass_effects = (getattr(target_character, "derived", None) or {}).get("subclass_effects", {})
        if subclass_effects.get("bear_totem"):
            if normalized_type != "psychic":
                return final_damage // 2, final_damage != final_damage // 2
        elif normalized_type in PHYSICAL_DAMAGE_TYPES:
            return final_damage // 2, final_damage != final_damage // 2

    return final_damage, False
