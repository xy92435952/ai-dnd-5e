from dataclasses import dataclass
from typing import Any, Callable

from services.dnd_rules import roll_dice


@dataclass(frozen=True)
class PendingDamageRoll:
    damage_dice_expr: str
    damage_roll_result: dict[str, Any]
    damage_rolls: list[int]
    damage: int
    crit_extra: int


@dataclass(frozen=True)
class DamageExtraResult:
    damage: int
    extra_damage_notes: list[str]
    sneak_attack_applied: bool = False
    sneak_attack_damage: int = 0
    sneak_attack_dice: str = ""


def roll_pending_damage(
    *,
    hit_die: int,
    dmg_mod: int,
    is_crit: bool,
    damage_values: list[int] | None = None,
) -> PendingDamageRoll:
    """Roll base weapon damage, apply frontend dice override, then add crit dice."""
    damage_dice_expr = f"1d{hit_die}+{dmg_mod}" if dmg_mod >= 0 else f"1d{hit_die}{dmg_mod}"
    damage_roll_result = roll_dice(damage_dice_expr)
    damage = damage_roll_result["total"]
    damage_rolls = damage_roll_result.get("rolls", [])

    if damage_values:
        damage_rolls = damage_values
        damage_roll_result["rolls"] = damage_values
        damage_roll_result["total"] = sum(damage_values) + dmg_mod
        damage = damage_roll_result["total"]

    crit_extra = 0
    if is_crit:
        extra = roll_dice(f"1d{hit_die}")
        crit_extra = extra["total"]
        damage += crit_extra

    return PendingDamageRoll(
        damage_dice_expr=damage_dice_expr,
        damage_roll_result=damage_roll_result,
        damage_rolls=damage_rolls,
        damage=damage,
        crit_extra=crit_extra,
    )


def apply_basic_damage_bonuses(
    *,
    base_damage: int,
    pending: dict[str, Any],
    attacker_derived: dict[str, Any],
    level: int,
    is_ranged: bool,
    get_rage_bonus: Callable[[int], int],
):
    """Apply feat, dueling, and rage bonuses shared by two-step damage resolution."""
    damage = base_damage
    extra_damage_notes = []

    feat_power_bonus_dmg = pending.get("feat_power_bonus_dmg", 0)
    if pending.get("feat_power_attack") and feat_power_bonus_dmg > 0:
        damage += feat_power_bonus_dmg
        feat_name = "巨武器大师" if not is_ranged else "神射手"
        extra_damage_notes.append(f"{feat_name}+{feat_power_bonus_dmg}")

    dueling_bonus = 0
    if not is_ranged:
        melee_bonus = attacker_derived.get("melee_damage_bonus", 0)
        if melee_bonus > 0:
            damage += melee_bonus
            dueling_bonus = melee_bonus
            extra_damage_notes.append(f"决斗+{melee_bonus}")

    rage_bonus = 0
    if pending.get("is_raging") and not is_ranged:
        rage_bonus = get_rage_bonus(level)
        damage += rage_bonus
        extra_damage_notes.append(f"狂暴+{rage_bonus}")

    return damage, extra_damage_notes, dueling_bonus, rage_bonus, feat_power_bonus_dmg


def apply_divine_fury(
    *,
    damage: int,
    extra_damage_notes: list[str],
    pending: dict[str, Any],
    subclass_effects: dict[str, Any],
    level: int,
    turn_state: dict[str, Any],
) -> DamageExtraResult:
    notes = list(extra_damage_notes)
    if pending.get("is_raging") and subclass_effects.get("divine_fury"):
        if turn_state.get("attacks_made", 1) <= 1:
            fury_roll = roll_dice(f"1d6+{level // 2}")
            damage += fury_roll["total"]
            notes.append(f"神圣狂怒+{fury_roll['total']}")

    return DamageExtraResult(damage=damage, extra_damage_notes=notes)


