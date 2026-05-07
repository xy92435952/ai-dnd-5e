"""
api.combat.attack_modifiers — shared attack roll modifier helpers.
"""
from dataclasses import dataclass
from typing import Any

from api.combat._shared import _has_adjacent_enemy, svc


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

    has_crossbow_expert = (
        attacker_derived
        .get("feat_effects", {})
        .get("Crossbow Expert", {})
        .get("crossbow_expert", False)
    )
    if _has_adjacent_enemy(attacker_id, enemies, positions) and not has_crossbow_expert:
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
    atk_pos = positions.get(str(attacker_id))
    tgt_pos = positions.get(str(target_id))
    if not atk_pos or not tgt_pos:
        return 0

    cover_bonus = svc.get_cover_bonus(grid_data, atk_pos, tgt_pos)
    has_sharpshooter = bool(attacker_derived.get("feat_effects", {}).get("Sharpshooter"))
    if has_sharpshooter and is_ranged:
        return 0

    return cover_bonus


def choose_feat_power_attack(
    *,
    attacker_derived: dict[str, Any],
    target_derived: dict[str, Any],
    cover_bonus: int,
    is_ranged: bool,
) -> FeatPowerAttack:
    """Auto-select GWM/Sharpshooter power attack using the endpoint's existing heuristic."""
    feat_effects = attacker_derived.get("feat_effects", {})

    if not is_ranged and feat_effects.get("Great Weapon Master"):
        equipped_type = attacker_derived.get("equipped_weapon_type", "")
        if "heavy" in str(equipped_type).lower() or "two-handed" in str(equipped_type).lower():
            effective_ac = target_derived.get("ac", 13) + cover_bonus
            attack_bonus = attacker_derived.get("attack_bonus", 3)
            if attack_bonus - 5 + 10 >= effective_ac:
                return FeatPowerAttack(active=True, hit_penalty=5, bonus_damage=10)

    if is_ranged and feat_effects.get("Sharpshooter"):
        effective_ac = target_derived.get("ac", 13) + cover_bonus
        attack_bonus = attacker_derived.get("ranged_attack_bonus", 3)
        if attack_bonus - 5 + 10 >= effective_ac:
            return FeatPowerAttack(active=True, hit_penalty=5, bonus_damage=10)

    return FeatPowerAttack()


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
        attack_attacker_derived[bonus_key] = (
            attacker_derived.get(bonus_key, 3) - power.hit_penalty
        )

    return attack_attacker_derived, attack_target_derived


def build_weapon_damage_dice(character, *, is_ranged: bool, is_offhand: bool) -> WeaponDamageDice:
    """Build the damage dice expression used by the two-step attack flow."""
    derived = character.derived or {}
    equipment = character.equipment or {}
    equipped_weapons = equipment.get("weapons", [])
    weapon_hit_die = derived.get("hit_die", 8)
    weapon_damage = None

    if equipped_weapons:
        equipped = next(
            (w for w in equipped_weapons if w.get("equipped")),
            equipped_weapons[0] if equipped_weapons else None,
        )
        if equipped:
            weapon_damage = equipped.get("damage", f"1d{weapon_hit_die}")

    mods = derived.get("ability_modifiers", {})
    raw_mod = mods.get("dex", 0) if is_ranged else mods.get("str", 0)
    if is_offhand and not derived.get("two_weapon_fighting", False):
        dmg_mod = 0
    else:
        dmg_mod = raw_mod

    if weapon_damage:
        damage_dice = f"{weapon_damage}+{dmg_mod}" if dmg_mod >= 0 else f"{weapon_damage}{dmg_mod}"
    else:
        damage_dice = f"1d{weapon_hit_die}+{dmg_mod}" if dmg_mod >= 0 else f"1d{weapon_hit_die}{dmg_mod}"

    return WeaponDamageDice(
        damage_dice=damage_dice,
        hit_die=weapon_hit_die,
        dmg_mod=dmg_mod,
    )
