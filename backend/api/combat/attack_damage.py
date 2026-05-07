"""
api.combat.attack_damage — helpers for the two-step damage-roll endpoint.
"""
from dataclasses import dataclass
from typing import Any, Callable

from services.dnd_rules import roll_dice
from models import Character
from api.combat._shared import _do_concentration_check, svc


@dataclass(frozen=True)
class PendingDamageRoll:
    damage_dice_expr: str
    damage_roll_result: dict[str, Any]
    damage_rolls: list[int]
    damage: int
    crit_extra: int


def find_pending_attack(turn_states: dict[str, Any], pending_attack_id: str):
    """Find a pending attack by id across all entity turn states."""
    for entity_id, entity_ts in (turn_states or {}).items():
        pending = entity_ts.get("pending_attack")
        if pending and pending.get("pending_attack_id") == pending_attack_id:
            return entity_id, pending
    return None, None


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


async def apply_attack_damage_to_target(
    db,
    *,
    session_id: str,
    enemies: list[dict[str, Any]],
    target_id: str,
    target_is_enemy: bool,
    damage: int,
):
    """Apply final weapon damage to an enemy dict or Character."""
    if target_is_enemy:
        target_new_hp = None
        for enemy in enemies:
            if enemy.get("id") == target_id:
                enemy["hp_current"] = svc.apply_damage(
                    enemy.get("hp_current", 0),
                    damage,
                    enemy.get("derived", {}).get("hp_max", 10),
                )
                target_new_hp = enemy["hp_current"]
        return target_new_hp, None

    tchar = await db.get(Character, target_id)
    if not tchar:
        return None, None

    tchar.hp_current = svc.apply_damage(
        tchar.hp_current,
        damage,
        (tchar.derived or {}).get("hp_max", tchar.hp_current),
    )
    conc_log = await _do_concentration_check(tchar, damage, session_id)
    return tchar.hp_current, conc_log
