import re
from typing import Any

from models import Character
from services.combat_service import CombatService
from services.dnd_rules import _normalize_class, get_exhaustion_level, has_speed_zero_condition

svc = CombatService()


async def calculate_entity_turn_limits(db, session, entity_id: str) -> tuple[int, int]:
    """计算实体的每回合攻击次数和移动格数。返回 (attacks_max, movement_max)。"""
    char = await db.get(Character, entity_id)
    if char:
        derived = char.derived or {}
        normalized_class = _normalize_class(char.char_class)
        level = char.level or 1
        attacks_max = svc.get_attack_count(derived, level, normalized_class)
        speed = 30
        if char.equipment:
            pass
        return attacks_max, _movement_squares_for_speed(
            speed,
            exhaustion_level=get_exhaustion_level(char),
            speed_zero=has_speed_zero_condition(char),
        )

    state = session.game_state or {}
    for enemy in state.get("enemies", []):
        if str(enemy.get("id")) == str(entity_id):
            speed = _parse_speed(enemy.get("speed", 30))
            return 1, _movement_squares_for_speed(
                max(speed, 20),
                exhaustion_level=get_exhaustion_level(enemy),
                speed_zero=has_speed_zero_condition(enemy),
            )

    return 1, 6


def _parse_speed(raw_speed: Any) -> int:
    if isinstance(raw_speed, str):
        match = re.search(r"(\d+)", raw_speed)
        return int(match.group(1)) if match else 30
    return int(raw_speed or 30)


def _movement_squares_for_speed(speed: int, *, exhaustion_level: int = 0, speed_zero: bool = False) -> int:
    if speed_zero:
        return 0
    if exhaustion_level >= 5:
        return 0
    if exhaustion_level >= 2:
        speed = speed // 2
    return max(0, speed // 5)
