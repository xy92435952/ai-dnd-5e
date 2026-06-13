from dataclasses import dataclass
from typing import Callable

from services.dnd_rules import (
    ASI_LEVELS,
    ASI_LEVELS_FIGHTER,
    ASI_LEVELS_ROGUE,
    FEATS,
    HIT_DICE,
    SPELL_PREPARATION_TYPE,
    _normalize_class,
    ability_modifier,
    calc_derived,
    get_cantrips_count,
    get_class_resource_defaults,
    get_effective_hp_max,
    roll_dice,
)


@dataclass
class CharacterLevelingError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


SPELLS_KNOWN = {
    "Bard": {
        1: 4, 2: 5, 3: 6, 4: 7, 5: 8, 6: 9, 7: 10, 8: 11, 9: 12, 10: 14,
        11: 15, 13: 16, 14: 18, 15: 19, 17: 20, 18: 22,
    },
    "Ranger": {
        2: 2, 3: 3, 5: 4, 7: 5, 9: 6, 11: 7, 13: 8, 15: 9, 17: 10, 19: 11,
    },
    "Sorcerer": {
        1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9, 9: 10, 10: 11,
        11: 12, 13: 13, 15: 14, 17: 15,
    },
    "Warlock": {
        1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9, 9: 10, 10: 10,
        11: 11, 12: 11, 13: 12, 14: 12, 15: 13, 16: 13, 17: 14, 18: 14,
        19: 15, 20: 15,
    },
}

SLOT_LEVELS = {
    "1st": 1,
    "2nd": 2,
    "3rd": 3,
    "4th": 4,
    "5th": 5,
    "6th": 6,
    "7th": 7,
    "8th": 8,
    "9th": 9,
}


def get_asi_levels_for_class(cls_key: str) -> set[int]:
    if cls_key == "Fighter":
        return ASI_LEVELS_FIGHTER
    if cls_key == "Rogue":
        return ASI_LEVELS_ROGUE
    return ASI_LEVELS


def build_level_up_update(
    *,
    char_class: str,
    level: int,
    ability_scores: dict,
    derived: dict | None,
    hp_current: int,
    spell_slots: dict | None,
    use_average_hp: bool,
    subclass: str | None = None,
    fighting_style: str | None = None,
    feats: list | None = None,
    equipment: dict | None = None,
    class_resources: dict | None = None,
    known_spells: list[str] | None = None,
    cantrips: list[str] | None = None,
    race: str | None = None,
    proficient_skills: list[str] | None = None,
    ability_score_increases: dict | None = None,
    feat_choice: dict | None = None,
    learned_spells: list[str] | None = None,
    learned_cantrips: list[str] | None = None,
    available_class_spells: list | None = None,
    available_class_cantrips: list[str] | None = None,
    dice_roller: Callable[[str], dict] = roll_dice,
    condition_durations: dict | None = None,
) -> dict:
    old_level = level
    new_level = old_level + 1
    if new_level > 20:
        raise CharacterLevelingError(400, "角色已达最高等级20")

    cls_key = _normalize_class(char_class)
    hit_die = HIT_DICE.get(cls_key, 8)
    next_scores = dict(ability_scores or {})
    con_mod = ability_modifier(next_scores.get("con", 10))

    if use_average_hp:
        hp_gain = hit_die // 2 + 1 + con_mod
    else:
        hp_roll = dice_roller(f"1d{hit_die}")
        hp_gain = max(1, hp_roll["total"] + con_mod)

    asi_levels = get_asi_levels_for_class(cls_key)
    next_feats = list(feats or [])

    if new_level in asi_levels:
        if feat_choice:
            feat_name = feat_choice.get("name", "")
            if feat_name not in FEATS:
                raise CharacterLevelingError(400, f"未知专长：{feat_name}")
            next_feats.append(feat_choice)
        elif ability_score_increases:
            total_increase = sum(ability_score_increases.values())
            if total_increase > 2:
                raise CharacterLevelingError(400, "ASI每次最多增加2点属性值")
            for ability, increase in ability_score_increases.items():
                if ability in next_scores:
                    next_scores[ability] = min(20, next_scores[ability] + increase)

    old_derived = dict(derived or {})
    next_derived = calc_derived(
        char_class,
        new_level,
        next_scores,
        subclass,
        fighting_style=fighting_style,
        feats=next_feats or None,
        equipment=equipment or None,
        race=race,
        proficient_skills=proficient_skills or [],
    )

    new_hp_current = min(
        hp_current + hp_gain,
        get_effective_hp_max(
            {
                "derived": next_derived,
                "condition_durations": condition_durations or {},
                "hp_current": hp_current,
            },
            next_derived["hp_max"],
        ),
    )
    next_spell_slots = _advance_spell_slots(
        current_slots=spell_slots,
        old_slots_max=old_derived.get("spell_slots_max", {}),
        new_slots_max=next_derived.get("spell_slots_max", {}),
    )
    next_class_resources = _advance_class_resources(
        current_resources=class_resources,
        old_defaults=_class_resource_defaults_for_level(
            char_class=cls_key,
            level=old_level,
            subclass=subclass,
            derived=old_derived,
        ),
        new_defaults=_class_resource_defaults_for_level(
            char_class=cls_key,
            level=new_level,
            subclass=subclass,
            derived=next_derived,
        ),
    )
    spell_learning = _advance_spell_learning(
        cls_key=cls_key,
        old_level=old_level,
        new_level=new_level,
        next_spell_slots_max=next_derived.get("spell_slots_max", {}),
        known_spells=known_spells,
        cantrips=cantrips,
        learned_spells=learned_spells,
        learned_cantrips=learned_cantrips,
        available_class_spells=available_class_spells,
        available_class_cantrips=available_class_cantrips,
    )

    return {
        "old_level": old_level,
        "new_level": new_level,
        "hp_gain": hp_gain,
        "is_asi_level": new_level in asi_levels,
        "ability_scores": next_scores,
        "feats": next_feats,
        "derived": next_derived,
        "hp_current": new_hp_current,
        "spell_slots": next_spell_slots,
        "class_resources": next_class_resources,
        "new_spell_slots": next_derived.get("spell_slots_max", {}),
        "known_spells": spell_learning["known_spells"],
        "cantrips": spell_learning["cantrips"],
        "learned_spells": spell_learning["learned_spells"],
        "learned_cantrips": spell_learning["learned_cantrips"],
        "preparation_type": spell_learning["preparation_type"],
    }


