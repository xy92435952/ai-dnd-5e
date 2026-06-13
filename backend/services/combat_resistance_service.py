from typing import Any

from services.combat_damage_service import apply_damage_with_resistance, normalize_damage_type
from services.dnd_character_rules import _normalize_class


PHYSICAL_DAMAGE_TYPES = {"bludgeoning", "piercing", "slashing"}
ALL_DAMAGE_RESISTANCE = "all"
ALL_DAMAGE_RESISTANCE_CONDITIONS = {"petrified", "石化"}


def is_fire_damage(damage_type: str | None) -> bool:
    return normalize_damage_type(damage_type) == "fire"


def _character_damage_types(character: Any, key: str) -> list[str]:
    derived = getattr(character, "derived", None) or {}
    values = derived.get(key, [])
    return list(values or [])


def normalize_condition_key(condition: Any) -> str:
    return str(condition or "").strip().lower().replace(" ", "_").replace("-", "_")


def condition_damage_resistances(conditions: list[Any] | tuple[Any, ...] | set[Any] | None) -> set[str]:
    """Return damage resistance keys granted by active combat conditions."""
    keys = {
        normalize_condition_key(condition)
        for condition in (conditions or [])
        if condition
    }
    resistances: set[str] = set()
    for condition in keys:
        if condition in ALL_DAMAGE_RESISTANCE_CONDITIONS:
            resistances.add(ALL_DAMAGE_RESISTANCE)
            continue
        if not condition.endswith("_resistance"):
            continue
        damage_type = condition.removesuffix("_resistance")
        normalized = normalize_damage_type(damage_type)
        if normalized:
            resistances.add(normalized)
    return resistances


def _condition_resistances(character: Any) -> set[str]:
    return condition_damage_resistances(getattr(character, "conditions", None) or [])


def enemy_damage_resistances(enemy: dict[str, Any] | None, extra_conditions: list[Any] | None = None) -> list[str]:
    if not enemy:
        return []
    resistances = {
        normalize_damage_type(value)
        for value in (enemy.get("resistances", []) or [])
    }
    resistances |= condition_damage_resistances(enemy.get("conditions", []) or [])
    resistances |= condition_damage_resistances(extra_conditions or [])
    return [value for value in resistances if value]


def apply_enemy_damage_resistance(
    enemy: dict[str, Any] | None,
    damage: int,
    damage_type: str | None,
    *,
    extra_conditions: list[Any] | None = None,
) -> tuple[int, bool]:
    """Apply enemy-side resistance, immunity, vulnerability, and condition resistance."""
    final_damage = max(0, int(damage or 0))
    if not damage_type or not enemy:
        return final_damage, False

    applied = apply_damage_with_resistance(
        final_damage,
        damage_type,
        enemy_damage_resistances(enemy, extra_conditions),
        enemy.get("immunities", []),
        enemy.get("vulnerabilities", []),
    )
    return applied, applied != final_damage


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

    applied_damage = apply_damage_with_resistance(
        final_damage,
        normalized_type,
        list(resistances),
        list(immunities),
        list(vulnerabilities),
    )
    if applied_damage != final_damage:
        return applied_damage, True

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
