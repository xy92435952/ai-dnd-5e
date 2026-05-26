from typing import Any, Callable

from sqlalchemy.orm.attributes import flag_modified

from models import Character
from services.combat_ai_spell_models import AiSpellResolution
from services.combat_service import CombatService
from services.dnd_rules import get_effective_hp_max, roll_dice


async def apply_ai_damage_spell(
    db,
    *,
    resolution: AiSpellResolution,
    session,
    enemies: list[dict[str, Any]],
    enemies_alive: list[dict[str, Any]],
    all_characters: list[dict[str, Any]],
    is_enemy: bool,
    spell_mod: int,
    spell_save_dc: int,
    state: dict[str, Any],
    spell_service_obj,
    combat_service: CombatService,
    flag_modified_func: Callable[[Any, str], None] = flag_modified,
    roll_dice_func: Callable[[str], dict[str, Any]] = roll_dice,
) -> None:
    total_damage, _dice_detail = spell_service_obj.resolve_damage(
        resolution.spell_name,
        resolution.spell_level,
        spell_mod,
    )
    if resolution.spell_data.get("aoe", False):
        targets = all_characters if is_enemy else enemies_alive
        for target in [item for item in targets if item.get("hp_current", 0) > 0][:4]:
            damage_this = damage_after_ai_save(
                target,
                base_damage=total_damage,
                spell_data=resolution.spell_data,
                spell_save_dc=spell_save_dc,
                roll_dice_func=roll_dice_func,
            )
            target_id = str(target.get("id", ""))
            if not is_enemy:
                damage_enemy(enemies, target_id, damage_this, combat_service)
            else:
                target_character = await db.get(Character, target_id)
                if target_character:
                    target_character.hp_current = combat_service.apply_damage(
                        target_character.hp_current,
                        damage_this,
                        get_effective_hp_max(target_character),
                    )
            resolution.damage += damage_this

        state["enemies"] = enemies
        session.game_state = dict(state)
        flag_modified_func(session, "game_state")
        return

    if not resolution.spell_target:
        return

    target_enemy = next(
        (enemy for enemy in enemies if str(enemy.get("id")) == str(resolution.spell_target)),
        None,
    )
    if target_enemy:
        total_damage = damage_after_ai_enemy_save(
            target_enemy,
            base_damage=total_damage,
            spell_data=resolution.spell_data,
            spell_save_dc=spell_save_dc,
            roll_dice_func=roll_dice_func,
        )
        target_enemy["hp_current"] = combat_service.apply_damage(
            target_enemy.get("hp_current", 0),
            total_damage,
            target_enemy.get("derived", {}).get("hp_max", 10),
        )
        resolution.target_new_hp = target_enemy["hp_current"]
        resolution.target_name = target_enemy.get("name", "敌人")
        state["enemies"] = enemies
        session.game_state = dict(state)
        flag_modified_func(session, "game_state")
    else:
        target_character = await db.get(Character, resolution.spell_target)
        if target_character:
            target_character.hp_current = combat_service.apply_damage(
                target_character.hp_current,
                total_damage,
                get_effective_hp_max(target_character),
            )
            resolution.target_new_hp = target_character.hp_current
            resolution.target_name = target_character.name

    resolution.damage = total_damage


def damage_after_ai_save(
    target: dict[str, Any],
    *,
    base_damage: int,
    spell_data: dict[str, Any],
    spell_save_dc: int,
    roll_dice_func: Callable[[str], dict[str, Any]],
) -> int:
    save_ability = spell_data.get("save")
    if not save_ability:
        return base_damage

    target_derived = target.get("derived", {})
    save_mod = target_derived.get("saving_throws", {}).get(
        save_ability,
        target_derived.get("ability_modifiers", {}).get(save_ability, 0),
    )
    save_roll = roll_dice_func("1d20")["rolls"][0]
    if save_roll + save_mod >= spell_save_dc:
        return base_damage // 2 if spell_data.get("half_on_save", True) else 0
    return base_damage


def damage_after_ai_enemy_save(
    enemy: dict[str, Any],
    *,
    base_damage: int,
    spell_data: dict[str, Any],
    spell_save_dc: int,
    roll_dice_func: Callable[[str], dict[str, Any]],
) -> int:
    save_ability = spell_data.get("save")
    if not save_ability:
        return base_damage

    saves = enemy.get("derived", {}).get("saving_throws", {})
    save_mod = saves.get(save_ability, 0)
    save_roll = roll_dice_func("1d20")["rolls"][0]
    if save_roll + save_mod >= spell_save_dc:
        return base_damage // 2 if spell_data.get("half_on_save") else 0
    return base_damage


def damage_enemy(
    enemies: list[dict[str, Any]],
    target_id: str,
    damage: int,
    combat_service: CombatService,
) -> None:
    for enemy in enemies:
        if str(enemy.get("id")) == target_id:
            enemy["hp_current"] = combat_service.apply_damage(
                enemy.get("hp_current", 0),
                damage,
                enemy.get("derived", {}).get("hp_max", 10),
            )
