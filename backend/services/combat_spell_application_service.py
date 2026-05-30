from dataclasses import dataclass, field
from typing import Any, Callable

from models import Character
from services.combat_spell_effect_service import (
    apply_armor_of_agathys_to_target,
    apply_control_spell_to_target,
    apply_resurrection_spell_to_target,
    apply_spell_damage_to_target,
    apply_spell_heal_to_target,
    get_resurrection_spell_config,
    resolve_spell_condition,
    resolve_spell_condition_duration,
    roll_spell_save,
    spell_applies_condition,
)
from services.combat_temporary_hp_service import is_armor_of_agathys
from services.combat_evasion_service import resolve_save_damage, spell_half_on_save
from services.combat_spell_damage_component_service import (
    apply_save_to_damage_components,
    resolve_spell_damage_components,
)
from services.combat_spell_resolution_service import resolve_spell_roll_amount


@dataclass
class SpellApplicationResult:
    result_damage: int = 0
    result_heal: int = 0
    dice_detail: dict[str, Any] = field(default_factory=dict)
    target_new_hp: int | None = None
    target_state: dict[str, Any] | None = None
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
    caster_id: str | None = None,
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
    is_crit: bool = False,
    attack_hit: bool | None = None,
    attack_roll: dict[str, Any] | None = None,
    session=None,
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
            half_on_save = spell_half_on_save(spell, default=True)
            damage_components = resolve_spell_damage_components(
                spell_name,
                spell,
                dice_detail=result.dice_detail,
                total_damage=result.result_damage,
            )

            for target_id in target_ids:
                save_result = await roll_spell_save(
                    db,
                    enemies,
                    target_id,
                    save_ability=save_ability,
                    spell_save_dc=spell_save_dc,
                )
                target = next((enemy for enemy in enemies if enemy.get("id") == target_id), None)
                if target is None:
                    target = await db.get(Character, target_id)
                save_damage = resolve_save_damage(
                    result.result_damage,
                    save_result=save_result,
                    save_ability=save_ability,
                    half_on_save=half_on_save,
                    target=target,
                )
                save_components = apply_save_to_damage_components(
                    damage_components,
                    save_result=save_result,
                    save_ability=save_ability,
                    half_on_save=half_on_save,
                    target=target,
                )

                applied, concentration_log = await apply_spell_damage_to_target(
                    db,
                    session_id,
                    enemies,
                    target_id,
                    save_damage["damage"],
                    save_result=save_result,
                    spell_name=spell_name,
                    spell=spell,
                    damage_components=save_components,
                    session=session,
                )
                if applied:
                    applied.update({
                        "base_damage": result.result_damage,
                        "evasion_applied": save_damage["evasion_applied"],
                        "evasion_failed_half": save_damage["evasion_failed_half"],
                    })
                    result.aoe_results.append(applied)
                if concentration_log:
                    result.concentration_logs.append(concentration_log)

            result.enemies_changed = True

        elif spell_applies_condition(spell_type, spell_name, spell):
            result.condition_name, save_ability = resolve_spell_condition(spell_name, spell)
            duration_rounds = resolve_spell_condition_duration(spell_name, spell)

            for target_id in target_ids:
                control_result = await apply_control_spell_to_target(
                    db,
                    enemies,
                    target_id,
                    session_id=session_id,
                    condition_name=result.condition_name,
                    save_ability=save_ability,
                    spell_save_dc=spell_save_dc,
                    duration_rounds=duration_rounds,
                    caster_id=caster_id,
                    spell_name=spell_name,
                    is_concentration=bool(spell.get("concentration")),
                )
                if result.save_detail is None and control_result.get("save_detail"):
                    result.save_detail = control_result["save_detail"]
                if control_result.get("target_state"):
                    result.aoe_results.append(control_result["target_state"])
                if control_result.get("concentration_log"):
                    result.concentration_logs.append(control_result["concentration_log"])

            result.enemies_changed = any(enemy["id"] in set(target_ids) for enemy in enemies)

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
        if attack_hit is False:
            result.dice_detail = {
                "attack_roll": attack_roll or {},
                "hit": False,
                "is_crit": False,
                "total": 0,
            }
            return result
        result.result_damage, result.dice_detail = resolve_spell_roll_amount(
            spell_type=spell_type,
            spell_name=spell_name,
            spell_level=spell_level,
            spell_mod=spell_mod,
            bonus_healing=bonus_healing,
            damage_values=damage_values,
            is_crit=is_crit,
            resolve_damage=resolve_damage,
            resolve_heal=resolve_heal,
        )
        if attack_roll is not None:
            result.dice_detail["attack_roll"] = attack_roll
            result.dice_detail["is_crit"] = bool(is_crit)
        save_ability = spell.get("save")
        save_result = await roll_spell_save(
            db,
            enemies,
            target_id,
            save_ability=save_ability,
            spell_save_dc=spell_save_dc,
        )
        target = next((enemy for enemy in enemies if enemy.get("id") == target_id), None)
        if target is None:
            target = await db.get(Character, target_id)
        save_damage = resolve_save_damage(
            result.result_damage,
            save_result=save_result,
            save_ability=save_ability,
            half_on_save=spell_half_on_save(spell, default=False),
            target=target,
        )
        damage_components = resolve_spell_damage_components(
            spell_name,
            spell,
            dice_detail=result.dice_detail,
            total_damage=result.result_damage,
        )
        save_components = apply_save_to_damage_components(
            damage_components,
            save_result=save_result,
            save_ability=save_ability,
            half_on_save=spell_half_on_save(spell, default=False),
            target=target,
        )
        applied, concentration_log = await apply_spell_damage_to_target(
            db,
            session_id,
            enemies,
            target_id,
            save_damage["damage"],
            save_result=save_result,
            spell_name=spell_name,
            spell=spell,
            damage_components=save_components,
            session=session,
        )
        if applied:
            applied.update({
                "base_damage": result.result_damage,
                "evasion_applied": save_damage["evasion_applied"],
                "evasion_failed_half": save_damage["evasion_failed_half"],
            })
            result.target_new_hp = applied["new_hp"]
            result.target_state = applied
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
            result.target_state = applied

    elif spell_type == "utility" and target_id and is_armor_of_agathys(spell_name, spell):
        applied = await apply_armor_of_agathys_to_target(
            db,
            target_id,
            spell_name=spell_name,
            spell=spell,
            spell_level=spell_level,
        )
        if applied:
            result.target_new_hp = applied["new_hp"]
            result.target_state = applied

    elif spell_type == "utility" and target_id and get_resurrection_spell_config(spell_name, spell):
        applied = await apply_resurrection_spell_to_target(db, target_id, spell_name, spell)
        if applied:
            result.resurrection_results.append(applied)
            result.target_new_hp = applied["new_hp"]
            result.target_state = applied

    elif target_id and spell_applies_condition(spell_type, spell_name, spell):
        result.condition_name, save_ability = resolve_spell_condition(spell_name, spell)
        duration_rounds = resolve_spell_condition_duration(spell_name, spell)
        control_result = await apply_control_spell_to_target(
            db,
            enemies,
            target_id,
            session_id=session_id,
            condition_name=result.condition_name,
            save_ability=save_ability,
            spell_save_dc=spell_save_dc,
            duration_rounds=duration_rounds,
            caster_id=caster_id,
            spell_name=spell_name,
            is_concentration=bool(spell.get("concentration")),
        )
        result.save_detail = control_result["save_detail"]
        result.target_state = control_result.get("target_state")
        if control_result.get("concentration_log"):
            result.concentration_logs.append(control_result["concentration_log"])
        result.enemies_changed = control_result["applied"] and any(
            enemy["id"] == target_id for enemy in enemies
        )

    return result
