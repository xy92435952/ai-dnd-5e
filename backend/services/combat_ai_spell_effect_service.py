from typing import Any, Callable

from sqlalchemy.orm.attributes import flag_modified

from models import Character
from services.combat_ai_spell_models import AiSpellResolution, CONTROL_CONDITION_MAP
from services.dnd_rules import roll_dice


async def apply_ai_heal_spell(
    db,
    *,
    resolution: AiSpellResolution,
    spell_mod: int,
    bonus_healing: bool,
    spell_service_obj,
) -> None:
    total_heal, _dice_detail = spell_service_obj.resolve_heal(
        resolution.spell_name,
        resolution.spell_level,
        spell_mod,
        bonus_healing,
    )
    if resolution.spell_target:
        target_character = await db.get(Character, resolution.spell_target)
        if target_character:
            hp_max = (target_character.derived or {}).get("hp_max", target_character.hp_current)
            target_character.hp_current = min(hp_max, target_character.hp_current + total_heal)
            resolution.target_new_hp = target_character.hp_current
            resolution.target_name = target_character.name
    resolution.heal = total_heal


async def apply_ai_control_spell(
    db,
    *,
    resolution: AiSpellResolution,
    session,
    enemies: list[dict[str, Any]],
    spell_save_dc: int,
    state: dict[str, Any],
    flag_modified_func: Callable[[Any, str], None] = flag_modified,
    roll_dice_func: Callable[[str], dict[str, Any]] = roll_dice,
) -> None:
    condition = CONTROL_CONDITION_MAP.get(resolution.spell_name, "hexed")
    save_ability = resolution.spell_data.get("save")
    if not resolution.spell_target or not save_ability:
        return

    target_enemy = next(
        (enemy for enemy in enemies if str(enemy.get("id")) == str(resolution.spell_target)),
        None,
    )
    if target_enemy:
        ability_scores = target_enemy.get("ability_scores", {})
        save_mod = (ability_scores.get(save_ability, 10) - 10) // 2
        save_roll = roll_dice_func("1d20")["rolls"][0]
        if save_roll + save_mod < spell_save_dc:
            conditions = target_enemy.get("conditions", [])
            if condition not in conditions:
                conditions.append(condition)
                target_enemy["conditions"] = conditions
            resolution.narration_parts.append(
                f"{target_enemy.get('name')} 未通过豁免，陷入{condition}状态！"
            )
        else:
            resolution.narration_parts.append(f"{target_enemy.get('name')} 通过了豁免！")
        resolution.target_name = target_enemy.get("name", "敌人")
        state["enemies"] = enemies
        session.game_state = dict(state)
        flag_modified_func(session, "game_state")
        return

    target_character = await db.get(Character, resolution.spell_target)
    if target_character:
        target_derived = target_character.derived or {}
        save_mod = target_derived.get("saving_throws", {}).get(save_ability, 0)
        save_roll = roll_dice_func("1d20")["rolls"][0]
        if save_roll + save_mod < spell_save_dc:
            conditions = list(target_character.conditions or [])
            if condition not in conditions:
                conditions.append(condition)
                target_character.conditions = conditions
            resolution.narration_parts.append(
                f"{target_character.name} 未通过豁免，陷入{condition}状态！"
            )
        else:
            resolution.narration_parts.append(f"{target_character.name} 通过了豁免！")
        resolution.target_name = target_character.name
