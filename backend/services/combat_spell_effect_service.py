"""
services.combat_spell_effect_service — shared spell damage/healing effect helpers.
"""
import re
from typing import Any

from models import Character
from services.combat_concentration_service import do_concentration_check
from services.combat_concentration_service import break_concentration_if_incapacitated
from services.combat_service import CombatService
from services.combat_spell_resolution_service import apply_frontend_dice_override
from services.combat_temporary_hp_service import (
    apply_armor_of_agathys_to_character,
    is_armor_of_agathys,
)
from services.dnd_rules import (
    apply_character_damage,
    apply_character_healing,
    apply_character_resurrection,
    get_effective_hp_max,
    get_life_state,
    is_dead,
    roll_saving_throw,
)

svc = CombatService()


RESURRECTION_SPELLS: dict[str, dict[str, int | None]] = {
    "Raise Dead": {"hp": 1},
    "复活死者": {"hp": 1},
    "Revivify": {"hp": 1},
    "回生术": {"hp": 1},
    "Resurrection": {"hp": None},
    "复生": {"hp": None},
}


SPELL_CONDITIONS: dict[str, tuple[str, str | None]] = {
    "Guidance": ("guided", None),
    "引导": ("guided", None),
    "Resistance": ("resistance", None),
    "抵抗": ("resistance", None),
    "Bless": ("blessed", None),
    "祝福": ("blessed", None),
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
    "诡异诅咒": ("hexed", None),
    "Hunter's Mark": ("hunters_marked", None),
    "猎手印记": ("hunters_marked", None),
    "Divine Favor": ("divine_favor", None),
    "天界印记": ("divine_favor", None),
    "Bane": ("baned", "cha"),
    "灾祸术": ("baned", "cha"),
}


SPELL_CONDITION_DURATION_OVERRIDES: dict[str, int | None] = {
    "Guidance": 10,
    "引导": 10,
    "Resistance": 10,
    "抵抗": 10,
    "Bless": 10,
    "祝福": 10,
    "Command": 1,
    "命令术": 1,
    "Sleep": 10,
    "睡眠术": 10,
    "Hold Person": 10,
    "定身术": 10,
    "Entangle": 10,
    "纠缠术": 10,
    "Faerie Fire": 10,
    "妖火": 10,
    "Bane": 10,
    "灾祸术": 10,
    "Blindness/Deafness": 10,
    "目盲/耳聋": 10,
    "Fear": 10,
    "恐惧术": 10,
    "Web": 600,
    "蛛网": 600,
    "Silence": 100,
    "沉默术": 100,
    "Hex": 600,
    "妖术": 600,
    "诡异诅咒": 600,
    "Hunter's Mark": 600,
    "猎手印记": 600,
    "Divine Favor": 10,
    "天界印记": 10,
}


def _spell_lookup_names(spell_name: str, spell: dict[str, Any] | None = None) -> list[str]:
    names = [spell_name]
    if spell:
        for key in ("name", "name_en"):
            value = spell.get(key)
            if value and value not in names:
                names.append(value)
    return names


def spell_applies_condition(spell_type: str | None, spell_name: str, spell: dict[str, Any] | None) -> bool:
    """Return whether this spell should write a combat condition to targets."""
    if spell_type == "control":
        return True
    if spell and spell.get("condition"):
        return True
    return any(name in SPELL_CONDITIONS for name in _spell_lookup_names(spell_name, spell))


