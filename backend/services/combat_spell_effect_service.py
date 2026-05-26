"""
services.combat_spell_effect_service — shared spell damage/healing effect helpers.
"""
from typing import Any

from models import Character
from services.combat_concentration_service import do_concentration_check
from services.combat_service import CombatService
from services.combat_spell_resolution_service import apply_frontend_dice_override
from services.dnd_rules import (
    apply_character_damage,
    apply_character_healing,
    roll_saving_throw,
)

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
    if target_enemy:
        return roll_saving_throw(target_enemy, save_ability, spell_save_dc)
    if target_character:
        return roll_saving_throw(
            {
                "derived": target_character.derived or {},
                "conditions": target_character.conditions or [],
                "condition_durations": target_character.condition_durations or {},
            },
            save_ability,
            spell_save_dc,
        )
    return roll_saving_throw({}, save_ability, spell_save_dc)


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

    damage_result = apply_character_damage(target_character, damage)
    concentration_log = await do_concentration_check(target_character, damage, session_id)
    return {
        "target_id": target_id,
        "target_name": target_character.name,
        "damage": damage,
        "new_hp": damage_result["hp_after"],
        "death_saves": damage_result["death_saves"],
        "save": save_result,
    }, concentration_log


async def apply_spell_heal_to_target(db, target_id: str, heal: int):
    """Apply spell healing to a Character and return response result."""
    target_character = await db.get(Character, target_id)
    if not target_character:
        return None

    heal_result = apply_character_healing(target_character, heal)
    return {
        "target_id": target_id,
        "target_name": target_character.name,
        "heal": heal,
        "new_hp": heal_result["hp_after"],
        "revived": heal_result["revived"],
        "death_saves": heal_result["death_saves"],
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
            save_detail = roll_saving_throw(target_enemy, save_ability, spell_save_dc)
        elif target_character:
            save_detail = roll_saving_throw(
                {
                    "derived": target_character.derived or {},
                    "conditions": target_character.conditions or [],
                    "condition_durations": target_character.condition_durations or {},
                },
                save_ability,
                spell_save_dc,
            )
        else:
            save_detail = roll_saving_throw({}, save_ability, spell_save_dc)
        saved = save_detail["success"]

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
