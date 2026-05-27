from __future__ import annotations

from typing import Any

from services.combat_damage_service import normalize_damage_type
from services.combat_evasion_service import has_evasion
from services.combat_spell_damage_type_service import resolve_spell_damage_type


SPELL_DAMAGE_COMPONENT_TYPES_BY_NAME: dict[str, list[str]] = {
    "flame strike": ["fire", "radiant"],
    "ice storm": ["bludgeoning", "cold"],
    "meteor swarm": ["fire", "bludgeoning"],
}


def _spell_names(spell_name: str | None, spell: dict[str, Any] | None) -> list[str]:
    names = [spell_name] if spell_name else []
    if spell:
        for key in ("name", "name_en"):
            value = spell.get(key)
            if value and value not in names:
                names.append(value)
    return names


def _explicit_damage_component_types(spell: dict[str, Any]) -> list[str]:
    components = spell.get("damage_components")
    if isinstance(components, list):
        types: list[str] = []
        for component in components:
            value = component.get("damage_type") if isinstance(component, dict) else component
            normalized = normalize_damage_type(value)
            if normalized:
                types.append(normalized)
        if types:
            return types

    explicit_types = spell.get("damage_types")
    if isinstance(explicit_types, str):
        normalized = normalize_damage_type(explicit_types)
        return [normalized] if normalized else []
    if isinstance(explicit_types, list):
        return [
            normalized
            for normalized in (normalize_damage_type(value) for value in explicit_types)
            if normalized
        ]
    return []


def resolve_spell_damage_type_sequence(
    spell_name: str | None,
    spell: dict[str, Any] | None,
) -> list[str]:
    """Return ordered canonical damage types for a spell's damage components."""
    spell = spell or {}
    explicit = _explicit_damage_component_types(spell)
    if explicit:
        return explicit

    for name in _spell_names(spell_name, spell):
        mapped = SPELL_DAMAGE_COMPONENT_TYPES_BY_NAME.get(str(name).strip().lower())
        if mapped:
            return mapped

    fallback = resolve_spell_damage_type(spell_name, spell)
    return [fallback] if fallback else []


def _roll_part_components(base_roll: dict[str, Any]) -> list[dict[str, Any]]:
    if not base_roll:
        return []

    parts = base_roll.get("parts")
    if isinstance(parts, list) and parts:
        components = []
        for part in parts:
            damage = max(0, int(part.get("total", 0) or 0))
            if damage <= 0:
                continue
            components.append({
                "damage": damage,
                "notation": part.get("notation"),
                "rolls": list(part.get("rolls") or []),
            })
        if components:
            return components

    damage = max(0, int(base_roll.get("total", 0) or 0))
    if damage <= 0:
        return []
    return [{
        "damage": damage,
        "notation": base_roll.get("notation"),
        "rolls": list(base_roll.get("rolls") or []),
    }]


def _extra_roll_components(extra_rolls: list[dict[str, Any]], damage_type: str | None) -> list[dict[str, Any]]:
    components = []
    for roll in extra_rolls or []:
        damage = max(0, int(roll.get("total", 0) or 0))
        if damage <= 0:
            continue
        components.append({
            "damage": damage,
            "damage_type": damage_type,
            "notation": roll.get("notation"),
            "rolls": list(roll.get("rolls") or []),
            "source": "upcast",
        })
    return components


def _normalize_component(component: dict[str, Any]) -> dict[str, Any] | None:
    damage = max(0, int(component.get("damage", component.get("total", 0)) or 0))
    if damage <= 0:
        return None
    damage_type = normalize_damage_type(component.get("damage_type"))
    normalized = {
        "damage": damage,
        "damage_type": damage_type or None,
    }
    for key in ("notation", "rolls", "source", "damage_before_save"):
        if key in component:
            normalized[key] = component[key]
    return normalized


def normalize_damage_components(components: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for component in components or []:
        item = _normalize_component(component)
        if item:
            normalized.append(item)
    return normalized


def resolve_spell_damage_components(
    spell_name: str | None,
    spell: dict[str, Any] | None,
    *,
    dice_detail: dict[str, Any] | None = None,
    total_damage: int | None = None,
) -> list[dict[str, Any]]:
    """Resolve rolled spell damage into typed components for per-type resistance."""
    spell = spell or {}
    dice_detail = dice_detail or {}
    existing = normalize_damage_components(dice_detail.get("damage_components"))
    if existing:
        return _reconcile_component_total(existing, total_damage)

    type_sequence = resolve_spell_damage_type_sequence(spell_name, spell)
    if not type_sequence:
        return []

    base_roll = dice_detail.get("base_roll") if isinstance(dice_detail, dict) else None
    base_components = _roll_part_components(base_roll or {})
    if not base_components:
        if total_damage is None:
            return []
        base_components = [{"damage": max(0, int(total_damage or 0))}]

    typed_components: list[dict[str, Any]] = []
    for index, component in enumerate(base_components):
        damage_type = type_sequence[min(index, len(type_sequence) - 1)]
        typed_components.append({
            **component,
            "damage_type": damage_type,
        })

    upcast_type = type_sequence[0] if type_sequence else None
    typed_components.extend(_extra_roll_components(dice_detail.get("extra_rolls") or [], upcast_type))
    return _reconcile_component_total(normalize_damage_components(typed_components), total_damage)


def _reconcile_component_total(
    components: list[dict[str, Any]],
    total_damage: int | None,
) -> list[dict[str, Any]]:
    if total_damage is None or not components:
        return components

    target_total = max(0, int(total_damage or 0))
    current_total = sum(component["damage"] for component in components)
    delta = target_total - current_total
    if delta == 0:
        return components

    reconciled = [dict(component) for component in components]
    if delta > 0:
        reconciled[-1]["damage"] += delta
        return reconciled

    remaining_delta = -delta
    for component in reversed(reconciled):
        reduction = min(component["damage"], remaining_delta)
        component["damage"] -= reduction
        remaining_delta -= reduction
        if remaining_delta <= 0:
            break
    return [component for component in reconciled if component["damage"] > 0]


def sum_damage_components(components: list[dict[str, Any]] | None) -> int:
    return sum(component["damage"] for component in normalize_damage_components(components))


def apply_save_to_damage_components(
    components: list[dict[str, Any]] | None,
    *,
    save_result: dict[str, Any] | None,
    save_ability: str | None,
    half_on_save: bool,
    target: dict[str, Any] | object | None,
) -> list[dict[str, Any]]:
    """Scale each component by save/evasion outcome before resistance is applied."""
    normalized = normalize_damage_components(components)
    if not normalized or not save_result:
        return normalized

    saved = bool(save_result.get("success"))
    evasion = save_ability == "dex" and half_on_save and has_evasion(target)
    if saved and (evasion or not half_on_save):
        scale = "zero"
    elif saved or evasion:
        scale = "half"
    else:
        return normalized

    scaled: list[dict[str, Any]] = []
    for component in normalized:
        damage_before_save = component["damage"]
        damage = 0 if scale == "zero" else damage_before_save // 2
        if damage <= 0:
            continue
        scaled.append({
            **component,
            "damage": damage,
            "damage_before_save": damage_before_save,
        })
    return scaled
