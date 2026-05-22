from __future__ import annotations

from models import GameLog
from services.character_roster import CharacterRoster
from services.dnd_rules import (
    HIT_DICE,
    _normalize_class,
    get_class_resource_defaults,
    roll_dice,
)


async def apply_party_rest(db, session, rest_type: str) -> dict:
    """Apply a short or long rest to the whole party and persist the system log."""
    if rest_type not in ("long", "short"):
        raise ValueError("rest_type must be 'long' or 'short'")

    roster = CharacterRoster(db, session)
    results = []
    for character in await roster.party():
        results.append(_apply_rest_to_character(character, rest_type))

    rest_label = "长休" if rest_type == "long" else "短休"
    db.add(GameLog(
        session_id=session.id,
        role="system",
        content=(
            f"🌙 队伍完成了{rest_label}。"
            + ("HP和法术位已完全恢复。" if rest_type == "long" else "消耗了一颗生命骰。")
        ),
        log_type="system",
    ))
    return {"rest_type": rest_type, "characters": results}


def _apply_rest_to_character(character, rest_type: str) -> dict:
    derived = character.derived or {}
    hp_max = derived.get("hp_max", character.hp_current)
    hit_die = derived.get("hit_die", HIT_DICE.get(_normalize_class(character.char_class), 8))
    con_mod = derived.get("ability_modifiers", {}).get("con", 0)
    caster_type = derived.get("caster_type")
    slots_max = dict(derived.get("spell_slots_max", {}))
    old_hp = character.hp_current
    if character.hit_dice_remaining is None:
        character.hit_dice_remaining = character.level

    if rest_type == "long":
        cls_key = _normalize_class(character.char_class)
        restored_dice = max(1, character.level // 2)
        character.hp_current = hp_max
        character.spell_slots = slots_max
        character.conditions = []
        character.concentration = None
        character.hit_dice_remaining = min(character.level, (character.hit_dice_remaining or 0) + restored_dice)
        character.class_resources = get_class_resource_defaults(cls_key, character.level, subclass=character.subclass)
        return {
            "name": character.name,
            "hp_recovered": hp_max - old_hp,
            "hp_current": hp_max,
            "slots_restored": slots_max,
            "hit_dice_remaining": character.hit_dice_remaining,
        }

    return _apply_short_rest_to_character(
        character=character,
        old_hp=old_hp,
        hp_max=hp_max,
        hit_die=hit_die,
        con_mod=con_mod,
        caster_type=caster_type,
        slots_max=slots_max,
    )


def _apply_short_rest_to_character(
    *,
    character,
    old_hp: int,
    hp_max: int,
    hit_die: int,
    con_mod: int,
    caster_type: str | None,
    slots_max: dict,
) -> dict:
    hd_remaining = character.hit_dice_remaining or 0
    hit_roll_result = None
    if hd_remaining > 0:
        hit_roll = roll_dice(f"1d{hit_die}")
        heal_amt = max(1, hit_roll["total"] + con_mod)
        character.hp_current = min(hp_max, character.hp_current + heal_amt)
        character.hit_dice_remaining = hd_remaining - 1
        hit_roll_result = hit_roll["rolls"][0]

    if caster_type == "pact":
        character.spell_slots = slots_max

    class_resources = dict(character.class_resources or {})
    changed = _restore_short_rest_class_resources(character, class_resources)
    if changed:
        character.class_resources = class_resources

    return {
        "name": character.name,
        "hit_die_roll": hit_roll_result,
        "con_mod": con_mod,
        "hp_recovered": character.hp_current - old_hp,
        "hp_current": character.hp_current,
        "slots_restored": slots_max if caster_type == "pact" else {},
        "hit_dice_remaining": character.hit_dice_remaining,
        "no_hit_dice": hd_remaining <= 0,
        "class_resources": class_resources if changed else None,
    }


def _restore_short_rest_class_resources(character, class_resources: dict) -> bool:
    cls_key = _normalize_class(character.char_class)
    if cls_key == "Fighter":
        class_resources["second_wind_used"] = False
        if character.level >= 2:
            class_resources["action_surge_used"] = False
        sub_effects = (character.derived or {}).get("subclass_effects", {})
        if sub_effects.get("battle_master"):
            class_resources["superiority_dice_remaining"] = sub_effects.get("superiority_dice_max", 4)
        return True

    if cls_key == "Monk" and character.level >= 2:
        class_resources["ki_remaining"] = (character.derived or {}).get("subclass_effects", {}).get("ki_max", character.level)
        return True

    if cls_key == "Bard" and character.level >= 5:
        cha_mod = (character.derived or {}).get("ability_modifiers", {}).get("cha", 3)
        class_resources["bardic_inspiration_remaining"] = max(1, cha_mod)
        return True

    if cls_key in {"Cleric", "Paladin"}:
        class_resources["channel_divinity_used"] = False
        return True

    if cls_key == "Druid":
        _restore_druid_natural_recovery(character)
        return True

    return False


def _restore_druid_natural_recovery(character) -> None:
    sub_effects = (character.derived or {}).get("subclass_effects", {})
    if not (sub_effects.get("circle_of_land") and sub_effects.get("natural_recovery")):
        return

    max_slot_level = (character.level + 1) // 2
    slots_max = (character.derived or {}).get("spell_slots_max", {})
    current_slots = dict(character.spell_slots or {})
    recovery_budget = (character.level + 1) // 2
    for level in range(1, min(max_slot_level + 1, 6)):
        slot_key = ["1st", "2nd", "3rd", "4th", "5th"][level - 1]
        cap = slots_max.get(slot_key, 0)
        current = current_slots.get(slot_key, 0)
        if current < cap and recovery_budget >= level:
            current_slots[slot_key] = current + 1
            recovery_budget -= level
    character.spell_slots = current_slots
