from __future__ import annotations

from typing import Any

from services.combat_attack_roll_service import CombatAttackRollError
from services.dnd_rules import WEAPONS

TWO_WEAPON_REQUIRED_MESSAGE = (
    "Two-weapon fighting requires two equipped light melee weapons and no equipped shield"
)


def get_two_weapon_fighting_error(actor: Any | None) -> str | None:
    equipment = getattr(actor, "equipment", None) or {}
    if _has_equipped_shield(equipment):
        return TWO_WEAPON_REQUIRED_MESSAGE

    weapons = [
        weapon
        for weapon in _equipped_weapons(equipment)
        if _is_light_melee_weapon(weapon)
    ]
    if len(weapons) < 2:
        return TWO_WEAPON_REQUIRED_MESSAGE
    return None


def validate_two_weapon_fighting_equipment(actor: Any | None) -> None:
    error = get_two_weapon_fighting_error(actor)
    if error:
        raise CombatAttackRollError(400, error)


def _equipped_weapons(equipment: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        weapon
        for weapon in equipment.get("weapons", []) or []
        if isinstance(weapon, dict) and weapon.get("equipped")
    ]


def _has_equipped_shield(equipment: dict[str, Any]) -> bool:
    shield = equipment.get("shield")
    return isinstance(shield, dict) and shield.get("equipped") is not False


def _is_light_melee_weapon(weapon: dict[str, Any]) -> bool:
    return _has_property(weapon, "light") and _is_melee_weapon(weapon)


def _is_melee_weapon(weapon: dict[str, Any]) -> bool:
    weapon_type = str(_weapon_field(weapon, "type", "")).lower()
    return "melee" in weapon_type


def _has_property(weapon: dict[str, Any], property_name: str) -> bool:
    return property_name in _weapon_properties(weapon)


def _weapon_properties(weapon: dict[str, Any]) -> list[str]:
    properties = _weapon_field(weapon, "properties", [])
    if isinstance(properties, str):
        return [properties.lower()]
    return [str(prop).lower() for prop in properties or []]


def _weapon_field(weapon: dict[str, Any], key: str, default: Any) -> Any:
    if key in weapon:
        return weapon.get(key)
    return WEAPONS.get(weapon.get("name", ""), {}).get(key, default)
