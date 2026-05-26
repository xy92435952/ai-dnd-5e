from __future__ import annotations

from typing import Any

from services.dnd_rules import _normalize_class


_HALF_ON_SAVE_HINTS = (
    "成功减半",
    "成功受一半",
    "成功只受",
    "成功减半",
    "half damage",
    "half as much",
    "half on save",
)


def has_evasion(target: dict[str, Any] | object | None) -> bool:
    """Return whether a target has the 5e Evasion feature."""
    if target is None:
        return False

    if isinstance(target, dict):
        char_class = target.get("char_class") or target.get("class")
        level = target.get("level", 1)
        derived = target.get("derived") or {}
    else:
        char_class = getattr(target, "char_class", None)
        level = getattr(target, "level", 1)
        derived = getattr(target, "derived", None) or {}

    try:
        level = int(level or 1)
    except (TypeError, ValueError):
        level = 1

    subclass_effects = derived.get("subclass_effects", {})
    if subclass_effects.get("evasion"):
        return True

    class_key = _normalize_class(char_class or "")
    return class_key in {"Rogue", "Monk"} and level >= 7


def resolve_save_damage(
    base_damage: int,
    *,
    save_result: dict[str, Any] | None,
    save_ability: str | None,
    half_on_save: bool = True,
    target: dict[str, Any] | object | None = None,
) -> dict[str, Any]:
    """Apply save-based damage reduction, including Rogue/Monk Evasion."""
    damage = max(0, int(base_damage or 0))
    if not save_result:
        return {
            "damage": damage,
            "evasion_applied": False,
            "evasion_failed_half": False,
        }

    saved = bool(save_result.get("success"))
    evasion = save_ability == "dex" and half_on_save and has_evasion(target)
    evasion_failed_half = False

    if saved:
        damage = 0 if evasion else (damage // 2 if half_on_save else 0)
    elif evasion:
        damage = damage // 2
        evasion_failed_half = True

    return {
        "damage": damage,
        "evasion_applied": evasion and saved,
        "evasion_failed_half": evasion_failed_half,
    }


def spell_half_on_save(spell: dict[str, Any] | None, *, default: bool = False) -> bool:
    """Infer whether a spell deals half damage on a successful save."""
    if not spell:
        return default
    if "half_on_save" in spell:
        return bool(spell.get("half_on_save"))
    desc = str(spell.get("desc") or "").lower()
    return any(hint.lower() in desc for hint in _HALF_ON_SAVE_HINTS)
