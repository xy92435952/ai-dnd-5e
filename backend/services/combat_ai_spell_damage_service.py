from typing import Any, Callable

from sqlalchemy.orm.attributes import flag_modified

from models import Character
from services.combat_ai_spell_models import AiSpellResolution
from services.combat_evasion_service import resolve_save_damage, spell_half_on_save
from services.combat_legendary_resistance_service import maybe_use_legendary_resistance
from services.combat_resistance_service import apply_character_damage_resistance
from services.combat_service import CombatService
from services.combat_spell_damage_component_service import (
    apply_save_to_damage_components,
    normalize_damage_components,
    resolve_spell_damage_components,
)
from services.combat_spell_damage_type_service import resolve_spell_damage_type
from services.dnd_rules import apply_character_damage, roll_dice, roll_saving_throw


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
    total_damage, dice_detail = spell_service_obj.resolve_damage(
        resolution.spell_name,
        resolution.spell_level,
        spell_mod,
    )
    damage_type = resolve_spell_damage_type(resolution.spell_name, resolution.spell_data)
    damage_components = resolve_spell_damage_components(
        resolution.spell_name,
        resolution.spell_data,
        dice_detail=dice_detail,
        total_damage=total_damage,
    )
    if resolution.spell_data.get("aoe", False):
        targets = all_characters if is_enemy else enemies_alive
        for target in [item for item in targets if item.get("hp_current", 0) > 0][:4]:
            target_id = str(target.get("id", ""))
            target_for_evasion = target
            if is_enemy and target_id:
                target_character = await db.get(Character, target_id)
                if target_character:
                    target_for_evasion = target_character
            save_damage = resolve_ai_save_damage(
                target,
                base_damage=total_damage,
                spell_data=resolution.spell_data,
                spell_save_dc=spell_save_dc,
                roll_dice_func=roll_dice_func,
                target_for_evasion=target_for_evasion,
                half_on_save_default=True,
            )
            target_components = apply_save_to_damage_components(
                damage_components,
                save_result=save_damage["save_result"],
                save_ability=save_damage["save_ability"],
                half_on_save=save_damage["half_on_save"],
                target=target_for_evasion,
            )
            if not is_enemy:
                damage_this = damage_enemy(
                    enemies,
                    target_id,
                    save_damage["damage"],
                    combat_service,
                    damage_type=damage_type,
                    damage_components=target_components,
                )
            else:
                target_character = await db.get(Character, target_id)
                damage_this = save_damage["damage"]
                if target_character:
                    damage_this = apply_character_spell_damage(
                        target_character,
                        save_damage["damage"],
                        damage_type=damage_type,
                        damage_components=target_components,
                    )
                    apply_character_damage(target_character, damage_this)
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
        save_damage = resolve_ai_save_damage(
            target_enemy,
            base_damage=total_damage,
            spell_data=resolution.spell_data,
            spell_save_dc=spell_save_dc,
            roll_dice_func=roll_dice_func,
            target_for_evasion=target_enemy,
            half_on_save_default=False,
        )
        target_components = apply_save_to_damage_components(
            damage_components,
            save_result=save_damage["save_result"],
            save_ability=save_damage["save_ability"],
            half_on_save=save_damage["half_on_save"],
            target=target_enemy,
        )
        total_damage = apply_enemy_spell_damage(
            target_enemy,
            save_damage["damage"],
            combat_service,
            damage_type=damage_type,
            damage_components=target_components,
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
            save_damage = resolve_ai_character_save_damage(
                target_character,
                base_damage=total_damage,
                spell_data=resolution.spell_data,
                spell_save_dc=spell_save_dc,
                roll_dice_func=roll_dice_func,
            )
            target_components = apply_save_to_damage_components(
                damage_components,
                save_result=save_damage["save_result"],
                save_ability=save_damage["save_ability"],
                half_on_save=save_damage["half_on_save"],
                target=target_character,
            )
            total_damage = apply_character_spell_damage(
                target_character,
                save_damage["damage"],
                damage_type=damage_type,
                damage_components=target_components,
            )
            apply_character_damage(target_character, total_damage)
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
    target_for_evasion: dict[str, Any] | object | None = None,
) -> int:
    return resolve_ai_save_damage(
        target,
        base_damage=base_damage,
        spell_data=spell_data,
        spell_save_dc=spell_save_dc,
        roll_dice_func=roll_dice_func,
        target_for_evasion=target_for_evasion,
        half_on_save_default=True,
    )["damage"]


def damage_after_ai_enemy_save(
    enemy: dict[str, Any],
    *,
    base_damage: int,
    spell_data: dict[str, Any],
    spell_save_dc: int,
    roll_dice_func: Callable[[str], dict[str, Any]],
) -> int:
    return resolve_ai_save_damage(
        enemy,
        base_damage=base_damage,
        spell_data=spell_data,
        spell_save_dc=spell_save_dc,
        roll_dice_func=roll_dice_func,
        target_for_evasion=enemy,
        half_on_save_default=False,
    )["damage"]