def resolve_spell_condition_duration(
    spell_name: str,
    spell: dict[str, Any] | None,
    *,
    default_rounds: int | None = None,
) -> int | None:
    """Return combat-round duration for a spell-applied condition."""
    for name in _spell_lookup_names(spell_name, spell):
        if name in SPELL_CONDITION_DURATION_OVERRIDES:
            return SPELL_CONDITION_DURATION_OVERRIDES[name]

    if not spell:
        return default_rounds

    explicit = spell.get("duration_rounds")
    if explicit is not None:
        try:
            return max(1, int(explicit))
        except (TypeError, ValueError):
            return default_rounds

    desc = str(spell.get("desc") or "")
    if "1分钟" in desc or "1 分钟" in desc:
        return 10
    if "10分钟" in desc or "10 分钟" in desc:
        return 100
    if "1小时" in desc or "1 小时" in desc:
        return 600
    match = re.search(r"(\d+)\s*分钟", desc)
    if match:
        return max(1, int(match.group(1)) * 10)
    match = re.search(r"(\d+)\s*小时", desc)
    if match:
        return max(1, int(match.group(1)) * 600)

    if spell.get("concentration"):
        return default_rounds if default_rounds is not None else 10
    return default_rounds


def _apply_condition_to_enemy(
    enemy: dict[str, Any],
    condition_name: str,
    duration_rounds: int | None,
) -> None:
    conditions = list(enemy.get("conditions", []))
    if condition_name not in conditions:
        conditions.append(condition_name)
    enemy["conditions"] = conditions
    if duration_rounds is not None:
        durations = dict(enemy.get("condition_durations", {}))
        durations[condition_name] = duration_rounds
        enemy["condition_durations"] = durations


def _apply_condition_to_character(
    character,
    condition_name: str,
    duration_rounds: int | None,
) -> None:
    conditions = list(character.conditions or [])
    if condition_name not in conditions:
        conditions.append(condition_name)
    character.conditions = conditions
    if duration_rounds is not None:
        durations = dict(character.condition_durations or {})
        durations[condition_name] = duration_rounds
        character.condition_durations = durations


def _is_guiding_bolt(spell_name: str | None) -> bool:
    return str(spell_name or "").strip().lower() in {"guiding bolt", "神力打击"}


def resolve_spell_condition(spell_name: str, spell: dict[str, Any]) -> tuple[str, str | None]:
    """Return the condition and saving throw ability for a control/utility spell."""
    if spell.get("condition"):
        return spell["condition"], spell.get("save")
    explicit_save = spell.get("save") if "save" in spell else None
    for name in _spell_lookup_names(spell_name, spell):
        if name in SPELL_CONDITIONS:
            condition, mapped_save = SPELL_CONDITIONS[name]
            return condition, explicit_save if "save" in spell else mapped_save
    return "affected", spell.get("save")


def get_resurrection_spell_config(spell_name: str, spell: dict[str, Any] | None = None) -> dict[str, int | None] | None:
    """Return resurrection settings for utility spells that revive dead characters."""
    config = RESURRECTION_SPELLS.get(spell_name)
    if config:
        return config
    name_en = spell.get("name_en") if spell else None
    return RESURRECTION_SPELLS.get(name_en)


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
    is_critical: bool = False,
    spell_name: str | None = None,
):
    """Apply spell damage to an enemy dict or Character and return response result plus conc log."""
    target_enemy = next((enemy for enemy in enemies if enemy.get("id") == target_id), None)
    if target_enemy:
        target_enemy["hp_current"] = svc.apply_damage(
            target_enemy.get("hp_current", 0),
            damage,
            target_enemy.get("derived", {}).get("hp_max", 10),
        )
        if _is_guiding_bolt(spell_name):
            _apply_condition_to_enemy(target_enemy, "guiding_bolt", 1)
        return {
            "target_id": target_id,
            "target_name": target_enemy.get("name", "敌人"),
            "damage": damage,
            "new_hp": target_enemy["hp_current"],
            "conditions": target_enemy.get("conditions", []),
            "condition_durations": target_enemy.get("condition_durations", {}),
            "save": save_result,
        }, None

    target_character = await db.get(Character, target_id)
    if not target_character:
        return None, None

    damage_result = apply_character_damage(target_character, damage, is_critical=is_critical)
    concentration_log = await do_concentration_check(target_character, damage, session_id)
    if _is_guiding_bolt(spell_name):
        _apply_condition_to_character(target_character, "guiding_bolt", 1)
    return {
        "target_id": target_id,
        "target_name": target_character.name,
        "damage": damage,
        "new_hp": damage_result["hp_after"],
        "hp_current": damage_result["hp_after"],
        "death_saves": damage_result["death_saves"],
        "conditions": target_character.conditions or damage_result["conditions"],
        "condition_durations": target_character.condition_durations or {},
        "life_state": get_life_state(target_character),
        "concentration": target_character.concentration,
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
        "hp_current": heal_result["hp_after"],
        "revived": heal_result["revived"],
        "death_saves": heal_result["death_saves"],
        "conditions": heal_result["conditions"],
        "life_state": get_life_state(target_character),
    }


