"""
api.combat.spell_effects — shared spell damage/healing effect helpers.
"""
from typing import Any

from models import Character
from api.combat._shared import _do_concentration_check, svc
from services.dnd_rules import roll_dice


SPELL_CONDITIONS: dict[str, tuple[str, str | None]] = {
    "Hold Person": ("paralyzed", "wis"),
    "定身术": ("paralyzed", "wis"),
    "Entangle": ("restrained", "str"),
    "纠缠术": ("restrained", "str"),
    "Web": ("restrained", "dex"),
    "蛛网": ("restrained", "dex"),
    "Sleep": ("unconscious", None),
    "睡眠术": ("unconscious", None),
    "Command": ("commanded", "wis"),
    "命令术": ("commanded", "wis"),
    "Faerie Fire": ("faerie_fire", "dex"),
    "妖火": ("faerie_fire", "dex"),
    "Blindness/Deafness": ("blinded", "con"),
    "目盲/耳聋": ("blinded", "con"),
    "Fear": ("frightened", "wis"),
    "恐惧术": ("frightened", "wis"),
    "Silence": ("silenced", None),
    "沉默术": ("silenced", None),
    "Hex": ("hexed", None),
    "妖术": ("hexed", None),
    "Bane": ("baned", "cha"),
    "灾祸术": ("baned", "cha"),
}


def resolve_spell_condition(spell_name: str, spell: dict[str, Any]) -> tuple[str, str | None]:
    """Return the condition and saving throw ability for a control/utility spell."""
    return SPELL_CONDITIONS.get(spell_name, ("affected", spell.get("save")))


def apply_frontend_dice_override(
    *,
    value: int,
    dice_detail: dict[str, Any],
    damage_values: list[int] | None,
    modifier: int,
) -> tuple[int, dict[str, Any]]:
    """Use frontend 3D dice values while preserving the existing dice_detail shape."""
    if not damage_values:
        return value, dice_detail

    updated = dict(dice_detail or {})
    total = sum(damage_values) + modifier
    updated["total"] = total
    if "base_roll" in updated:
        updated["base_roll"] = {
            **updated["base_roll"],
            "rolls": damage_values,
            "total": sum(damage_values),
        }
    return total, updated


async def roll_spell_save(
    db,
    enemies: list[dict[str, Any]],
    target_id: str,
    *,
    save_ability: str | None,
    spell_save_dc: int,
):
    """Roll a per-target spell save result, or return None for spells without saves."""
    if not save_ability:
        return None

    target_enemy = next((e for e in enemies if e.get("id") == target_id), None)
    target_char = None if target_enemy else await db.get(Character, target_id)
    t_derived = (
        target_enemy.get("derived", {}) if target_enemy
        else (target_char.derived or {} if target_char else {})
    )
    t_saves = t_derived.get("saving_throws", {})
    save_mod = t_saves.get(
        save_ability,
        t_derived.get("ability_modifiers", {}).get(save_ability, 0),
    )

    from services.dnd_rules import roll_dice as _roll_d20
    d20 = _roll_d20("1d20")["rolls"][0]
    save_total = d20 + save_mod
    saved = save_total >= spell_save_dc
    return {
        "ability": save_ability,
        "dc": spell_save_dc,
        "d20": d20,
        "modifier": save_mod,
        "total": save_total,
        "success": saved,
    }


async def apply_spell_damage_to_target(
    db,
    session_id: str,
    enemies: list[dict[str, Any]],
    target_id: str,
    damage: int,
    *,
    save_result=None,
):
    """Apply spell damage to an enemy dict or Character and return response result plus conc log."""
    target_enemy = next((e for e in enemies if e.get("id") == target_id), None)
    if target_enemy:
        target_enemy["hp_current"] = svc.apply_damage(
            target_enemy.get("hp_current", 0),
            damage,
            target_enemy.get("derived", {}).get("hp_max", 10),
        )
        return {
            "target_id": target_id,
            "target_name": target_enemy.get("name", "敌人"),
            "damage": damage,
            "new_hp": target_enemy["hp_current"],
            "save": save_result,
        }, None

    tc = await db.get(Character, target_id)
    if not tc:
        return None, None

    tc.hp_current = svc.apply_damage(
        tc.hp_current,
        damage,
        (tc.derived or {}).get("hp_max", tc.hp_current),
    )
    conc_log = await _do_concentration_check(tc, damage, session_id)
    return {
        "target_id": target_id,
        "target_name": tc.name,
        "damage": damage,
        "new_hp": tc.hp_current,
        "save": save_result,
    }, conc_log


async def apply_spell_heal_to_target(db, target_id: str, heal: int):
    """Apply spell healing to a Character and return response result."""
    tc = await db.get(Character, target_id)
    if not tc:
        return None

    tc.hp_current = svc.apply_heal(
        tc.hp_current,
        heal,
        (tc.derived or {}).get("hp_max", tc.hp_current),
    )
    return {
        "target_id": target_id,
        "target_name": tc.name,
        "heal": heal,
        "new_hp": tc.hp_current,
    }


async def apply_control_spell_to_target(
    db,
    enemies: list[dict[str, Any]],
    target_id: str,
    *,
    condition_name: str,
    save_ability: str | None,
    spell_save_dc: int,
):
    """Resolve a control spell save and apply its condition if the target fails."""
    saved = False
    save_detail = None

    target_enemy = next((e for e in enemies if e["id"] == target_id), None)
    target_char = None if target_enemy else await db.get(Character, target_id)

    if save_ability:
        if target_enemy:
            target_scores = target_enemy.get("ability_scores", {})
            target_mod = (target_scores.get(save_ability, 10) - 10) // 2
        elif target_char:
            target_mod = (target_char.derived or {}).get("saving_throws", {}).get(save_ability, 0)
        else:
            target_mod = 0

        save_roll = roll_dice("1d20")["rolls"][0]
        save_total = save_roll + target_mod
        saved = save_total >= spell_save_dc
        save_detail = {
            "ability": save_ability,
            "dc": spell_save_dc,
            "d20": save_roll,
            "modifier": target_mod,
            "total": save_total,
            "success": saved,
        }

    if not saved:
        if target_enemy:
            conditions = target_enemy.get("conditions", [])
            if condition_name not in conditions:
                conditions.append(condition_name)
                target_enemy["conditions"] = conditions
        elif target_char:
            conditions = list(target_char.conditions or [])
            if condition_name not in conditions:
                conditions.append(condition_name)
                target_char.conditions = conditions

    return {
        "condition_name": condition_name,
        "save_detail": save_detail,
        "saved": saved,
        "applied": not saved,
    }