def damage_after_ai_character_save(
    character: Character,
    *,
    base_damage: int,
    spell_data: dict[str, Any],
    spell_save_dc: int,
    roll_dice_func: Callable[[str], dict[str, Any]],
) -> int:
    return resolve_ai_character_save_damage(
        character,
        base_damage=base_damage,
        spell_data=spell_data,
        spell_save_dc=spell_save_dc,
        roll_dice_func=roll_dice_func,
    )["damage"]


def resolve_ai_save_damage(
    target: dict[str, Any],
    *,
    base_damage: int,
    spell_data: dict[str, Any],
    spell_save_dc: int,
    roll_dice_func: Callable[[str], dict[str, Any]],
    target_for_evasion: dict[str, Any] | object | None = None,
    half_on_save_default: bool,
) -> dict[str, Any]:
    save_ability = spell_data.get("save")
    if not save_ability:
        return {
            "damage": max(0, int(base_damage or 0)),
            "save_result": None,
            "save_ability": None,
            "half_on_save": False,
            "evasion_applied": False,
            "evasion_failed_half": False,
        }

    save_detail = roll_saving_throw(
        target,
        save_ability,
        spell_save_dc,
        d20_roller=roll_dice_func,
    )
    save_detail = maybe_use_legendary_resistance(
        target,
        save_detail,
        reason="ai_spell_save",
    )
    half_on_save = spell_half_on_save(spell_data, default=half_on_save_default)
    resolved = resolve_save_damage(
        base_damage,
        save_result=save_detail,
        save_ability=save_ability,
        half_on_save=half_on_save,
        target=target_for_evasion or target,
    )
    return {
        **resolved,
        "save_result": save_detail,
        "save_ability": save_ability,
        "half_on_save": half_on_save,
    }


def resolve_ai_character_save_damage(
    character: Character,
    *,
    base_damage: int,
    spell_data: dict[str, Any],
    spell_save_dc: int,
    roll_dice_func: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    return resolve_ai_save_damage(
        {
            "derived": character.derived or {},
            "conditions": character.conditions or [],
            "condition_durations": character.condition_durations or {},
        },
        base_damage=base_damage,
        spell_data=spell_data,
        spell_save_dc=spell_save_dc,
        roll_dice_func=roll_dice_func,
        target_for_evasion=character,
        half_on_save_default=False,
    )


def apply_enemy_spell_damage(
    enemy: dict[str, Any],
    damage: int,
    combat_service: CombatService,
    *,
    damage_type: str | None = None,
    damage_components: list[dict[str, Any]] | None = None,
) -> int:
    component_results = []
    for component in normalize_damage_components(damage_components):
        base_damage = component["damage"]
        component_type = component.get("damage_type")
        component_damage = base_damage
        if component_type:
            component_damage = combat_service.apply_damage_with_resistance(
                base_damage,
                component_type,
                enemy.get("resistances", []),
                enemy.get("immunities", []),
                enemy.get("vulnerabilities", []),
            )
        component_results.append(component_damage)
    if component_results:
        return sum(component_results)

    if damage_type:
        return combat_service.apply_damage_with_resistance(
            damage,
            damage_type,
            enemy.get("resistances", []),
            enemy.get("immunities", []),
            enemy.get("vulnerabilities", []),
        )
    return max(0, int(damage or 0))


def apply_character_spell_damage(
    character: Character,
    damage: int,
    *,
    damage_type: str | None = None,
    damage_components: list[dict[str, Any]] | None = None,
) -> int:
    component_results = []
    for component in normalize_damage_components(damage_components):
        component_damage, _resistance_applied = apply_character_damage_resistance(
            character,
            component["damage"],
            component.get("damage_type"),
        )
        component_results.append(component_damage)
    if component_results:
        return sum(component_results)

    applied_damage, _resistance_applied = apply_character_damage_resistance(
        character,
        damage,
        damage_type,
    )
    return applied_damage


def damage_enemy(
    enemies: list[dict[str, Any]],
    target_id: str,
    damage: int,
    combat_service: CombatService,
    *,
    damage_type: str | None = None,
    damage_components: list[dict[str, Any]] | None = None,
) -> int:
    for enemy in enemies:
        if str(enemy.get("id")) == target_id:
            applied_damage = apply_enemy_spell_damage(
                enemy,
                damage,
                combat_service,
                damage_type=damage_type,
                damage_components=damage_components,
            )
            enemy["hp_current"] = combat_service.apply_damage(
                enemy.get("hp_current", 0),
                applied_damage,
                enemy.get("derived", {}).get("hp_max", 10),
            )
            return applied_damage
    return damage
