from dataclasses import dataclass, field
from typing import Any, Callable

from sqlalchemy.orm.attributes import flag_modified

from models import Character
from services.combat_service import CombatService
from services.dnd_rules import roll_dice
from services.spell_service import spell_service

SLOT_KEYS = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th"]

CONTROL_CONDITION_MAP = {
    "Hold Person": "paralyzed",
    "定身术": "paralyzed",
    "Entangle": "restrained",
    "纠缠术": "restrained",
    "Web": "restrained",
    "蛛网": "restrained",
    "Sleep": "unconscious",
    "睡眠术": "unconscious",
    "Command": "commanded",
    "命令术": "commanded",
    "Faerie Fire": "faerie_fire",
    "妖火": "faerie_fire",
    "Blindness/Deafness": "blinded",
    "目盲/耳聋": "blinded",
    "Fear": "frightened",
    "恐惧术": "frightened",
    "Silence": "silenced",
    "沉默术": "silenced",
}

svc = CombatService()


@dataclass
class AiSpellResolution:
    spell_name: str
    spell_level: int
    spell_target: str | None
    spell_data: dict[str, Any]
    is_cantrip: bool
    damage: int = 0
    heal: int = 0
    target_new_hp: int | None = None
    target_name: str = ""
    narration_parts: list[str] = field(default_factory=list)
    mechanical_narration: str = ""


async def resolve_ai_spell_action(
    db,
    *,
    session,
    actor_name: str,
    is_enemy: bool,
    caster,
    actor_derived: dict[str, Any],
    decided_target_id: str | None,
    decided_reason: str,
    decision: dict[str, Any],
    state: dict[str, Any],
    enemies: list[dict[str, Any]],
    enemies_alive: list[dict[str, Any]],
    all_characters: list[dict[str, Any]],
    spell_service_obj=spell_service,
    combat_service: CombatService = svc,
    flag_modified_func: Callable[[Any, str], None] = flag_modified,
    roll_dice_func: Callable[[str], dict[str, Any]] = roll_dice,
) -> AiSpellResolution | None:
    """Resolve the AI spell branch and mutate combat state like the legacy endpoint did."""
    if not (decision.get("action_type") == "spell" and decision.get("action_name")):
        return None

    spell_name = decision["action_name"]
    spell_level = decision.get("spell_level") or 1
    spell_target = decided_target_id
    spell_data = spell_service_obj.get(spell_name)
    if not spell_data:
        return None

    spell_mod = _spell_modifier(actor_derived)
    spell_save_dc = actor_derived.get("spell_save_dc", 13)
    bonus_healing = actor_derived.get("bonus_healing", False)
    is_cantrip = spell_data.get("level", 0) == 0
    is_aoe = spell_data.get("aoe", False)
    spell_type = spell_data.get("type", "damage")

    if not is_cantrip and caster:
        if not consume_ai_spell_slot(caster, spell_level):
            return None

    resolution = AiSpellResolution(
        spell_name=spell_name,
        spell_level=spell_level,
        spell_target=spell_target,
        spell_data=spell_data,
        is_cantrip=is_cantrip,
    )

    if spell_type == "damage":
        await _apply_ai_damage_spell(
            db,
            resolution=resolution,
            session=session,
            enemies=enemies,
            enemies_alive=enemies_alive,
            all_characters=all_characters,
            is_enemy=is_enemy,
            spell_mod=spell_mod,
            spell_save_dc=spell_save_dc,
            state=state,
            spell_service_obj=spell_service_obj,
            combat_service=combat_service,
            flag_modified_func=flag_modified_func,
            roll_dice_func=roll_dice_func,
        )
    elif spell_type == "heal":
        await _apply_ai_heal_spell(
            db,
            resolution=resolution,
            spell_mod=spell_mod,
            bonus_healing=bonus_healing,
            spell_service_obj=spell_service_obj,
        )
    elif spell_type in ("control", "utility"):
        await _apply_ai_control_spell(
            db,
            resolution=resolution,
            session=session,
            enemies=enemies,
            spell_save_dc=spell_save_dc,
            state=state,
            flag_modified_func=flag_modified_func,
            roll_dice_func=roll_dice_func,
        )

    if spell_data.get("concentration") and caster:
        caster.concentration = spell_name

    resolution.mechanical_narration = build_ai_spell_narration(
        actor_name=actor_name,
        spell_name=spell_name,
        spell_level=spell_level,
        is_cantrip=is_cantrip,
        damage=resolution.damage,
        heal=resolution.heal,
        narration_parts=resolution.narration_parts,
        decided_reason=decided_reason,
    )
    return resolution


