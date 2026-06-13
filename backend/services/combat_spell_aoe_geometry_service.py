from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any

from services.combat_spell_cover_service import parse_grid_position, spell_aoe_template


@dataclass(frozen=True)
class SpellAoeTargetFilter:
    target_ids: list[str]
    geometry_applied: bool
    excluded_ids: list[str]


def filter_spell_aoe_targets(
    *,
    spell: dict[str, Any] | None,
    target_ids: list[str] | None,
    positions: dict[str, Any] | None,
    caster_id: str | None,
    aoe_center: Any = None,
) -> SpellAoeTargetFilter:
    ids = [str(target_id) for target_id in (target_ids or []) if target_id is not None]
    if not ids or not (spell or {}).get("aoe"):
        return SpellAoeTargetFilter(ids, False, [])

    positions = positions or {}
    if not positions:
        return SpellAoeTargetFilter(ids, False, [])

    template = spell_aoe_template(spell)
    radius = spell_aoe_radius_tiles(spell, template=template)
    if radius <= 0:
        return SpellAoeTargetFilter(ids, False, [])

    origin = _template_origin(
        template=template,
        positions=positions,
        caster_id=caster_id,
        aoe_center=aoe_center,
    )
    anchor = _template_anchor(
        template=template,
        positions=positions,
        caster_id=caster_id,
        aoe_center=aoe_center,
    )
    if origin is None or anchor is None:
        return SpellAoeTargetFilter(ids, False, [])

    kept: list[str] = []
    excluded: list[str] = []
    for target_id in ids:
        target_position = parse_grid_position(positions.get(str(target_id)))
        if target_position and _point_in_spell_template(
            target_position=target_position,
            origin=origin,
            anchor=anchor,
            template=template,
            radius=radius,
        ):
            kept.append(target_id)
        else:
            excluded.append(target_id)

    return SpellAoeTargetFilter(kept, True, excluded)


def filter_spell_aoe_target_ids(
    *,
    spell: dict[str, Any] | None,
    target_ids: list[str] | None,
    positions: dict[str, Any] | None,
    caster_id: str | None,
    aoe_center: Any = None,
) -> list[str]:
    return filter_spell_aoe_targets(
        spell=spell,
        target_ids=target_ids,
        positions=positions,
        caster_id=caster_id,
        aoe_center=aoe_center,
    ).target_ids


def spell_aoe_radius_tiles(spell: dict[str, Any] | None, *, template: str | None = None) -> int:
    spell = spell or {}
    explicit_tiles = _first_number(
        spell,
        "aoe_radius_tiles",
        "area_radius_tiles",
        "radius_tiles",
        "length_tiles",
        "size_tiles",
    )
    if explicit_tiles is not None:
        return max(1, int(math.ceil(explicit_tiles)))

    explicit_ft = _first_number(
        spell,
        "aoe_radius_ft",
        "area_radius_ft",
        "radius_ft",
        "length_ft",
        "size_ft",
        "area_range_ft",
    )
    if explicit_ft is not None:
        return _feet_to_tiles(explicit_ft)

    distances = _distance_feet_from_spell_text(spell)
    if distances:
        return _feet_to_tiles(max(distances))

    if template == "aura":
        fallback_range = _number_or_none(spell.get("range"))
        if fallback_range is not None:
            return max(1, int(math.ceil(fallback_range)))

    fallback = _number_or_none(spell.get("range"))
    return max(1, int(math.ceil(fallback or 0))) if fallback else 0


def _template_origin(
    *,
    template: str,
    positions: dict[str, Any],
    caster_id: str | None,
    aoe_center: Any,
) -> dict[str, int] | None:
    if template in {"cone", "line", "aura"}:
        return parse_grid_position(positions.get(str(caster_id))) if caster_id is not None else None
    return parse_grid_position(aoe_center)


def _template_anchor(
    *,
    template: str,
    positions: dict[str, Any],
    caster_id: str | None,
    aoe_center: Any,
) -> dict[str, int] | None:
    if template in {"cone", "line"}:
        return parse_grid_position(aoe_center)
    if template == "aura":
        return parse_grid_position(positions.get(str(caster_id))) if caster_id is not None else None
    return parse_grid_position(aoe_center)


def _point_in_spell_template(
    *,
    target_position: dict[str, int],
    origin: dict[str, int],
    anchor: dict[str, int],
    template: str,
    radius: int,
) -> bool:
    dx = int(target_position["x"]) - int(origin["x"])
    dy = int(target_position["y"]) - int(origin["y"])

    if template == "line":
        return _point_on_line_template(dx, dy, _template_direction(origin, anchor), radius)
    if template == "cone":
        return _point_in_cone_template(dx, dy, _template_direction(origin, anchor), radius)
    if template == "cube":
        half_size = max(0, int(radius) // 2)
        return abs(dx) <= half_size and abs(dy) <= half_size
    return max(abs(dx), abs(dy)) <= radius


def _template_direction(
    origin: dict[str, int],
    anchor: dict[str, int],
) -> tuple[int, int]:
    return (
        _sign(int(anchor["x"]) - int(origin["x"])),
        _sign(int(anchor["y"]) - int(origin["y"])),
    )


def _point_on_line_template(
    dx: int,
    dy: int,
    direction: tuple[int, int],
    range_tiles: int,
) -> bool:
    step_x, step_y = direction
    if step_x == 0 and step_y == 0:
        return False
    if step_x == 0:
        return dx == 0 and _same_direction(dy, step_y) and abs(dy) <= range_tiles
    if step_y == 0:
        return dy == 0 and _same_direction(dx, step_x) and abs(dx) <= range_tiles
    return (
        abs(dx) == abs(dy)
        and _same_direction(dx, step_x)
        and _same_direction(dy, step_y)
        and abs(dx) <= range_tiles
    )


def _point_in_cone_template(
    dx: int,
    dy: int,
    direction: tuple[int, int],
    range_tiles: int,
) -> bool:
    distance = max(abs(dx), abs(dy))
    if distance <= 0 or distance > range_tiles:
        return False

    dir_x, dir_y = direction
    magnitude = math.hypot(dx, dy)
    dir_magnitude = math.hypot(dir_x, dir_y)
    if not magnitude or not dir_magnitude:
        return False
    cosine = ((dx * dir_x) + (dy * dir_y)) / (magnitude * dir_magnitude)
    return cosine >= math.cos(math.radians(45)) - 1e-9


def _same_direction(value: int, direction: int) -> bool:
    return direction == 0 or (value != 0 and _sign(value) == direction)


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)


def _feet_to_tiles(feet: float) -> int:
    return max(1, int(math.ceil(float(feet) / 5)))


def _distance_feet_from_spell_text(spell: dict[str, Any]) -> list[int]:
    text = " ".join(
        str(spell.get(key) or "")
        for key in ("area", "targeting", "template", "shape", "name", "name_en", "desc", "description")
    )
    return [
        int(match.group(1))
        for match in re.finditer(r"(\d+)\s*(?:ft\.?|feet|foot|尺)", text, flags=re.IGNORECASE)
    ]


def _first_number(spell: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _number_or_none(spell.get(key))
        if value is not None:
            return value
    return None


def _number_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
