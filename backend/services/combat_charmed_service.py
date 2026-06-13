from __future__ import annotations

from typing import Any

from services.dnd_rules import normalize_condition, normalize_conditions


CHARMED_ATTACK_ERROR = "Cannot attack the creature that charmed you"
CHARMED_HARMFUL_SPELL_ERROR = "Cannot target the creature that charmed you with a harmful spell"


def is_charmed_by_target(
    conditions: list[str] | None,
    condition_durations: dict[str, Any] | None,
    target_id: str | None,
) -> bool:
    """Return True when a charmed actor is trying to attack its recorded charmer."""
    if not target_id:
        return False
    if normalize_condition("charmed") not in normalize_conditions(conditions or []):
        return False
    return str(target_id) in charmed_source_ids(condition_durations or {})


def charmed_harmful_spell_target_id(
    conditions: list[str] | None,
    condition_durations: dict[str, Any] | None,
    *,
    spell_name: str,
    spell: dict[str, Any],
    target_ids: list[str] | tuple[str, ...] | set[str] | None,
) -> str | None:
    """Return the blocked charmer id when a harmful spell targets the charmer."""
    if not spell_is_harmful_to_target(spell_name, spell):
        return None
    if normalize_condition("charmed") not in normalize_conditions(conditions or []):
        return None

    source_ids = charmed_source_ids(condition_durations or {})
    if not source_ids:
        return None

    for target_id in target_ids or []:
        if str(target_id) in source_ids:
            return str(target_id)
    return None


def spell_is_harmful_to_target(spell_name: str, spell: dict[str, Any] | None) -> bool:
    if not spell:
        return False

    spell_type = str(spell.get("type") or "").strip().lower()
    if spell_type in {"damage", "control", "debuff", "harmful"}:
        return True
    if spell_type == "heal":
        return False

    for key in (
        "damage",
        "damage_dice",
        "damageDice",
        "damage_formula",
        "damageFormula",
        "save",
        "saving_throw",
        "save_ability",
        "condition_on_failed_save",
        "conditions_on_failed_save",
        "condition",
        "conditions",
    ):
        if spell.get(key):
            return True

    text = " ".join(
        str(value or "")
        for value in (
            spell_name,
            spell.get("name"),
            spell.get("name_en"),
            spell.get("desc"),
            spell.get("description"),
        )
    ).lower()
    harmful_terms = (
        "hex",
        "hunter's mark",
        "hunters mark",
        "curse",
        "mark target",
        "disadvantage",
        "restrained",
        "paralyzed",
        "stunned",
        "frightened",
        "poisoned",
        "blinded",
        "deafened",
        "petrified",
        "unconscious",
        "诅咒",
        "标记目标",
        "劣势",
        "束缚",
        "麻痹",
        "震慑",
        "恐慌",
        "中毒",
        "目盲",
        "耳聋",
        "石化",
        "昏迷",
        "伤害",
    )
    return any(term in text for term in harmful_terms)


def charmed_source_ids(condition_durations: dict[str, Any]) -> set[str]:
    entries: list[Any] = [_duration_entry(condition_durations, "charmed")]
    for key in (
        "charmed_source",
        "charmed_source_id",
        "charmed_source_ids",
        "charmer",
        "charmer_id",
        "charmer_ids",
    ):
        if key in condition_durations:
            entries.append(condition_durations.get(key))

    ids: set[str] = set()
    for entry in entries:
        ids.update(_source_ids_from_entry(entry))
    return ids


def _duration_entry(condition_durations: dict[str, Any], condition: str) -> Any:
    canonical = normalize_condition(condition)
    for key, value in condition_durations.items():
        if normalize_condition(str(key)) == canonical:
            return value
    return None


def _source_ids_from_entry(entry: Any) -> set[str]:
    if entry is None:
        return set()
    if isinstance(entry, (list, tuple, set)):
        ids: set[str] = set()
        for item in entry:
            ids.update(_source_ids_from_entry(item))
        return ids
    if isinstance(entry, dict):
        ids: set[str] = set()
        for key in ("source_ids", "sourceIds", "charmer_ids", "charmerIds", "caster_ids", "casterIds"):
            ids.update(_source_ids_from_entry(entry.get(key)))
        for key in (
            "source_id",
            "sourceId",
            "source",
            "charmer_id",
            "charmerId",
            "charmer",
            "caster_id",
            "casterId",
            "source_entity_id",
            "sourceEntityId",
        ):
            value = entry.get(key)
            if value is not None and not isinstance(value, dict):
                ids.add(str(value))
        return ids
    return {str(entry)}
