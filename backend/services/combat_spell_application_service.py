from dataclasses import dataclass, field
from typing import Any, Callable

from services.combat_spell_effect_service import (
    apply_control_spell_to_target,
    apply_resurrection_spell_to_target,
    apply_spell_damage_to_target,
    apply_spell_heal_to_target,
    get_resurrection_spell_config,
    resolve_spell_condition,
    roll_spell_save,
)
from services.combat_spell_resolution_service import resolve_spell_roll_amount


@dataclass
class SpellApplicationResult:
    result_damage: int = 0
    result_heal: int = 0
    dice_detail: dict[str, Any] = field(default_factory=dict)
    target_new_hp: int | None = None
    aoe_results: list[dict[str, Any]] = field(default_factory=list)
    resurrection_results: list[dict[str, Any]] = field(default_factory=list)
    concentration_logs: list[Any] = field(default_factory=list)
    condition_name: str | None = None
    save_detail: dict[str, Any] | None = None
    enemies_changed: bool = False


async def apply_confirmed_spell_effects(
    db,
    *,
    session_id: str,
    enemies: list[dict[str, Any]],
    target_ids: list[str],
    is_aoe: bool,
    spell_type: str,
    spell_name: str,
    spell_level: int,
    spell_mod: int,
    bonus_healing: bool,
    spell: dict[str, Any],
    damage_values: list[int] | None,
    spell_save_dc: int,
    resolve_damage: Callable[[str, int, int], tuple[int, dict]],
    resolve_heal: Callable[[str, int, int, bool], tuple[int, dict]],
) -> SpellApplicationResult:
    result = SpellApplicationResult()

    if is_aoe:
        if spell_type == "damage":
            result.result_damage, result.dice_detail = resolve_spell_roll_amount(
                spell_type=spell_type,
                spell_name=spell_name,
                spell_level=spell_level,
                spell_mod=spell_mod,
                bonus_healing=bonus_healing,
                damage_values=damage_values,
                resolve_damage=resolve_damage,
                resolve_heal=resolve_heal,
            )
            save_ability = spell.get("save")
            half_on_save = spell.get("half_on_save", True)

            for target_id in target_ids:
                damage_this = result.result_damage
                save_result = await roll_spell_save(
                    db,
                    enemies,
                    target_id,
                    save_ability=save_ability,
                    spell_save_dc=spell_save_dc,
                )
                if save_result and save_result["success"] and half_on_save:
                    damage_this = damage_this // 2

                applied, concentration_log = await apply_spell_damage_to_target(
                    db,
                    session_id,
                    enemies,
                    target_id,
                    damage_this,
                    save_result=save_result,
                )
                if applied:
                    result.aoe_results.append(applied)
                if concentration_log:
                    result.concentration_logs.append(concentration_log)

            result.enemies_changed = True

        elif spell_type == "heal":
            result.result_heal, result.dice_detail = resolve_spell_roll_amount(
                spell_type=spell_type,
                spell_name=spell_name,
                spell_level=spell_level,
                spell_mod=spell_mod,
                bonus_healing=bonus_healing,
                damage_values=damage_values,
                resolve_damage=resolve_damage,
                resolve_heal=resolve_heal,
            )
            for target_id in target_ids:
                applied = await apply_spell_heal_to_target(db, target_id, result.result_heal)
                if applied:
                    result.aoe_results.append(applied)

        return result

    target_id = target_ids[0] if target_ids else None
    if spell_type == "damage" and target_id:
        result.result_damage, result.dice_detail = resolve_spell_roll_amount(
            spell_type=spell_type,
            spell_name=spell_name,
            spell_level=spell_level,
            spell_mod=spell_mod,
            bonus_healing=bonus_healing,
            damage_values=damage_values,
            resolve_damage=resolve_damage,
            resolve_heal=resolve_heal,
        )
        applied, concentration_log = await apply_spell_damage_to_target(
            db,
            session_id,
            enemies,
            target_id,
            result.result_damage,
        )
        if applied:
            result.target_new_hp = applied["new_hp"]
            result.enemies_changed = applied["target_id"] in {enemy.get("id") for enemy in enemies}
        if concentration_log:
            result.concentration_logs.append(concentration_log)

    elif spell_type == "heal" and target_id:
        result.result_heal, result.dice_detail = resolve_spell_roll_amount(
            spell_type=spell_type,
            spell_name=spell_name,
            spell_level=spell_level,
            spell_mod=spell_mod,
            bonus_healing=bonus_healing,
            damage_values=damage_values,
            resolve_damage=resolve_damage,
            resolve_heal=resolve_heal,
        )
        applied = await apply_spell_heal_to_target(db, target_id, result.result_heal)
        if applied:
            result.target_new_hp = applied["new_hp"]

    elif spell_type == "utility" and target_id and get_resurrection_spell_config(spell_name, spell):
        applied = await apply_resurrection_spell_to_target(db, target_id, spell_name, spell)
        if applied:
            result.resurrection_results.append(applied)
            result.target_new_hp = applied["new_hp"]

    elif spell_type in ("control", "utility") and target_id:
        result.condition_name, save_ability = resolve_spell_condition(spell_name, spell)
        control_result = await apply_control_spell_to_target(
            db,
            enemies,
            target_id,
            condition_name=result.condition_name,
            save_ability=save_ability,
            spell_save_dc=spell_save_dc,
        )
        result.save_detail = control_result["save_detail"]
        result.enemies_changed = control_result["applied"] and any(
            enemy["id"] == target_id for enemy in enemies
        )

    return result
