from dataclasses import dataclass
from typing import Any

from services.combat_ammunition_service import choose_attack_weapon
from services.combat_grid_service import has_adjacent_enemy
from services.combat_service import CombatService

svc = CombatService()


@dataclass(frozen=True)
class FeatPowerAttack:
    active: bool = False
    hit_penalty: int = 0
    bonus_damage: int = 0


@dataclass(frozen=True)
class WeaponDamageDice:
    damage_dice: str
    hit_die: int
    dmg_mod: int


@dataclass(frozen=True)
class CoverInfo:
    bonus: int = 0
    raw_bonus: int = 0
    ignored_by: str | None = None
    cells: tuple[dict[str, Any], ...] = ()

    def to_prediction_detail(self) -> dict[str, Any] | None:
        if self.raw_bonus <= 0 and not self.cells:
            return None
        return {
            "bonus": self.bonus,
            "raw_bonus": self.raw_bonus,
            "ignored_by": self.ignored_by,
            "cells": list(self.cells),
        }


def apply_ranged_close_penalty(
    *,
    atk_dis: bool,
    is_ranged: bool,
    attacker_id: str,
    enemies: list[dict[str, Any]],
    positions: dict[str, Any],
    attacker_derived: dict[str, Any],
) -> tuple[bool, bool]:
    """Apply close-quarters ranged disadvantage unless Crossbow Expert negates it."""
    if not is_ranged:
        return atk_dis, False

    has_crossbow_expert = _has_feat_effect(
        attacker_derived,
        "Crossbow Expert",
        "crossbow_expert",
    )
    if has_adjacent_enemy(attacker_id, enemies, positions) and not has_crossbow_expert:
        return True, True

    return atk_dis, False


def calculate_cover_bonus(
    *,
    grid_data: dict[str, Any],
    positions: dict[str, Any],
    attacker_id: str,
    target_id: str,
    attacker_derived: dict[str, Any],
    is_ranged: bool,
) -> int:
    """Calculate cover bonus and apply Sharpshooter cover bypass for ranged attacks."""
    return calculate_cover_info(
        grid_data=grid_data,
        positions=positions,
        attacker_id=attacker_id,
        target_id=target_id,
        attacker_derived=attacker_derived,
        is_ranged=is_ranged,
    ).bonus


def calculate_cover_info(
    *,
    grid_data: dict[str, Any],
    positions: dict[str, Any],
    attacker_id: str,
    target_id: str,
    attacker_derived: dict[str, Any],
    is_ranged: bool,
) -> CoverInfo:
    """Calculate applied cover and keep the path cells that explain it."""
    attacker_position = positions.get(str(attacker_id))
    target_position = positions.get(str(target_id))
    if not attacker_position or not target_position:
        return CoverInfo()

    analysis = svc.get_cover_analysis(grid_data, attacker_position, target_position)
    raw_bonus = int(analysis.get("bonus") or 0)
    cells = tuple(analysis.get("cells") or ())
    has_sharpshooter = _has_feat_effect(attacker_derived, "Sharpshooter", "sharpshooter")
    if has_sharpshooter and is_ranged and raw_bonus > 0:
        return CoverInfo(bonus=0, raw_bonus=raw_bonus, ignored_by="Sharpshooter", cells=cells)

    return CoverInfo(bonus=raw_bonus, raw_bonus=raw_bonus, cells=cells)


