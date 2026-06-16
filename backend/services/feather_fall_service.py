from __future__ import annotations

from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from services.dnd_rules import _normalize_class
from services.spell_service import SpellService


class FeatherFallError(ValueError):
    pass


FEATHER_FALL_NAMES = {
    "feather fall",
    "featherfall",
    "feather-fall",
    "\u8dcc\u843d\u4e4b\u7fbd",
    "\u5760\u843d\u4e4b\u7fbd",
    "\u7fbd\u843d\u672f",
}

FEATHER_FALL_CLASSES = {"Bard", "Sorcerer", "Wizard"}

FALL_DAMAGE_TYPES = {"fall", "falling"}
FALL_TEXT_TOKENS = {
    "fall",
    "falling",
    "fallen",
    "drop",
    "shaft",
    "pit",
    "chasm",
    "cliff",
    "ledge",
    "sinkhole",
    "\u8dcc\u843d",
    "\u5760\u843d",
    "\u6389\u843d",
    "\u5760\u4e0b",
    "\u843d\u7a74",
    "\u9677\u5751",
}


def is_fall_damage_event(event: dict[str, Any] | None) -> bool:
    """Return whether hazard/trap metadata represents a fall-damage trigger."""
    if not isinstance(event, dict):
        return False

    if any(_coerce_bool(event.get(key)) for key in (
        "is_fall",
        "fall",
        "falling",
        "fall_damage",
        "fall_trigger",
    )):
        return True

    if any(_positive_number(event.get(key)) for key in (
        "fall_distance",
        "fall_distance_ft",
        "fall_distance_feet",
        "height",
        "height_ft",
        "drop_distance",
        "drop_distance_ft",
    )):
        return True

    damage_type = _normalize_key(event.get("damage_type"))
    if damage_type in FALL_DAMAGE_TYPES:
        return True

    text_key = _event_text_key(event)
    if damage_type == "bludgeoning" and _contains_fall_token(text_key):
        return True
    return _contains_fall_token(text_key)


def character_knows_feather_fall(character: Any) -> bool:
    known = _character_spell_keys(character)
    return any(_normalize_spell_key(name) in known for name in FEATHER_FALL_NAMES)


def choose_feather_fall_slot(spell_slots: dict[str, Any] | None) -> tuple[str, int] | None:
    slots = dict(spell_slots or {})
    available = [
        (SpellService.slot_key(level), level)
        for level in range(1, 10)
        if _as_int(slots.get(SpellService.slot_key(level)), 0) > 0
    ]
    if not available:
        return None
    return min(available, key=lambda item: item[1])


def character_can_cast_feather_fall(
    character: Any,
    *,
    reaction_state: dict[str, Any] | None = None,
) -> bool:
    if not character:
        return False
    if _normalize_class(getattr(character, "char_class", "")) not in FEATHER_FALL_CLASSES:
        return False
    if reaction_state and reaction_state.get("reaction_used"):
        return False
    if not character_knows_feather_fall(character):
        return False
    return choose_feather_fall_slot(getattr(character, "spell_slots", None) or {}) is not None


