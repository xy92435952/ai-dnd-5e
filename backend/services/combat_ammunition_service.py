from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from services.combat_attack_roll_service import CombatAttackRollError
from services.dnd_rules import WEAPONS


@dataclass(frozen=True)
class WeaponResourceUse:
    weapon: dict[str, Any] | None = None
    weapon_name: str | None = None
    resource_type: str | None = None
    consumed: bool = False
    ammo_remaining: int | None = None
    weapon_removed: bool = False

    def to_dict(self) -> dict[str, Any]:
        if not self.consumed:
            return {}

        payload: dict[str, Any] = {
            "weapon": self.weapon_name,
            "resource_type": self.resource_type,
            "consumed": True,
        }
        if self.ammo_remaining is not None:
            payload["ammo_remaining"] = self.ammo_remaining
        if self.weapon_removed:
            payload["weapon_removed"] = True
        return payload


def consume_attack_weapon_resource(character, *, is_ranged: bool) -> WeaponResourceUse:
    """Consume ammo/thrown inventory for a committed ranged weapon attack."""
    equipment = deepcopy(getattr(character, "equipment", None) or {})
    weapons = list(equipment.get("weapons", []))

    selected = _select_attack_weapon_index(weapons, is_ranged=is_ranged)
    if selected is None:
        if is_ranged:
            raise CombatAttackRollError(400, "No ranged or thrown weapon available")
        return WeaponResourceUse()

    weapon_index, weapon = selected
    weapon_name = weapon.get("name")

    if not is_ranged:
        return WeaponResourceUse(weapon=dict(weapon), weapon_name=weapon_name)

    if _has_ammunition_property(weapon):
        if "ammo" not in weapon:
            return WeaponResourceUse(
                weapon=dict(weapon),
                weapon_name=weapon_name,
                resource_type="ammunition",
            )

        ammo = _as_int(weapon.get("ammo"), 0)
        if ammo <= 0:
            raise CombatAttackRollError(400, f"No ammunition remaining for {weapon_name}")

        updated_weapon = {**weapon, "ammo": ammo - 1}
        weapons[weapon_index] = updated_weapon
        equipment["weapons"] = weapons
        character.equipment = equipment
        return WeaponResourceUse(
            weapon=updated_weapon,
            weapon_name=weapon_name,
            resource_type="ammunition",
            consumed=True,
            ammo_remaining=ammo - 1,
        )

    if _has_thrown_property(weapon):
        quantity = _as_int(weapon.get("quantity"), 1)
        weapon_removed = quantity <= 1
        if quantity > 1:
            updated_weapon = {**weapon, "quantity": quantity - 1}
            weapons[weapon_index] = updated_weapon
        else:
            weapons.pop(weapon_index)
            _equip_replacement_thrown_weapon(weapons, weapon_name)

        equipment["weapons"] = weapons
        character.equipment = equipment
        return WeaponResourceUse(
            weapon=dict(weapon),
            weapon_name=weapon_name,
            resource_type="thrown_weapon",
            consumed=True,
            weapon_removed=weapon_removed,
        )

    return WeaponResourceUse(
        weapon=dict(weapon),
        weapon_name=weapon_name,
        resource_type="ranged_weapon",
    )


def choose_attack_weapon(equipment: dict | None, *, is_ranged: bool) -> dict[str, Any] | None:
    weapons = list((equipment or {}).get("weapons", []))
    selected = _select_attack_weapon_index(weapons, is_ranged=is_ranged)
    if selected is None:
        return None
    return dict(selected[1])


def is_ammunition_weapon(weapon: dict[str, Any]) -> bool:
    return _has_ammunition_property(weapon)


def is_thrown_weapon(weapon: dict[str, Any]) -> bool:
    return _has_thrown_property(weapon)


def _select_attack_weapon_index(
    weapons: list[Any],
    *,
    is_ranged: bool,
) -> tuple[int, dict[str, Any]] | None:
    indexed = [(idx, weapon) for idx, weapon in enumerate(weapons) if isinstance(weapon, dict)]
    if not indexed:
        return None

    if not is_ranged:
        melee_candidates = [
            candidate for candidate in indexed
            if not _is_pure_ranged_weapon(candidate[1])
        ]
        equipped = [candidate for candidate in melee_candidates if candidate[1].get("equipped")]
        return (equipped or melee_candidates or indexed)[0]

    ranged_candidates = [
        candidate for candidate in indexed
        if _is_ranged_weapon(candidate[1]) or _has_thrown_property(candidate[1])
    ]
    if not ranged_candidates:
        return None

    equipped_available = [
        candidate for candidate in ranged_candidates
        if candidate[1].get("equipped") and _has_available_resource(candidate[1])
    ]
    available = [
        candidate for candidate in ranged_candidates
        if _has_available_resource(candidate[1])
    ]
    equipped = [candidate for candidate in ranged_candidates if candidate[1].get("equipped")]
    return (equipped_available or available or equipped or ranged_candidates)[0]


def _has_available_resource(weapon: dict[str, Any]) -> bool:
    if _has_ammunition_property(weapon) and "ammo" in weapon:
        return _as_int(weapon.get("ammo"), 0) > 0
    if _has_thrown_property(weapon):
        return _as_int(weapon.get("quantity"), 1) > 0
    return True


def _equip_replacement_thrown_weapon(weapons: list[Any], weapon_name: str | None) -> None:
    if not weapon_name:
        return
    for weapon in weapons:
        if isinstance(weapon, dict) and weapon.get("name") == weapon_name:
            weapon["equipped"] = True
            return


def _is_ranged_weapon(weapon: dict[str, Any]) -> bool:
    weapon_type = str(_weapon_field(weapon, "type", "")).lower()
    return (
        _has_ammunition_property(weapon)
        or weapon_type in {"simple_ranged", "martial_ranged"}
        or "ranged" in weapon_type
    )


def _is_pure_ranged_weapon(weapon: dict[str, Any]) -> bool:
    return _is_ranged_weapon(weapon) and not _has_thrown_property(weapon)


def _has_ammunition_property(weapon: dict[str, Any]) -> bool:
    return any(prop == "ammunition" for prop in _weapon_properties(weapon))


def _has_thrown_property(weapon: dict[str, Any]) -> bool:
    return any(prop.startswith("thrown") for prop in _weapon_properties(weapon))


def _weapon_properties(weapon: dict[str, Any]) -> list[str]:
    properties = _weapon_field(weapon, "properties", [])
    if isinstance(properties, str):
        return [properties.lower()]
    return [str(prop).lower() for prop in properties or []]


def _weapon_field(weapon: dict[str, Any], key: str, default: Any) -> Any:
    if key in weapon:
        return weapon.get(key)
    return WEAPONS.get(weapon.get("name", ""), {}).get(key, default)


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