def consume_ai_spell_slot(caster, spell_level: int) -> bool:
    slots = dict(caster.spell_slots or {})
    slot_key = SLOT_KEYS[min(spell_level - 1, 8)]
    if slots.get(slot_key, 0) <= 0:
        return False
    slots[slot_key] -= 1
    caster.spell_slots = slots
    return True


def build_ai_spell_narration(
    *,
    actor_name: str,
    spell_name: str,
    spell_level: int,
    is_cantrip: bool,
    damage: int,
    heal: int,
    narration_parts: list[str],
    decided_reason: str,
) -> str:
    level_str = f"{spell_level}环" if not is_cantrip else "戏法"
    narration = f"✨ {actor_name} 施放了【{spell_name}】（{level_str}）！"
    if damage > 0:
        narration += f"造成 {damage} 点伤害！"
    if heal > 0:
        narration += f"恢复 {heal} HP！"
    if narration_parts:
        narration += " ".join(narration_parts)
    if decided_reason:
        narration += f"（{decided_reason}）"
    return narration


def _spell_modifier(actor_derived: dict[str, Any]) -> int:
    spell_ability = actor_derived.get("spell_ability")
    if not spell_ability:
        return 0
    return actor_derived.get("ability_modifiers", {}).get(spell_ability, 0)


async def _apply_ai_damage_spell(
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
    flag_modified_func: Callable[[Any, str], None],
    roll_dice_func: Callable[[str], dict[str, Any]],
) -> None:
    total_damage, _dice_detail = spell_service_obj.resolve_damage(
        resolution.spell_name,
        resolution.spell_level,
        spell_mod,
    )
    if resolution.spell_data.get("aoe", False):
        targets = all_characters if is_enemy else enemies_alive
        for target in [item for item in targets if item.get("hp_current", 0) > 0][:4]:
            damage_this = _damage_after_ai_save(
                target,
                base_damage=total_damage,
                spell_data=resolution.spell_data,
                spell_save_dc=spell_save_dc,
                roll_dice_func=roll_dice_func,
            )
            target_id = str(target.get("id", ""))
            if not is_enemy:
                _damage_enemy(enemies, target_id, damage_this, combat_service)
            else:
                target_character = await db.get(Character, target_id)
                if target_character:
                    target_character.hp_current = combat_service.apply_damage(
                        target_character.hp_current,
                        damage_this,
                        (target_character.derived or {}).get("hp_max", target_character.hp_current),
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
        total_damage = _damage_after_ai_enemy_save(
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
                (target_character.derived or {}).get("hp_max", target_character.hp_current),
            )
            resolution.target_new_hp = target_character.hp_current
            resolution.target_name = target_character.name

    resolution.damage = total_damage


async def _apply_ai_heal_spell(
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


async def _apply_ai_control_spell(
    db,
    *,
    resolution: AiSpellResolution,
    session,
    enemies: list[dict[str, Any]],
    spell_save_dc: int,
    state: dict[str, Any],
    flag_modified_func: Callable[[Any, str], None],
    roll_dice_func: Callable[[str], dict[str, Any]],
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


def _damage_after_ai_save(
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


def _damage_after_ai_enemy_save(
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


def _damage_enemy(
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
