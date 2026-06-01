from typing import Any
import re

from fastapi import HTTPException

from models import Character
from services.combat_grid_service import chebyshev_distance
from services.dnd_rules import can_receive_ordinary_healing, ordinary_healing_block_reason
from services.session_access_service import assert_character_in_session


def collect_spell_target_ids(
    target_id: str | None,
    target_ids: list[str] | None,
    enemies: list[dict[str, Any]],
    *,
    is_aoe: bool,
) -> list[str]:
    raw_ids = target_ids if target_ids is not None else ([target_id] if target_id else [])
    if is_aoe and not raw_ids:
        raw_ids = [enemy["id"] for enemy in enemies if enemy.get("hp_current", 0) > 0]
    return list(raw_ids)


async def collect_spell_target_names(
    db,
    target_ids: list[str],
    enemies: list[dict[str, Any]],
    session=None,
) -> list[str]:
    target_names = []
    for target_id in target_ids:
        enemy = next((item for item in enemies if item["id"] == target_id), None)
        if enemy:
            target_names.append(enemy.get("name", "Enemy"))
            continue

        target_character = await db.get(Character, target_id)
        if target_character:
            if session is not None:
                await assert_character_in_session(target_character, session, db)
            target_names.append(target_character.name)
            continue

        raise HTTPException(400, f"Target does not exist: {target_id}")
    return target_names


async def validate_ordinary_healing_targets(
    db,
    target_ids: list[str],
    enemies: list[dict[str, Any]],
    session=None,
) -> None:
    """Reject ordinary healing when a target is already dead or immune to ordinary healing."""
    for target_id in target_ids:
        enemy = next((item for item in enemies if item["id"] == target_id), None)
        if enemy:
            _raise_if_healing_blocked(enemy)
            continue

        target_character = await db.get(Character, target_id)
        if not target_character:
            continue
        if session is not None:
            await assert_character_in_session(target_character, session, db)
        _raise_if_healing_blocked(target_character)


def _raise_if_healing_blocked(target: Any) -> None:
    if can_receive_ordinary_healing(target):
        return
    reason = ordinary_healing_block_reason(target)
    if reason == "dead":
        raise HTTPException(400, "Ordinary healing cannot revive a dead target")
    raise HTTPException(400, "Ordinary healing has no effect on undead or construct targets")


def parse_spell_range_ft(spell_range: int | str | None) -> int:
    if isinstance(spell_range, str):
        match = re.search(r"(\d+)", str(spell_range))
        return int(match.group(1)) if match else 0
    return int(spell_range or 0)


def parse_spell_range_tiles(spell_range: int | str | None) -> int:
    """Return spell range in grid tiles.

    Local spell data stores numeric ranges as grid tiles; imported/string ranges
    are usually authored in feet, so strings are converted to 5ft tiles.
    """
    if isinstance(spell_range, str):
        range_ft = parse_spell_range_ft(spell_range)
        return max(range_ft // 5, 1) if range_ft > 0 else 0
    return max(0, int(spell_range or 0))


def validate_spell_range(
    *,
    target_ids: list[str],
    positions: dict[str, dict[str, Any]],
    caster_id: str,
    spell_range_ft: int | str | None,
) -> None:
    spell_range_tiles = parse_spell_range_tiles(spell_range_ft)
    if spell_range_tiles <= 0 or not target_ids:
        return

    caster_position = positions.get(str(caster_id))
    for target_id in target_ids:
        target_position = positions.get(str(target_id))
        distance = chebyshev_distance(caster_position, target_position)
        if distance > spell_range_tiles:
            raise HTTPException(400, f"目标超出法术射程（距离{distance*5}ft，射程{spell_range_tiles*5}ft）")