def build_feather_fall_reaction_option(
    character: Any,
    fall_event: dict[str, Any] | None,
    *,
    targets: list[Any] | None = None,
    reaction_state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not is_fall_damage_event(fall_event):
        return None
    if not character_can_cast_feather_fall(character, reaction_state=reaction_state):
        return None
    slot = choose_feather_fall_slot(getattr(character, "spell_slots", None) or {})
    if not slot:
        return None
    slot_key, slot_level = slot
    damage = fall_damage_amount(fall_event)
    return {
        "id": "feather_fall",
        "name": "Feather Fall",
        "type": "feather_fall",
        "trigger": "fall_damage",
        "cost": f"{slot_key} spell slot + reaction",
        "slot_level": slot_key,
        "slot_level_number": slot_level,
        "slots_remaining": (getattr(character, "spell_slots", None) or {}).get(slot_key, 0),
        "damage_before": damage,
        "damage_after": 0,
        "damage_prevented": damage,
        "max_targets": 5,
        "target_ids": [_entity_id(target) for target in (targets or []) if _entity_id(target)],
    }


def resolve_feather_fall_reaction(
    *,
    caster: Any,
    fall_event: dict[str, Any],
    targets: list[Any] | None = None,
    reaction_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not is_fall_damage_event(fall_event):
        raise FeatherFallError("Feather Fall can only be used on fall damage.")
    if not character_knows_feather_fall(caster):
        raise FeatherFallError("Feather Fall is not known or prepared.")
    if _normalize_class(getattr(caster, "char_class", "")) not in FEATHER_FALL_CLASSES:
        raise FeatherFallError("This character cannot cast Feather Fall.")
    if reaction_state and reaction_state.get("reaction_used"):
        raise FeatherFallError("Reaction already used this turn.")

    spell_slots = dict(getattr(caster, "spell_slots", None) or {})
    slot = choose_feather_fall_slot(spell_slots)
    if not slot:
        raise FeatherFallError("No spell slot available for Feather Fall.")
    slot_key, slot_level = slot
    new_slots, slot_error = SpellService.consume_slot(spell_slots, slot_level)
    if slot_error:
        raise FeatherFallError(slot_error)

    target_list = list(targets or [])
    if len(target_list) > 5:
        raise FeatherFallError("Feather Fall can affect at most five creatures.")

    caster.spell_slots = new_slots
    _flag_json_modified(caster, "spell_slots")

    damage_before = fall_damage_amount(fall_event)
    result = {
        "type": "feather_fall",
        "trigger": "fall_damage",
        "spell_name": "Feather Fall",
        "caster_id": _entity_id(caster),
        "caster_name": getattr(caster, "name", None),
        "slot_level": slot_key,
        "slot_level_number": slot_level,
        "reaction_spent": True,
        "damage_before": damage_before,
        "damage_after": 0,
        "damage_prevented": damage_before,
        "target_ids": [_entity_id(target) for target in target_list if _entity_id(target)],
        "target_names": [_entity_name(target) for target in target_list if _entity_name(target)],
        "spell_slots": dict(new_slots),
    }
    if reaction_state is not None:
        reaction_state["reaction_used"] = True
        reaction_state["feather_fall"] = {
            key: value
            for key, value in result.items()
            if key not in {"spell_slots"}
        }
    return result


def fall_damage_amount(event: dict[str, Any] | None) -> int:
    if not isinstance(event, dict):
        return 0
    for key in ("final_damage", "damage_after_save", "damage", "rolled_damage"):
        if key in event:
            return max(0, _as_int(event.get(key), 0))
    return 0


def apply_feather_fall_damage_prevention(
    fall_event: dict[str, Any],
    feather_fall_result: dict[str, Any],
) -> dict[str, Any]:
    prevented = max(0, _as_int(feather_fall_result.get("damage_prevented"), 0))
    original = fall_damage_amount(fall_event)
    return {
        **dict(fall_event or {}),
        "damage": max(0, original - prevented),
        "final_damage": max(0, original - prevented),
        "feather_fall": dict(feather_fall_result or {}),
    }


def _character_spell_keys(character: Any) -> set[str]:
    spells = []
    for field in ("known_spells", "prepared_spells", "spellbook", "spells"):
        value = getattr(character, field, None)
        if isinstance(value, list):
            spells.extend(value)
    return {_normalize_spell_key(spell) for spell in spells}


def _normalize_spell_key(value: Any) -> str:
    return _normalize_key(value).replace("_", " ").replace("-", " ")


def _normalize_key(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _event_text_key(event: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "id",
        "name",
        "label",
        "description",
        "type",
        "kind",
        "category",
        "terrain",
        "trigger",
        "effect",
    ):
        value = event.get(key)
        if value is not None:
            parts.append(str(value))
    return _normalize_key(" ".join(parts))


def _contains_fall_token(text: str) -> bool:
    if not text:
        return False
    return any(token in text for token in FALL_TEXT_TOKENS)


def _positive_number(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _entity_id(entity: Any) -> str | None:
    if isinstance(entity, dict):
        value = entity.get("id") or entity.get("character_id")
    else:
        value = getattr(entity, "id", None)
    return str(value) if value not in (None, "") else None


def _entity_name(entity: Any) -> str | None:
    if isinstance(entity, dict):
        value = entity.get("name")
    else:
        value = getattr(entity, "name", None)
    return str(value) if value not in (None, "") else None


def _flag_json_modified(character: Any, field: str) -> None:
    try:
        flag_modified(character, field)
    except Exception:
        pass
