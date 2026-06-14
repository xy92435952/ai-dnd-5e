from dataclasses import dataclass
from typing import Callable

from services.dnd_rules import (
    ASI_LEVELS,
    ASI_LEVELS_FIGHTER,
    ASI_LEVELS_ROGUE,
    BATTLE_MASTER_MANEUVERS,
    BATTLE_MASTER_MANEUVERS_KNOWN_BY_LEVEL,
    FEATS,
    FIGHTING_STYLE_CLASSES,
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
from services.dnd_subclass_progression import (
    canonical_subclass_choice,
    subclass_options_for_class,
    subclass_unlock_level,
)
from services.dnd_data import CLASS_SAVE_PROFICIENCIES
from services.character_feat_service import (
    apply_resilient_ability_bonuses,
    CharacterFeatError,
    feat_resource_defaults,
    normalize_existing_feats,
    normalize_level_up_feat_choice,
    resilient_ability_choices,
    validate_feat_prerequisites,
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
    proficient_saves: list[str] | None = None,
    ability_score_increases: dict | None = None,
    feat_choice: dict | None = None,
    subclass_choice: str | None = None,
    fighting_style_choice: str | None = None,
    maneuver_choices: list[str] | None = None,
    learned_spells: list[str] | None = None,
    learned_cantrips: list[str] | None = None,
    spell_replacements: list[dict] | None = None,
    magic_initiate_spell_options: dict | None = None,
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
    next_subclass = _resolve_subclass_choice(
        cls_key=cls_key,
        old_level=old_level,
        new_level=new_level,
        current_subclass=subclass,
        subclass_choice=subclass_choice,
    )
    next_fighting_style = _resolve_fighting_style_choice(
        cls_key=cls_key,
        old_level=old_level,
        new_level=new_level,
        current_fighting_style=fighting_style,
        fighting_style_choice=fighting_style_choice,
    )
    hit_die = HIT_DICE.get(cls_key, 8)
    next_scores = dict(ability_scores or {})
    con_mod = ability_modifier(next_scores.get("con", 10))

    if use_average_hp:
        hp_gain = hit_die // 2 + 1 + con_mod
    else:
        hp_roll = dice_roller(f"1d{hit_die}")
        hp_gain = max(1, hp_roll["total"] + con_mod)

    asi_levels = get_asi_levels_for_class(cls_key)
    next_feats = normalize_existing_feats(feats)
    selected_feat_choice = None

    if new_level in asi_levels:
        if feat_choice:
            try:
                feat_choice = normalize_level_up_feat_choice(
                    feat_choice,
                    existing_feats=next_feats,
                    magic_initiate_spell_options=magic_initiate_spell_options,
                )
            except CharacterFeatError as exc:
                raise CharacterLevelingError(exc.status_code, exc.detail) from exc
            feat_name = feat_choice.get("name", "")
            if feat_name not in FEATS:
                raise CharacterLevelingError(400, f"未知专长：{feat_name}")
            next_feats.append(feat_choice)
            selected_feat_choice = feat_choice
        elif ability_score_increases:
            total_increase = sum(ability_score_increases.values())
            if total_increase > 2:
                raise CharacterLevelingError(400, "ASI每次最多增加2点属性值")
            for ability, increase in ability_score_increases.items():
                if ability in next_scores:
                    next_scores[ability] = min(20, next_scores[ability] + increase)

    if selected_feat_choice:
        next_scores = apply_resilient_ability_bonuses(next_scores, [selected_feat_choice])
    next_scores = _apply_level_capstone_ability_scores(
        cls_key=cls_key,
        new_level=new_level,
        ability_scores=next_scores,
    )
    next_save_profs = list(dict.fromkeys([
        *(proficient_saves or CLASS_SAVE_PROFICIENCIES.get(cls_key, [])),
        *resilient_ability_choices(next_feats),
    ]))

    old_derived = dict(derived or {})
    next_derived = calc_derived(
        char_class,
        new_level,
        next_scores,
        next_subclass,
        fighting_style=next_fighting_style,
        feats=next_feats or None,
        equipment=equipment or None,
        race=race,
        proficient_skills=proficient_skills or [],
        proficient_saves=next_save_profs,
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
            subclass=next_subclass,
            derived=next_derived,
        ),
    )
    maneuver_learning = _advance_maneuver_choices(
        cls_key=cls_key,
        old_level=old_level,
        new_level=new_level,
        subclass=next_subclass,
        current_resources=next_class_resources,
        maneuver_choices=maneuver_choices,
    )
    next_class_resources = maneuver_learning["class_resources"]
    if selected_feat_choice:
        next_class_resources.update(feat_resource_defaults([selected_feat_choice]))
    spell_learning = _advance_spell_learning(
        cls_key=cls_key,
        old_level=old_level,
        new_level=new_level,
        next_spell_slots_max=next_derived.get("spell_slots_max", {}),
        known_spells=known_spells,
        cantrips=cantrips,
        learned_spells=learned_spells,
        learned_cantrips=learned_cantrips,
        spell_replacements=spell_replacements,
        available_class_spells=available_class_spells,
        available_class_cantrips=available_class_cantrips,
    )
    if selected_feat_choice:
        try:
            validate_feat_prerequisites(
                [selected_feat_choice],
                ability_scores=next_scores,
                derived=next_derived,
                known_spells=spell_learning["known_spells"],
                cantrips=spell_learning["cantrips"],
                spell_slots=next_spell_slots,
            )
        except CharacterFeatError as exc:
            raise CharacterLevelingError(exc.status_code, exc.detail) from exc

    return {
        "old_level": old_level,
        "new_level": new_level,
        "hp_gain": hp_gain,
        "is_asi_level": new_level in asi_levels,
        "ability_scores": next_scores,
        "proficient_saves": next_save_profs,
        "subclass": next_subclass,
        "fighting_style": next_fighting_style,
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
        "spell_replacements": spell_learning["spell_replacements"],
        "maneuver_choices": maneuver_learning["maneuver_choices"],
        "preparation_type": spell_learning["preparation_type"],
    }


def _apply_level_capstone_ability_scores(
    *,
    cls_key: str,
    new_level: int,
    ability_scores: dict,
) -> dict:
    next_scores = dict(ability_scores or {})
    if cls_key == "Barbarian" and new_level >= 20:
        for ability in ("str", "con"):
            next_scores[ability] = min(24, int(next_scores.get(ability, 10) or 10) + 4)
    return next_scores


def _resolve_subclass_choice(
    *,
    cls_key: str,
    old_level: int,
    new_level: int,
    current_subclass: str | None,
    subclass_choice: str | None,
) -> str | None:
    current = (current_subclass or "").strip()
    requested = (subclass_choice or "").strip()
    unlock_level = subclass_unlock_level(cls_key)
    unlocked_this_level = old_level < unlock_level <= new_level
    if not requested:
        if current:
            return current
        if unlocked_this_level and subclass_options_for_class(cls_key):
            raise CharacterLevelingError(
                400,
                f"{cls_key} must choose a subclass at level {unlock_level}.",
            )
        return None

    canonical = canonical_subclass_choice(cls_key, requested)
    if not canonical:
        raise CharacterLevelingError(400, f"{requested} is not a valid {cls_key} subclass choice.")
    if current and current.lower() != canonical.lower():
        raise CharacterLevelingError(400, f"{cls_key} subclass is already {current}.")

    if old_level < unlock_level and new_level < unlock_level:
        raise CharacterLevelingError(400, f"{cls_key} subclass choices unlock at level {unlock_level}.")

    return canonical


def _resolve_fighting_style_choice(
    *,
    cls_key: str,
    old_level: int,
    new_level: int,
    current_fighting_style: str | None,
    fighting_style_choice: str | None,
) -> str | None:
    current = (current_fighting_style or "").strip()
    requested = (fighting_style_choice or "").strip()
    style_config = FIGHTING_STYLE_CLASSES.get(cls_key)
    unlock_level = int(style_config.get("level", 0) or 0) if style_config else 0
    if not requested:
        if current:
            return current
        if style_config and old_level < unlock_level <= new_level:
            raise CharacterLevelingError(
                400,
                f"{cls_key} must choose a fighting style at level {unlock_level}.",
            )
        return None

    if not style_config:
        raise CharacterLevelingError(400, f"{cls_key} cannot choose a fighting style.")
    if new_level < unlock_level:
        raise CharacterLevelingError(
            400,
            f"{cls_key} fighting style choices unlock at level {style_config['level']}.",
        )
    if requested not in style_config.get("styles", []):
        raise CharacterLevelingError(400, f"{requested} is not a valid {cls_key} fighting style.")
    if current and current != requested:
        raise CharacterLevelingError(400, f"{cls_key} fighting style is already {current}.")

    return requested


def _battle_master_maneuvers_known_for_level(level: int) -> int:
    known = 0
    for threshold, count in sorted(BATTLE_MASTER_MANEUVERS_KNOWN_BY_LEVEL.items()):
        if level >= int(threshold):
            known = int(count)
    return known


def _advance_maneuver_choices(
    *,
    cls_key: str,
    old_level: int,
    new_level: int,
    subclass: str | None,
    current_resources: dict | None,
    maneuver_choices: list[str] | None,
) -> dict:
    requested = _clean_choices(maneuver_choices)
    resources = dict(current_resources or {})
    has_explicit_maneuver_list = "maneuvers_known" in resources or "maneuvers" in resources
    existing = _clean_choices(resources.get("maneuvers_known") or resources.get("maneuvers") or [])

    if cls_key != "Fighter" or (subclass or "").strip().lower() != "battle master":
        if requested:
            raise CharacterLevelingError(400, "Only Battle Master fighters can learn maneuvers.")
        return {"class_resources": resources, "maneuver_choices": []}

    required_total = _battle_master_maneuvers_known_for_level(new_level)
    required_new = max(0, required_total - len(existing))
    initial_maneuver_unlock = old_level < 3 <= new_level
    must_choose = required_new > 0 and (initial_maneuver_unlock or has_explicit_maneuver_list)
    if not requested:
        if must_choose:
            raise CharacterLevelingError(
                400,
                f"Level {new_level} Battle Master must choose {required_new} new maneuver(s).",
            )
        return {"class_resources": resources, "maneuver_choices": []}

    if cls_key != "Fighter" or (subclass or "").strip().lower() != "battle master":
        raise CharacterLevelingError(400, "Only Battle Master fighters can learn maneuvers.")

    _reject_duplicate_choices(requested, "maneuver_choices")
    invalid = [choice for choice in requested if choice not in BATTLE_MASTER_MANEUVERS]
    if invalid:
        raise CharacterLevelingError(400, f"Unknown Battle Master maneuver(s): {', '.join(invalid)}.")

    already_known = [choice for choice in requested if choice in existing]
    if already_known:
        raise CharacterLevelingError(400, f"Battle Master maneuver(s) already known: {', '.join(already_known)}.")

    if len(requested) != required_new:
        raise CharacterLevelingError(
            400,
            f"Level {new_level} Battle Master must choose {required_new} new maneuver(s); "
            f"selected {len(requested)}.",
        )

    resources["maneuvers_known"] = [*existing, *requested]
    return {"class_resources": resources, "maneuver_choices": requested}


def _advance_spell_slots(
    *,
    current_slots: dict | None,
    old_slots_max: dict | None,
    new_slots_max: dict | None,
) -> dict:
    next_slots = {
        slot_key: value
        for slot_key, value in (current_slots or {}).items()
        if slot_key in (new_slots_max or {})
    }
    old_max = old_slots_max or {}

    for slot_key, max_value in (new_slots_max or {}).items():
        current_value = next_slots.get(slot_key)
        comparable_old_max = old_max.get(slot_key, 0)
        if current_value is None:
            migrated_slot = _remaining_slots_from_removed_slot_level(
                current_slots=current_slots,
                old_slots_max=old_max,
                new_slots_max=new_slots_max,
            )
            if migrated_slot is None:
                current_value = 0
            else:
                current_value, comparable_old_max = migrated_slot
        gained = max(0, max_value - comparable_old_max)
        next_slots[slot_key] = min(max_value, current_value + gained)

    return next_slots


def _remaining_slots_from_removed_slot_level(
    *,
    current_slots: dict | None,
    old_slots_max: dict | None,
    new_slots_max: dict | None,
) -> tuple[int, int] | None:
    removed_keys = set((current_slots or {}).keys()) - set((new_slots_max or {}).keys())
    if len(removed_keys) != 1 or len(new_slots_max or {}) != 1:
        return None
    removed_key = next(iter(removed_keys))
    if removed_key not in (old_slots_max or {}):
        return None
    try:
        remaining = max(0, int((current_slots or {}).get(removed_key, 0) or 0))
        old_capacity = max(0, int((old_slots_max or {}).get(removed_key, 0) or 0))
        return remaining, old_capacity
    except (TypeError, ValueError):
        return None


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
            if new_default >= 999:
                next_resources[key] = new_default
                continue
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
    spell_replacements: list[dict] | None,
    available_class_spells: list | None,
    available_class_cantrips: list[str] | None,
) -> dict:
    preparation_type = SPELL_PREPARATION_TYPE.get(cls_key)
    requested_spells = _clean_choices(learned_spells)
    requested_cantrips = _clean_choices(learned_cantrips)
    requested_replacements = _clean_replacements(spell_replacements)
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

    if requested_replacements:
        if preparation_type != "known":
            raise CharacterLevelingError(
                400,
                f"{cls_key} cannot replace known spells during level-up.",
            )
        if len(requested_replacements) > 1:
            raise CharacterLevelingError(400, "Only one known spell replacement is allowed per level-up.")
        replacement_old_spells = {replacement["old_spell"] for replacement in requested_replacements}
        replacement_new_spells = {replacement["new_spell"] for replacement in requested_replacements}
        requested_spell_set = set(requested_spells)
        if replacement_old_spells & requested_spell_set:
            raise CharacterLevelingError(
                400,
                "A replaced spell cannot also be learned again in the same level-up.",
            )
        if replacement_new_spells & requested_spell_set:
            raise CharacterLevelingError(
                400,
                "Replacement spells cannot also be selected as learned spells.",
            )

    for replacement in requested_replacements:
        old_spell = replacement["old_spell"]
        new_spell = replacement["new_spell"]
        if old_spell == new_spell:
            raise CharacterLevelingError(400, "Replacement spell must be different from the old spell.")
        if old_spell not in known_set:
            raise CharacterLevelingError(400, f"Spell '{old_spell}' is not currently known.")
        if new_spell in known_set:
            raise CharacterLevelingError(400, f"Spell '{new_spell}' is already known.")
        _validate_leveled_class_spell(
            spell_name=new_spell,
            spell_levels=spell_levels,
            max_spell_level=max_spell_level,
        )
        next_known_spells = [
            new_spell if spell_name == old_spell else spell_name
            for spell_name in next_known_spells
        ]
        known_set.remove(old_spell)
        known_set.add(new_spell)

    for spell_name in requested_spells:
        if spell_name in known_set:
            raise CharacterLevelingError(400, f"Spell '{spell_name}' is already known.")
        _validate_leveled_class_spell(
            spell_name=spell_name,
            spell_levels=spell_levels,
            max_spell_level=max_spell_level,
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
        "spell_replacements": requested_replacements,
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


def _validate_leveled_class_spell(
    *,
    spell_name: str,
    spell_levels: dict[str, int | None],
    max_spell_level: int,
) -> None:
    spell_level = spell_levels.get(spell_name)
    if spell_level is None or spell_level <= 0:
        raise CharacterLevelingError(400, f"Spell '{spell_name}' is not a class leveled spell.")
    if max_spell_level <= 0 or spell_level > max_spell_level:
        raise CharacterLevelingError(
            400,
            f"Spell '{spell_name}' requires level {spell_level}; max allowed is {max_spell_level}.",
        )


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


def _clean_replacements(replacements: list[dict] | None) -> list[dict]:
    cleaned = []
    for replacement in replacements or []:
        if not isinstance(replacement, dict):
            raise CharacterLevelingError(400, "Spell replacements must be objects.")
        old_spell = str(replacement.get("old_spell", "")).strip()
        new_spell = str(replacement.get("new_spell", "")).strip()
        if not old_spell or not new_spell:
            raise CharacterLevelingError(400, "Spell replacements require old_spell and new_spell.")
        cleaned.append({"old_spell": old_spell, "new_spell": new_spell})
    return cleaned


def _reject_duplicate_choices(choices: list[str], label: str) -> None:
    if len(set(choices)) != len(choices):
        raise CharacterLevelingError(400, f"Duplicate choices are not allowed in {label}.")