def _advance_spell_slots(
    *,
    current_slots: dict | None,
    old_slots_max: dict | None,
    new_slots_max: dict | None,
) -> dict:
    next_slots = dict(current_slots or {})
    old_max = old_slots_max or {}

    for slot_key, max_value in (new_slots_max or {}).items():
        current_value = next_slots.get(slot_key, 0)
        gained = max(0, max_value - old_max.get(slot_key, 0))
        next_slots[slot_key] = min(max_value, current_value + gained)

    return next_slots


def _class_resource_defaults_for_level(
    *,
    char_class: str,
    level: int,
    subclass: str | None,
    derived: dict | None,
) -> dict:
    cls_key = _normalize_class(char_class)
    resources = get_class_resource_defaults(cls_key, level, subclass=subclass)
    derived = derived or {}
    subclass_effects = derived.get("subclass_effects", {}) or {}
    ability_mods = derived.get("ability_modifiers", {}) or {}

    if cls_key == "Fighter":
        if subclass_effects.get("battle_master"):
            resources["superiority_dice_remaining"] = subclass_effects.get("superiority_dice_max", 4)
        if subclass_effects.get("samurai"):
            resources["fighting_spirit_remaining"] = subclass_effects.get(
                "fighting_spirit_uses",
                max(1, ability_mods.get("wis", 1)),
            )
    if cls_key == "Bard":
        resources["bardic_inspiration_remaining"] = max(1, ability_mods.get("cha", 3))
    if cls_key == "Cleric" and subclass_effects.get("war_domain"):
        resources["war_priest_remaining"] = max(1, ability_mods.get("wis", 1))
    if cls_key == "Wizard" and subclass_effects.get("divination"):
        resources["portent_remaining"] = subclass_effects.get("portent_count", 3 if level >= 14 else 2)
    if cls_key == "Monk" and level >= 2:
        resources["ki_remaining"] = subclass_effects.get("ki_max", level)

    return resources


def _advance_class_resources(
    *,
    current_resources: dict | None,
    old_defaults: dict | None,
    new_defaults: dict | None,
) -> dict:
    next_resources = dict(current_resources or {})
    old_defaults = old_defaults or {}

    for key, new_default in (new_defaults or {}).items():
        if isinstance(new_default, bool):
            next_resources[key] = bool(next_resources.get(key, new_default))
            continue

        if isinstance(new_default, int):
            current_value = next_resources.get(key, old_defaults.get(key, 0))
            old_value = old_defaults.get(key, 0)
            gained = max(0, new_default - old_value)
            try:
                next_value = int(current_value or 0) + gained
            except (TypeError, ValueError):
                next_value = gained
            next_resources[key] = min(new_default, next_value)
            continue

        next_resources.setdefault(key, new_default)

    return next_resources