def choose_feat_power_attack(
    *,
    attacker_derived: dict[str, Any],
    target_derived: dict[str, Any],
    cover_bonus: int,
    is_ranged: bool,
) -> FeatPowerAttack:
    """Auto-select GWM/Sharpshooter power attack using the endpoint's existing heuristic."""
    if not is_ranged and _has_feat_effect(attacker_derived, "Great Weapon Master", "gwm"):
        equipped_type = attacker_derived.get("equipped_weapon_type", "")
        if "heavy" in str(equipped_type).lower() or "two-handed" in str(equipped_type).lower():
            effective_ac = target_derived.get("ac", 13) + cover_bonus
            attack_bonus = attacker_derived.get("attack_bonus", 3)
            if attack_bonus - 5 + 10 >= effective_ac:
                return FeatPowerAttack(active=True, hit_penalty=5, bonus_damage=10)

    if is_ranged and _has_feat_effect(attacker_derived, "Sharpshooter", "sharpshooter"):
        effective_ac = target_derived.get("ac", 13) + cover_bonus
        attack_bonus = attacker_derived.get("ranged_attack_bonus", 3)
        if attack_bonus - 5 + 10 >= effective_ac:
            return FeatPowerAttack(active=True, hit_penalty=5, bonus_damage=10)

    return FeatPowerAttack()


def _has_feat_effect(attacker_derived: dict[str, Any], feat_name: str, effect_key: str) -> bool:
    feat_effect = (attacker_derived.get("feat_effects") or {}).get(feat_name)
    if isinstance(feat_effect, dict):
        return bool(feat_effect.get(effect_key))
    return bool(feat_effect)


def build_attack_deriveds(
    *,
    attacker_derived: dict[str, Any],
    target_derived: dict[str, Any],
    cover_bonus: int,
    is_ranged: bool,
    power: FeatPowerAttack,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return modified attacker/target derived dicts for this attack roll."""
    attack_target_derived = dict(target_derived)
    if cover_bonus > 0:
        attack_target_derived["ac"] = target_derived.get("ac", 10) + cover_bonus

    attack_attacker_derived = dict(attacker_derived)
    if power.active:
        bonus_key = "ranged_attack_bonus" if is_ranged else "attack_bonus"
        attack_attacker_derived[bonus_key] = attacker_derived.get(bonus_key, 3) - power.hit_penalty

    return attack_attacker_derived, attack_target_derived


def build_weapon_damage_dice(
    character,
    *,
    is_ranged: bool,
    is_offhand: bool,
    weapon: dict[str, Any] | None = None,
) -> WeaponDamageDice:
    """Build the damage dice expression used by the two-step attack flow."""
    derived = character.derived or {}
    equipment = character.equipment or {}
    equipped_weapons = equipment.get("weapons", [])
    weapon_hit_die = derived.get("hit_die", 8)
    weapon_damage = None

    if weapon:
        weapon_damage = weapon.get("damage", f"1d{weapon_hit_die}")
    elif equipped_weapons:
        selected_weapon = choose_attack_weapon(equipment, is_ranged=is_ranged)
        if selected_weapon:
            weapon_damage = selected_weapon.get("damage", f"1d{weapon_hit_die}")
        else:
            equipped = None
            if not is_ranged:
                equipped = next(
                    (weapon for weapon in equipped_weapons if weapon.get("equipped")),
                    equipped_weapons[0] if equipped_weapons else None,
                )
            if equipped:
                weapon_damage = equipped.get("damage", f"1d{weapon_hit_die}")

    if not weapon_damage and equipped_weapons:
        equipped = next(
            (weapon for weapon in equipped_weapons if weapon.get("equipped")),
            equipped_weapons[0] if equipped_weapons else None,
        )
        if equipped:
            weapon_damage = equipped.get("damage", f"1d{weapon_hit_die}")

    modifiers = derived.get("ability_modifiers", {})
    raw_modifier = modifiers.get("dex", 0) if is_ranged else modifiers.get("str", 0)
    damage_modifier = 0 if is_offhand and not derived.get("two_weapon_fighting", False) else raw_modifier

    if weapon_damage:
        damage_dice = (
            f"{weapon_damage}+{damage_modifier}"
            if damage_modifier >= 0
            else f"{weapon_damage}{damage_modifier}"
        )
    else:
        damage_dice = (
            f"1d{weapon_hit_die}+{damage_modifier}"
            if damage_modifier >= 0
            else f"1d{weapon_hit_die}{damage_modifier}"
        )

    return WeaponDamageDice(
        damage_dice=damage_dice,
        hit_die=weapon_hit_die,
        dmg_mod=damage_modifier,
    )
