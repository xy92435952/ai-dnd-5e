"""
services.combat_spell_effect_service — shared spell damage/healing effect helpers.
"""
from typing import Any

from models import Character
from services.combat_concentration_service import do_concentration_check
from services.combat_service import CombatService
from services.combat_spell_resolution_service import apply_frontend_dice_override
from services.dnd_rules import get_effective_hp_max, roll_dice

svc = CombatService()


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

    target_enemy = next((enemy for enemy in enemies if enemy.get("id") == target_id), None)
    target_character = None if target_enemy else await db.get(Character, target_id)
    target_derived = (
        target_enemy.get("derived", {}) if target_enemy
        else (target_character.derived or {} if target_character else {})
    )
    target_saves = target_derived.get("saving_throws", {})
    save_modifier = target_saves.get(
        save_ability,
        target_derived.get("ability_modifiers", {}).get(save_ability, 0),
    )

    d20 = roll_dice("1d20")["rolls"][0]
    save_total = d20 + save_modifier
    saved = save_total >= spell_save_dc
    return {
        "ability": save_ability,
        "dc": spell_save_dc,
        "d20": d20,
        "modifier": save_modifier,
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
    target_enemy = next((enemy for enemy in enemies if enemy.get("id") == target_id), None)
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

    target_character = await db.get(Character, target_id)
    if not target_character:
        return None, None

    target_character.hp_current = svc.apply_damage(
        target_character.hp_current,
        damage,
        get_effective_hp_max(target_character),
    )
    concentration_log = await do_concentration_check(target_character, damage, session_id)
    return {
        "target_id": target_id,
        "target_name": target_character.name,
        "damage": damage,
        "new_hp": target_character.hp_current,
        "save": save_result,
    }, concentration_log


async def apply_spell_heal_to_target(db, target_id: str, heal: int):
    """Apply spell healing to a Character and return response result."""
    target_character = await db.get(Character, target_id)
    if not target_character:
        return None

    target_character.hp_current = svc.apply_heal(
        target_character.hp_current,
        heal,
        get_effective_hp_max(target_character),
    )
    return {
        "target_id": target_id,
        "target_name": target_character.name,
        "heal": heal,
        "new_hp": target_character.hp_current,
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

    target_enemy = next((enemy for enemy in enemies if enemy["id"] == target_id), None)
    target_character = None if target_enemy else await db.get(Character, target_id)

    if save_ability:
        if target_enemy:
            target_scores = target_enemy.get("ability_scores", {})
            target_modifier = (target_scores.get(save_ability, 10) - 10) // 2
        elif target_character:
            target_modifier = (target_character.derived or {}).get("saving_throws", {}).get(save_ability, 0)
        else:
            target_modifier = 0

        save_roll = roll_dice("1d20")["rolls"][0]
        save_total = save_roll + target_modifier
        saved = save_total >= spell_save_dc
        save_detail = {
            "ability": save_ability,
            "dc": spell_save_dc,
            "d20": save_roll,
            "modifier": target_modifier,
            "total": save_total,
            "success": saved,
        }

    if not saved:
        if target_enemy:
            conditions = target_enemy.get("conditions", [])
            if condition_name not in conditions:
                conditions.append(condition_name)
                target_enemy["conditions"] = conditions
        elif target_character:
            conditions = list(target_character.conditions or [])
            if condition_name not in conditions:
                conditions.append(condition_name)
                target_character.conditions = conditions

    return {
        "condition_name": condition_name,
        "save_detail": save_detail,
        "saved": saved,
        "applied": not saved,
    }
