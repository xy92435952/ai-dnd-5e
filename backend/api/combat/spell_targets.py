"""
api.combat.spell_targets — target selection and range checks for spell endpoints.
"""
from typing import Any
import re

from fastapi import HTTPException

from api.combat._shared import _chebyshev_dist
from models import Character


def collect_spell_target_ids(
    target_id: str | None,
    target_ids: list[str] | None,
    enemies: list[dict[str, Any]],
    *,
    is_aoe: bool,
) -> list[str]:
    raw_ids = target_ids if target_ids is not None else ([target_id] if target_id else [])
    if is_aoe and not raw_ids:
        raw_ids = [e["id"] for e in enemies if e.get("hp_current", 0) > 0]
    return list(raw_ids)


async def collect_spell_target_names(
    db,
    target_ids: list[str],
    enemies: list[dict[str, Any]],
) -> list[str]:
    target_names = []
    for target_id in target_ids:
        enemy = next((en for en in enemies if en["id"] == target_id), None)
        if enemy:
            target_names.append(enemy["name"])
            continue

        target_char = await db.get(Character, target_id)
        if target_char:
            target_names.append(target_char.name)
    return target_names


def parse_spell_range_ft(spell_range: int | str | None) -> int:
    if isinstance(spell_range, str):
        match = re.search(r"(\d+)", str(spell_range))
        return int(match.group(1)) if match else 0
    return int(spell_range or 0)


def validate_spell_range(
    *,
    target_ids: list[str],
    positions: dict[str, dict[str, Any]],
    caster_id: str,
    spell_range_ft: int | str | None,
) -> None:
    parsed_range = parse_spell_range_ft(spell_range_ft)
    if parsed_range <= 0 or not target_ids:
        return

    caster_pos = positions.get(str(caster_id))
    spell_range_tiles = max(parsed_range // 5, 1)
    for target_id in target_ids:
        target_pos = positions.get(str(target_id))
        distance = _chebyshev_dist(caster_pos, target_pos)
        if distance > spell_range_tiles:
            raise HTTPException(400, f"目标超出法术射程（距离{distance*5}ft，射程{parsed_range}ft）")
