from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm.attributes import flag_modified


BARDIC_RESOURCE_KEY = "bardic_inspiration"


@dataclass
class BardicInspirationError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


def spend_bardic_inspiration(
    character: Any,
    *,
    bardic_roll: int | None,
    context: str,
) -> dict[str, Any]:
    """Spend one granted Bardic Inspiration die and return public roll metadata."""
    if bardic_roll is None:
        raise BardicInspirationError(400, "Bardic Inspiration requires bardic_inspiration_roll.")

    class_resources = dict(getattr(character, "class_resources", None) or {})
    inspiration = dict(class_resources.get(BARDIC_RESOURCE_KEY) or {})
    uses_remaining = _coerce_non_negative_int(inspiration.get("uses_remaining", 0))
    if uses_remaining <= 0:
        raise BardicInspirationError(400, "No Bardic Inspiration die available.")

    die = str(inspiration.get("die") or "d6").strip().lower()
    die_faces = _parse_die_faces(die)
    roll = _normalize_roll(bardic_roll, die_faces)

    inspiration["uses_remaining"] = uses_remaining - 1
    class_resources[BARDIC_RESOURCE_KEY] = inspiration
    character.class_resources = class_resources
    _flag_class_resources_modified(character)

    return {
        "type": "bardic_inspiration",
        "spent": True,
        "context": context,
        "die": die,
        "roll": roll,
        "uses_remaining": uses_remaining - 1,
        "source_character_id": inspiration.get("source_character_id"),
        "source_character_name": inspiration.get("source_character_name"),
    }


def apply_bardic_inspiration_to_skill_check(
    result: dict[str, Any],
    *,
    bardic_inspiration: dict[str, Any],
    dc: int,
) -> dict[str, Any]:
    total_before = int(result.get("total") or 0)
    total = total_before + int(bardic_inspiration["roll"])
    return {
        **result,
        "total": total,
        "success": total >= dc,
        "bardic_inspiration": {
            **bardic_inspiration,
            "total_before": total_before,
            "total_after": total,
        },
    }


def apply_bardic_inspiration_to_attack_roll(
    attack_roll: dict[str, Any],
    *,
    bardic_inspiration: dict[str, Any],
) -> dict[str, Any]:
    total_before = int(attack_roll.get("attack_total") or 0)
    attack_total = total_before + int(bardic_inspiration["roll"])
    target_ac = int(attack_roll.get("target_ac") or 0)
    is_crit = bool(attack_roll.get("is_crit"))
    is_fumble = bool(attack_roll.get("is_fumble"))
    hit = (not is_fumble) and (is_crit or attack_total >= target_ac)
    roll_modifiers = list(attack_roll.get("roll_modifiers") or [])
    roll_modifiers.append({
        "source": "bardic_inspiration",
        "value": int(bardic_inspiration["roll"]),
        "die": bardic_inspiration.get("die"),
    })
    return {
        **attack_roll,
        "attack_total": attack_total,
        "hit": hit,
        "roll_modifiers": roll_modifiers,
        "bardic_inspiration": {
            **bardic_inspiration,
            "total_before": total_before,
            "total_after": attack_total,
        },
    }


def get_bardic_inspiration_die(character_or_resources: Any = None) -> str | None:
    resources = getattr(character_or_resources, "class_resources", None)
    if resources is None and isinstance(character_or_resources, dict):
        resources = character_or_resources.get("class_resources") or character_or_resources
    inspiration = (resources or {}).get(BARDIC_RESOURCE_KEY) or {}
    if _coerce_non_negative_int(inspiration.get("uses_remaining", 0)) <= 0:
        return None
    die = str(inspiration.get("die") or "").strip().lower()
    return die if die else "d6"


def _parse_die_faces(die: str) -> int:
    if not die.startswith("d"):
        raise BardicInspirationError(400, "Invalid Bardic Inspiration die.")
    try:
        faces = int(die[1:])
    except (TypeError, ValueError) as exc:
        raise BardicInspirationError(400, "Invalid Bardic Inspiration die.") from exc
    if faces not in {6, 8, 10, 12}:
        raise BardicInspirationError(400, "Invalid Bardic Inspiration die.")
    return faces


def _normalize_roll(value: int | None, die_faces: int) -> int:
    try:
        roll = int(value)
    except (TypeError, ValueError) as exc:
        raise BardicInspirationError(400, "bardic_inspiration_roll must be an integer.") from exc
    if roll < 1 or roll > die_faces:
        raise BardicInspirationError(400, f"bardic_inspiration_roll must be between 1 and {die_faces}.")
    return roll


def _coerce_non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _flag_class_resources_modified(character: Any) -> None:
    try:
        flag_modified(character, "class_resources")
    except Exception:
        pass
