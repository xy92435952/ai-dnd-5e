from dataclasses import dataclass
from typing import Callable

from services.dnd_rules import (
    ASI_LEVELS,
    ASI_LEVELS_FIGHTER,
    ASI_LEVELS_ROGUE,
    FEATS,
    HIT_DICE,
    _normalize_class,
    ability_modifier,
    calc_derived,
    get_effective_hp_max,
    roll_dice,
)


@dataclass
class CharacterLevelingError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


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
    race: str | None = None,
    proficient_skills: list[str] | None = None,
    ability_score_increases: dict | None = None,
    feat_choice: dict | None = None,
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
        "new_spell_slots": next_derived.get("spell_slots_max", {}),
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