def _advance_spell_learning(
    *,
    cls_key: str,
    old_level: int,
    new_level: int,
    next_spell_slots_max: dict | None,
    known_spells: list[str] | None,
    cantrips: list[str] | None,
    learned_spells: list[str] | None,
    learned_cantrips: list[str] | None,
    available_class_spells: list | None,
    available_class_cantrips: list[str] | None,
) -> dict:
    preparation_type = SPELL_PREPARATION_TYPE.get(cls_key)
    requested_spells = _clean_choices(learned_spells)
    requested_cantrips = _clean_choices(learned_cantrips)
    next_known_spells = list(known_spells or [])
    next_cantrips = list(cantrips or [])

    spell_capacity = _leveled_spell_learning_capacity(
        cls_key=cls_key,
        old_level=old_level,
        new_level=new_level,
        preparation_type=preparation_type,
    )
    cantrip_capacity = max(
        0,
        get_cantrips_count(cls_key, new_level) - get_cantrips_count(cls_key, old_level),
    )

    if len(requested_spells) > spell_capacity:
        raise CharacterLevelingError(
            400,
            f"Level {new_level} {cls_key} can learn {spell_capacity} leveled spell(s); "
            f"selected {len(requested_spells)}.",
        )
    if len(requested_cantrips) > cantrip_capacity:
        raise CharacterLevelingError(
            400,
            f"Level {new_level} {cls_key} can learn {cantrip_capacity} cantrip(s); "
            f"selected {len(requested_cantrips)}.",
        )

    _reject_duplicate_choices(requested_spells, "learned_spells")
    _reject_duplicate_choices(requested_cantrips, "learned_cantrips")

    spell_levels = _available_spell_levels(available_class_spells)
    max_spell_level = _max_leveled_spell_rank(next_spell_slots_max)
    known_set = set(next_known_spells)
    for spell_name in requested_spells:
        if spell_name in known_set:
            raise CharacterLevelingError(400, f"Spell '{spell_name}' is already known.")
        spell_level = spell_levels.get(spell_name)
        if spell_level is None or spell_level <= 0:
            raise CharacterLevelingError(400, f"Spell '{spell_name}' is not a class leveled spell.")
        if max_spell_level <= 0 or spell_level > max_spell_level:
            raise CharacterLevelingError(
                400,
                f"Spell '{spell_name}' requires level {spell_level}; max allowed is {max_spell_level}.",
            )
        next_known_spells.append(spell_name)
        known_set.add(spell_name)

    available_cantrips = set(available_class_cantrips or [])
    cantrip_set = set(next_cantrips)
    for cantrip_name in requested_cantrips:
        if cantrip_name in cantrip_set:
            raise CharacterLevelingError(400, f"Cantrip '{cantrip_name}' is already known.")
        if cantrip_name not in available_cantrips:
            raise CharacterLevelingError(400, f"Cantrip '{cantrip_name}' is not a class cantrip.")
        next_cantrips.append(cantrip_name)
        cantrip_set.add(cantrip_name)

    return {
        "known_spells": next_known_spells,
        "cantrips": next_cantrips,
        "learned_spells": requested_spells,
        "learned_cantrips": requested_cantrips,
        "preparation_type": preparation_type,
    }


def _leveled_spell_learning_capacity(
    *,
    cls_key: str,
    old_level: int,
    new_level: int,
    preparation_type: str | None,
) -> int:
    if preparation_type == "spellbook" and cls_key == "Wizard":
        return 2
    if preparation_type == "known":
        return max(
            0,
            _progression_count(SPELLS_KNOWN.get(cls_key, {}), new_level)
            - _progression_count(SPELLS_KNOWN.get(cls_key, {}), old_level),
        )
    return 0


def _progression_count(table: dict[int, int], level: int) -> int:
    count = 0
    for threshold, value in sorted(table.items()):
        if level >= threshold:
            count = value
    return count


def _available_spell_levels(available_class_spells: list | None) -> dict[str, int | None]:
    spell_levels: dict[str, int | None] = {}
    for spell in available_class_spells or []:
        if isinstance(spell, str):
            spell_levels[spell] = None
            continue
        if not isinstance(spell, dict):
            continue
        name = spell.get("name")
        if not name:
            continue
        try:
            spell_levels[name] = int(spell.get("level", 0))
        except (TypeError, ValueError):
            spell_levels[name] = None
    return spell_levels


def _max_leveled_spell_rank(spell_slots_max: dict | None) -> int:
    max_rank = 0
    for slot_key, count in (spell_slots_max or {}).items():
        try:
            slot_count = int(count or 0)
        except (TypeError, ValueError):
            slot_count = 0
        if slot_count <= 0:
            continue
        max_rank = max(max_rank, SLOT_LEVELS.get(slot_key, _parse_slot_level(slot_key)))
    return max_rank


def _parse_slot_level(slot_key: str) -> int:
    try:
        return int(str(slot_key).strip().lower().replace("level", ""))
    except (TypeError, ValueError):
        return 0


def _clean_choices(choices: list[str] | None) -> list[str]:
    return [str(choice).strip() for choice in choices or [] if str(choice).strip()]


def _reject_duplicate_choices(choices: list[str], label: str) -> None:
    if len(set(choices)) != len(choices):
        raise CharacterLevelingError(400, f"Duplicate choices are not allowed in {label}.")
