"""Temporary HP and Armor of Agathys helpers for combat rules."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from models import Character
from services.combat_service import CombatService
from services.dnd_rules import apply_character_damage, get_life_state, get_temporary_hp, grant_temporary_hp

svc = CombatService()

ARMOR_OF_AGATHYS_NAMES = {"armor of agathys", "寒甲"}


def is_armor_of_agathys(spell_name: str | None, spell: dict[str, Any] | None = None) -> bool:
    """Return whether spell data names Armor of Agathys."""
    names = [spell_name]
    if spell:
        names.extend([spell.get("name"), spell.get("name_en")])
    return any(str(name or "").strip().lower() in ARMOR_OF_AGATHYS_NAMES for name in names)


def apply_generic_temporary_hp_to_character(
    character: Character,
    *,
    amount: int,
    source: str,
) -> dict[str, Any]:
    """Grant generic non-stacking temporary HP and return a compact target state."""
    summary = grant_temporary_hp(
        character,
        amount,
        source=source,
        replace_if_higher=True,
    )
    state = build_character_target_state(character)
    state.update({
        "temporary_hp_before": summary["temporary_hp_before"],
        "temporary_hp_after": summary["temporary_hp_after"],
        "temporary_hp_granted": summary["temporary_hp_granted"],
        "temporary_hp_source": source,
        "reason": summary.get("reason"),
    })
    return state


def apply_armor_of_agathys_to_character(
    character: Character,
    *,
    spell_level: int,
    duration_rounds: int = 600,
) -> dict[str, Any]:
    """Grant Armor of Agathys temp HP and track its retaliation damage."""
    level = max(1, int(spell_level or 1))
    amount = 5 * level
    before = get_temporary_hp(character)
    summary = grant_temporary_hp(
        character,
        amount,
        source="armor_of_agathys",
        replace_if_higher=True,
    )

    resources = dict(character.class_resources or {})
    if summary["applied"]:
        resources["armor_of_agathys_active"] = True
        resources["armor_of_agathys_damage"] = amount
        resources["armor_of_agathys_spell_level"] = level
        resources["temporary_hp_source"] = "armor_of_agathys"
        character.class_resources = resources

        conditions = list(character.conditions or [])
        if "armor_of_agathys" not in conditions:
            conditions.append("armor_of_agathys")
        character.conditions = conditions

        durations = dict(character.condition_durations or {})
        durations["armor_of_agathys"] = duration_rounds
        character.condition_durations = durations
    elif resources.get("temporary_hp_source") == "armor_of_agathys":
        conditions = list(character.conditions or [])
        if "armor_of_agathys" not in conditions:
            conditions.append("armor_of_agathys")
        character.conditions = conditions

    return {
        "target_id": character.id,
        "target_name": character.name,
        "temporary_hp_before": before,
        "temporary_hp_after": get_temporary_hp(character),
        "temporary_hp_granted": amount if summary["applied"] else 0,
        "armor_of_agathys_damage": resources.get("armor_of_agathys_damage", 0),
        "new_hp": character.hp_current,
        "hp_current": character.hp_current,
        "death_saves": character.death_saves,
        "conditions": character.conditions or [],
        "condition_durations": character.condition_durations or {},
        "class_resources": character.class_resources or {},
        "life_state": get_life_state(character),
        "reason": summary.get("reason"),
    }


def _active_armor_of_agathys_damage(character: Character) -> int:
    resources = dict(character.class_resources or {})
    if resources.get("temporary_hp_source") != "armor_of_agathys":
        return 0
    if get_temporary_hp(character) <= 0:
        return 0
    try:
        return max(0, int(resources.get("armor_of_agathys_damage") or 0))
    except (TypeError, ValueError):
        return 0


def get_armor_of_agathys_retaliation_damage(character: Character) -> int:
    """Return cold retaliation damage that should be locked in before applying a hit."""
    return _active_armor_of_agathys_damage(character)


def build_character_target_state(character: Character) -> dict[str, Any]:
    """Build the common character target_state shape used by combat endpoints."""
    state = {
        "target_id": character.id,
        "hp_current": character.hp_current,
        "new_hp": character.hp_current,
        "death_saves": getattr(character, "death_saves", None),
        "conditions": getattr(character, "conditions", None) or [],
        "life_state": get_life_state(character),
        "concentration": getattr(character, "concentration", None),
    }
    temporary_hp = get_temporary_hp(character)
    if temporary_hp:
        state["temporary_hp"] = temporary_hp
    condition_durations = getattr(character, "condition_durations", None) or {}
    if condition_durations:
        state["condition_durations"] = condition_durations
    class_resources = getattr(character, "class_resources", None) or {}
    if class_resources:
        state["class_resources"] = class_resources
    return state


def apply_armor_of_agathys_retaliation_to_enemy(
    *,
    defender: Character,
    attacker_enemy: dict[str, Any] | None,
    enemies: list[dict[str, Any]],
    melee_hit: bool = True,
    retaliation_damage: int | None = None,
) -> dict[str, Any] | None:
    """Apply Armor of Agathys cold retaliation to an enemy that made a melee hit."""
    if not melee_hit or not attacker_enemy:
        return None

    locked_damage = retaliation_damage
    if locked_damage is None:
        locked_damage = _active_armor_of_agathys_damage(defender)
    if locked_damage <= 0:
        return None

    target_id = attacker_enemy.get("id")
    enemy = next((item for item in enemies if item.get("id") == target_id), attacker_enemy)
    final_damage = svc.apply_damage_with_resistance(
        locked_damage,
        "cold",
        enemy.get("resistances", []),
        enemy.get("immunities", []),
        enemy.get("vulnerabilities", []),
    )
    enemy["hp_current"] = svc.apply_damage(
        enemy.get("hp_current", 0),
        final_damage,
        enemy.get("derived", {}).get("hp_max", enemy.get("hp_max", 10)),
    )

    return {
        "source": "armor_of_agathys",
        "defender_id": defender.id,
        "defender_name": defender.name,
        "target_id": enemy.get("id"),
        "target_name": enemy.get("name", "敌人"),
        "damage_type": "cold",
        "damage": final_damage,
        "base_damage": locked_damage,
        "target_new_hp": enemy.get("hp_current", 0),
    }


async def apply_armor_of_agathys_retaliation_to_character(
    db,
    *,
    defender: Character,
    attacker_character_id: str | None,
    melee_hit: bool = True,
    retaliation_damage: int | None = None,
) -> dict[str, Any] | None:
    """Apply Armor of Agathys retaliation to a Character attacker."""
    if not melee_hit or not attacker_character_id:
        return None

    locked_damage = retaliation_damage
    if locked_damage is None:
        locked_damage = _active_armor_of_agathys_damage(defender)
    if locked_damage <= 0:
        return None

    attacker = await db.get(Character, attacker_character_id)
    if not attacker:
        return None

    damage_result = apply_character_damage(attacker, locked_damage)
    return {
        "source": "armor_of_agathys",
        "defender_id": defender.id,
        "defender_name": defender.name,
        "target_id": attacker.id,
        "target_name": attacker.name,
        "damage_type": "cold",
        "damage": damage_result["damage_to_hp"] + damage_result["damage_to_temporary_hp"],
        "base_damage": locked_damage,
        "target_new_hp": attacker.hp_current,
        "target_state": build_character_target_state(attacker),
    }


def maybe_flag_character_resources(character: Character) -> None:
    """Mark JSON fields that Armor of Agathys and temp HP helpers may mutate."""
    for field in ("class_resources", "conditions", "condition_durations"):
        try:
            flag_modified(character, field)
        except Exception:
            pass
