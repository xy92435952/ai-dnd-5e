from dataclasses import dataclass

from services.dnd_rules import CASTER_TYPE, SPELL_PREPARATION_TYPE, _normalize_class


@dataclass
class CharacterSpellError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


def build_prepared_spells_update(
    *,
    known_spells: list[str] | None,
    requested_spells: list[str],
    level: int,
    derived: dict | None,
    char_class: str | None = None,
    available_class_spells: list[str] | None = None,
) -> dict:
    cls_key = _normalize_class(char_class) if char_class else None
    preparation_type = SPELL_PREPARATION_TYPE.get(cls_key) if cls_key else None
    known = set(known_spells or [])
    requested = list(requested_spells)

    if preparation_type == "known":
        if set(requested) != known or len(requested) != len(known):
            raise CharacterSpellError(400, "Known-spell casters do not prepare a daily subset")
        return {
            "prepared_spells": list(known_spells or []),
            "max_prepared": len(known),
            "preparation_type": preparation_type,
        }

    allowed_spells = known
    if preparation_type == "prepared" and available_class_spells is not None:
        allowed_spells = set(available_class_spells)

    for spell in requested:
        if spell not in allowed_spells:
            source = "class spell list" if preparation_type == "prepared" else "known spell list"
            raise CharacterSpellError(400, f"Spell '{spell}' is not in the character's {source}")

    derived_data = derived or {}
    modifiers = derived_data.get("ability_modifiers", {})
    spell_ability = derived_data.get("spell_ability")
    spell_modifier = modifiers.get(spell_ability, 0) if spell_ability else 0
    max_prepared = _max_prepared_spells(
        level=level,
        spell_modifier=spell_modifier,
        cls_key=cls_key,
        preparation_type=preparation_type,
    )

    if len(requested) > max_prepared:
        raise CharacterSpellError(
            400,
            f"Prepared spell limit is {max_prepared} "
            f"(level {level}, modifier {spell_modifier}); selected {len(requested)}.",
        )

    return {
        "prepared_spells": requested,
        "max_prepared": max_prepared,
        "preparation_type": preparation_type or "spellbook",
    }


def _max_prepared_spells(
    *,
    level: int,
    spell_modifier: int,
    cls_key: str | None,
    preparation_type: str | None,
) -> int:
    caster_type = CASTER_TYPE.get(cls_key) if cls_key else None
    if preparation_type == "prepared" and caster_type == "half":
        return max(1, (level // 2) + spell_modifier)
    return max(1, level + spell_modifier)