async def apply_resurrection_spell_to_target(db, target_id: str, spell_name: str, spell: dict[str, Any]):
    """Apply a resurrection utility spell to a dead Character."""
    target_character = await db.get(Character, target_id)
    if not target_character:
        return None

    config = get_resurrection_spell_config(spell_name, spell)
    if not config:
        return None
    hp_max = get_effective_hp_max(target_character)
    if not is_dead(target_character):
        return {
            "target_id": target_id,
            "target_name": target_character.name,
            "resurrected": False,
            "new_hp": target_character.hp_current,
            "hp_current": target_character.hp_current,
            "hp_max": hp_max,
            "death_saves": target_character.death_saves,
            "conditions": target_character.conditions or [],
            "life_state": get_life_state(target_character),
            "reason": "target_not_dead",
        }

    result = apply_character_resurrection(target_character, hp=config.get("hp"))
    return {
        "target_id": target_id,
        "target_name": target_character.name,
        "resurrected": True,
        "new_hp": result["hp_after"],
        "hp_current": result["hp_after"],
        "hp_max": hp_max,
        "death_saves": result["death_saves"],
        "conditions": result["conditions"],
        "life_state": get_life_state(target_character),
    }


async def apply_armor_of_agathys_to_target(
    db,
    target_id: str,
    *,
    spell_name: str,
    spell: dict[str, Any],
    spell_level: int,
):
    """Apply Armor of Agathys to a Character target."""
    if not is_armor_of_agathys(spell_name, spell):
        return None

    target_character = await db.get(Character, target_id)
    if not target_character:
        return None

    return apply_armor_of_agathys_to_character(
        target_character,
        spell_level=spell_level,
        duration_rounds=resolve_spell_condition_duration(
            spell_name,
            spell,
            default_rounds=600,
        ) or 600,
    )


async def apply_control_spell_to_target(
    db,
    enemies: list[dict[str, Any]],
    target_id: str,
    *,
    session_id: str,
    condition_name: str,
    save_ability: str | None,
    spell_save_dc: int,
    duration_rounds: int | None = None,
):
    """Resolve a control spell save and apply its condition if the target fails."""
    saved = False
    save_detail = None
    concentration_log = None

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
            _apply_condition_to_enemy(target_enemy, condition_name, duration_rounds)
        elif target_character:
            _apply_condition_to_character(target_character, condition_name, duration_rounds)
            concentration_log = break_concentration_if_incapacitated(target_character, session_id)

    target_enemy_hp = target_enemy.get("hp_current") if target_enemy else None

    return {
        "condition_name": condition_name,
        "save_detail": save_detail,
        "saved": saved,
        "applied": not saved,
        "target_state": (
            {
                "target_id": target_id,
                "target_name": target_enemy.get("name", "敌人"),
                "conditions": target_enemy.get("conditions", []),
                "condition_durations": target_enemy.get("condition_durations", {}),
                "life_state": "dead" if target_enemy_hp is not None and target_enemy_hp <= 0 else "alive",
            }
            if target_enemy else (
                {
                    "target_id": target_id,
                    "target_name": target_character.name,
                    "conditions": target_character.conditions or [],
                    "condition_durations": target_character.condition_durations or {},
                    "life_state": get_life_state(target_character),
                    "concentration": target_character.concentration,
                }
                if target_character else None
            )
        ),
        "concentration_log": concentration_log,
    }
