from __future__ import annotations

from typing import Any

from services.combat_tactical_service import get_cover_analysis


def parse_grid_position(value: Any) -> dict[str, int] | None:
    if isinstance(value, dict):
        try:
            return {"x": int(value["x"]), "y": int(value["y"])}
        except (KeyError, TypeError, ValueError):
            return None
    if isinstance(value, str):
        parts = value.strip().split("_")
        if len(parts) != 2:
            return None
        try:
            return {"x": int(parts[0]), "y": int(parts[1])}
        except ValueError:
            return None
    return None


def spell_aoe_template(spell: dict[str, Any] | None) -> str:
    text = " ".join(
        str((spell or {}).get(key) or "")
        for key in ("template", "shape", "name", "name_en", "desc", "description")
    ).lower()
    if "cone" in text or "锥" in text:
        return "cone"
    if "line" in text or "直线" in text:
        return "line"
    if "cube" in text or "立方" in text:
        return "cube"
    if (
        "aura" in text
        or "self" in text
        or "自身" in text
        or "以你为中心" in text
        or "内敌人" in text
        or "within " in text and " feet of you" in text
    ):
        return "aura"
    return "sphere"


def resolve_aoe_origin_position(
    *,
    spell: dict[str, Any] | None,
    positions: dict[str, Any],
    caster_id: str | None,
    aoe_center: Any = None,
) -> dict[str, int] | None:
    template = spell_aoe_template(spell)
    caster_position = positions.get(str(caster_id)) if caster_id is not None else None
    if template in {"cone", "line", "aura"}:
        return parse_grid_position(caster_position)
    return parse_grid_position(aoe_center)


def _cover_cells(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    cells = []
    for cell in analysis.get("cells") or []:
        if not isinstance(cell, dict):
            continue
        cells.append({
            "cell": cell.get("cell"),
            "terrain": cell.get("terrain"),
            "weight": cell.get("weight", 0),
        })
    return cells


def analyze_spell_save_cover(
    *,
    grid_data: dict[str, Any],
    positions: dict[str, Any],
    caster_id: str | None,
    target_id: str,
    spell: dict[str, Any] | None,
    save_ability: str | None,
    aoe_center: Any = None,
) -> dict[str, Any] | None:
    origin = resolve_aoe_origin_position(
        spell=spell,
        positions=positions,
        caster_id=caster_id,
        aoe_center=aoe_center,
    )
    target_position = parse_grid_position(positions.get(str(target_id)))
    if not grid_data or not origin or not target_position:
        return None

    analysis = get_cover_analysis(grid_data, origin, target_position)
    raw_bonus = int(analysis.get("bonus") or 0)
    blocks_target = bool(analysis.get("blocks_target"))
    bonus = raw_bonus if str(save_ability or "").lower() == "dex" and not blocks_target else 0
    if not blocks_target and bonus <= 0 and not analysis.get("cells"):
        return None

    return {
        "bonus": bonus,
        "raw_bonus": raw_bonus,
        "cells": _cover_cells(analysis),
        "blocks_target": blocks_target,
        "blocked_by": analysis.get("blocked_by") if blocks_target else None,
        "origin": origin,
        "applies_to": "dex_save" if bonus else "line_of_effect",
    }


def spell_save_cover_bonus(cover_detail: dict[str, Any] | None) -> int:
    if not cover_detail or cover_detail.get("blocks_target"):
        return 0
    try:
        return max(0, int(cover_detail.get("bonus") or 0))
    except (TypeError, ValueError):
        return 0