def apply_sneak_attack(
    *,
    damage: int,
    extra_damage_notes: list[str],
    attacker_class: str,
    level: int,
    pending: dict[str, Any],
    subclass_effects: dict[str, Any],
    turn_state: dict[str, Any],
    target_id: str,
    attacker_id: str,
    ally_list: list[dict[str, Any]],
    enemies: list[dict[str, Any]],
    positions: dict[str, Any],
    has_ally_adjacent_to: Callable[[str, str, list[dict[str, Any]], dict[str, Any]], bool],
    check_sneak_attack: Callable[..., bool],
    calc_sneak_attack_dice: Callable[[int], int],
) -> DamageExtraResult:
    notes = list(extra_damage_notes)
    if attacker_class != "Rogue":
        return DamageExtraResult(damage=damage, extra_damage_notes=notes)

    has_adv = pending.get("advantage", False)
    ally_adjacent = has_ally_adjacent_to(target_id, attacker_id, ally_list, positions)

    is_swashbuckler = subclass_effects.get("swashbuckler", False)
    no_other_enemy_adjacent = False
    if is_swashbuckler:
        other_enemies = [
            enemy for enemy in enemies
            if enemy["id"] != target_id and enemy.get("hp_current", 0) > 0
        ]
        no_other_enemy_adjacent = not has_ally_adjacent_to(
            attacker_id,
            target_id,
            other_enemies,
            positions,
        )

    attacks_before = turn_state.get("attacks_made", 1) - 1
    can_sneak = check_sneak_attack(
        attacker_class,
        has_adv,
        ally_adjacent,
        swashbuckler=is_swashbuckler,
        no_other_enemy_adjacent=no_other_enemy_adjacent,
    )
    if can_sneak and attacks_before == 0:
        dice_count = calc_sneak_attack_dice(level)
        sneak_roll = roll_dice(f"{dice_count}d6")
        sneak_damage = sneak_roll["total"]
        sneak_dice = f"{dice_count}d6"
        damage += sneak_damage
        notes.append(f"偷袭{dice_count}d6={sneak_damage}")
        return DamageExtraResult(
            damage=damage,
            extra_damage_notes=notes,
            sneak_attack_applied=True,
            sneak_attack_damage=sneak_damage,
            sneak_attack_dice=sneak_dice,
        )

    return DamageExtraResult(damage=damage, extra_damage_notes=notes)


def apply_target_resistance(
    *,
    damage: int,
    damage_type: str,
    target_id: str,
    target_is_enemy: bool,
    enemies: list[dict[str, Any]],
    apply_damage_with_resistance: Callable[[int, str, list, list, list], int],
) -> int:
    if not target_is_enemy:
        return damage

    enemy_data = next((enemy for enemy in enemies if enemy["id"] == target_id), {})
    return apply_damage_with_resistance(
        damage,
        damage_type,
        enemy_data.get("resistances", []),
        enemy_data.get("immunities", []),
        enemy_data.get("vulnerabilities", []),
    )


def resolve_damage_extras(
    *,
    damage: int,
    extra_damage_notes: list[str],
    pending: dict[str, Any],
    attacker_class: str,
    level: int,
    subclass_effects: dict[str, Any],
    turn_state: dict[str, Any],
    target_id: str,
    attacker_id: str,
    target_is_enemy: bool,
    ally_list: list[dict[str, Any]],
    enemies: list[dict[str, Any]],
    positions: dict[str, Any],
    damage_type: str,
    has_ally_adjacent_to: Callable[[str, str, list[dict[str, Any]], dict[str, Any]], bool],
    check_sneak_attack: Callable[..., bool],
    calc_sneak_attack_dice: Callable[[int], int],
    apply_damage_with_resistance: Callable[[int, str, list, list, list], int],
) -> DamageExtraResult:
    divine = apply_divine_fury(
        damage=damage,
        extra_damage_notes=extra_damage_notes,
        pending=pending,
        subclass_effects=subclass_effects,
        level=level,
        turn_state=turn_state,
    )

    sneak = apply_sneak_attack(
        damage=divine.damage,
        extra_damage_notes=divine.extra_damage_notes,
        attacker_class=attacker_class,
        level=level,
        pending=pending,
        subclass_effects=subclass_effects,
        turn_state=turn_state,
        target_id=target_id,
        attacker_id=attacker_id,
        ally_list=ally_list,
        enemies=enemies,
        positions=positions,
        has_ally_adjacent_to=has_ally_adjacent_to,
        check_sneak_attack=check_sneak_attack,
        calc_sneak_attack_dice=calc_sneak_attack_dice,
    )

    final_damage = apply_target_resistance(
        damage=sneak.damage,
        damage_type=damage_type,
        target_id=target_id,
        target_is_enemy=target_is_enemy,
        enemies=enemies,
        apply_damage_with_resistance=apply_damage_with_resistance,
    )

    return DamageExtraResult(
        damage=final_damage,
        extra_damage_notes=sneak.extra_damage_notes,
        sneak_attack_applied=sneak.sneak_attack_applied,
        sneak_attack_damage=sneak.sneak_attack_damage,
        sneak_attack_dice=sneak.sneak_attack_dice,
    )
