from dataclasses import dataclass

from services.dnd_rules import (
    SPELLCASTER_CLASSES,
    STARTING_SPELLS_COUNT,
    _normalize_class,
    get_cantrips_count,
)
from services.subclass_spell_service import available_spells_with_subclass_bonus


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


@dataclass
class CharacterStartingSpellError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


def validate_starting_spell_choices(
    *,
    spell_service,
    char_class: str,
    subclass: str | None,
    level: int,
    derived: dict | None,
    cantrips: list[str] | None,
    known_spells: list[str] | None,
) -> dict:
    cls_key = _normalize_class(char_class)
    requested_cantrips = _clean_choices(cantrips)
    requested_spells = _clean_choices(known_spells)

    if cls_key not in SPELLCASTER_CLASSES:
        if requested_cantrips or requested_spells:
            raise CharacterStartingSpellError(400, f"{cls_key} does not choose starting spells.")
        return {"cantrips": [], "known_spells": []}

    _reject_duplicate_choices(requested_cantrips, "cantrips")
    _reject_duplicate_choices(requested_spells, "known_spells")

    expected_cantrips = get_cantrips_count(cls_key, level)
    expected_spells = STARTING_SPELLS_COUNT.get(cls_key, 0)
    if len(requested_cantrips) != expected_cantrips:
        raise CharacterStartingSpellError(
            400,
            f"{cls_key} requires {expected_cantrips} starting cantrips; selected {len(requested_cantrips)}.",
        )
    if len(requested_spells) != expected_spells:
        raise CharacterStartingSpellError(
            400,
            f"{cls_key} requires {expected_spells} starting spells; selected {len(requested_spells)}.",
        )

    available_cantrips = {
        spell.get("name")
        for spell in spell_service.get_cantrips_for_class(cls_key)
        if spell.get("name")
    }
    for cantrip in requested_cantrips:
        if cantrip not in available_cantrips:
            raise CharacterStartingSpellError(400, f"Cantrip '{cantrip}' is not a {cls_key} cantrip.")

    max_spell_level = _max_leveled_spell_rank((derived or {}).get("spell_slots_max", {}))
    available_spell_levels = {
        spell.get("name"): int(spell.get("level", 0) or 0)
        for spell in available_spells_with_subclass_bonus(
            spell_service,
            cls_key,
            subclass,
            level=level,
        )
        if spell.get("name")
    }
    for spell_name in requested_spells:
        spell_level = available_spell_levels.get(spell_name)
        if spell_level is None or spell_level <= 0:
            raise CharacterStartingSpellError(400, f"Spell '{spell_name}' is not a {cls_key} leveled spell.")
        if max_spell_level <= 0 or spell_level > max_spell_level:
            raise CharacterStartingSpellError(
                400,
                f"Spell '{spell_name}' requires level {spell_level}; max allowed is {max_spell_level}.",
            )

    return {
        "cantrips": requested_cantrips,
        "known_spells": requested_spells,
    }


def _clean_choices(choices: list[str] | None) -> list[str]:
    return [str(choice).strip() for choice in choices or [] if str(choice).strip()]


def _reject_duplicate_choices(choices: list[str], label: str) -> None:
    if len(set(choices)) != len(choices):
        raise CharacterStartingSpellError(400, f"Duplicate choices are not allowed in {label}.")


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
