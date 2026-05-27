from typing import Any, Callable

from sqlalchemy.orm.attributes import flag_modified

from models import Character
from services.combat_concentration_effect_service import track_concentration_condition
from services.combat_ai_spell_models import AiSpellResolution, CONTROL_CONDITION_MAP
from services.combat_legendary_resistance_service import maybe_use_legendary_resistance
from services.combat_spell_effect_service import (
    resolve_spell_condition,
    resolve_spell_condition_duration,
)
from services.dnd_rules import get_life_state
from services.dnd_rules import apply_character_healing, can_receive_ordinary_healing, roll_dice, roll_saving_throw


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
            if not can_receive_ordinary_healing(target_character):
                return
            apply_character_healing(target_character, total_heal)
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
    caster_id: str | None = None,
    flag_modified_func: Callable[[Any, str], None] = flag_modified,
    roll_dice_func: Callable[[str], dict[str, Any]] = roll_dice,
) -> None:
    condition, resolved_save = resolve_spell_condition(resolution.spell_name, resolution.spell_data)
    if condition == "affected":
        condition = CONTROL_CONDITION_MAP.get(resolution.spell_name, "hexed")
    duration_rounds = resolve_spell_condition_duration(resolution.spell_name, resolution.spell_data)
    save_ability = resolved_save or resolution.spell_data.get("save")
    if not resolution.spell_target:
        return

    target_enemy = next(
        (enemy for enemy in enemies if str(enemy.get("id")) == str(resolution.spell_target)),
        None,
    )
    if target_enemy:
        save_detail = (
            roll_saving_throw(
                target_enemy,
                save_ability,
                spell_save_dc,
                d20_roller=roll_dice_func,
            )
            if save_ability else None
        )
        save_detail = maybe_use_legendary_resistance(
            target_enemy,
            save_detail,
            reason="ai_control_spell",
        )
        saved = bool(save_detail and save_detail["success"])
        if not saved:
            conditions = target_enemy.get("conditions", [])
            condition_preexisting = condition in conditions
            durations = dict(target_enemy.get("condition_durations", {}))
            had_previous_duration = condition in durations
            previous_duration = durations.get(condition)
            if condition not in conditions:
                conditions.append(condition)
                target_enemy["conditions"] = conditions
            if duration_rounds is not None:
                durations[condition] = duration_rounds
                target_enemy["condition_durations"] = durations
            if resolution.spell_data.get("concentration"):
                track_concentration_condition(
                    target_enemy,
                    condition,
                    caster_id=caster_id,
                    spell_name=resolution.spell_name,
                    condition_preexisting=condition_preexisting,
                    previous_duration=previous_duration,
                    had_previous_duration=had_previous_duration,
                )
            enemy_hp = target_enemy.get("hp_current")
            resolution.target_state = {
                "target_id": resolution.spell_target,
                "target_name": target_enemy.get("name", "敌人"),
                "conditions": target_enemy.get("conditions", []),
                "condition_durations": target_enemy.get("condition_durations", {}),
                "life_state": "dead" if enemy_hp is not None and enemy_hp <= 0 else "alive",
            }
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
        save_detail = (
            roll_saving_throw(
                {
                    "derived": target_character.derived or {},
                    "conditions": target_character.conditions or [],
                    "condition_durations": target_character.condition_durations or {},
                },
                save_ability,
                spell_save_dc,
                d20_roller=roll_dice_func,
            )
            if save_ability else None
        )
        saved = bool(save_detail and save_detail["success"])
        if not saved:
            conditions = list(target_character.conditions or [])
            condition_preexisting = condition in conditions
            durations = dict(target_character.condition_durations or {})
            had_previous_duration = condition in durations
            previous_duration = durations.get(condition)
            if condition not in conditions:
                conditions.append(condition)
                target_character.conditions = conditions
            if duration_rounds is not None:
                durations[condition] = duration_rounds
                target_character.condition_durations = durations
            if resolution.spell_data.get("concentration"):
                track_concentration_condition(
                    target_character,
                    condition,
                    caster_id=caster_id,
                    spell_name=resolution.spell_name,
                    condition_preexisting=condition_preexisting,
                    previous_duration=previous_duration,
                    had_previous_duration=had_previous_duration,
                )
            resolution.target_state = {
                "target_id": resolution.spell_target,
                "target_name": target_character.name,
                "conditions": target_character.conditions or [],
                "condition_durations": target_character.condition_durations or {},
                "life_state": get_life_state(target_character),
                "concentration": target_character.concentration,
            }
            resolution.narration_parts.append(
                f"{target_character.name} 未通过豁免，陷入{condition}状态！"
            )
        else:
            resolution.narration_parts.append(f"{target_character.name} 通过了豁免！")
        resolution.target_name = target_character.name
