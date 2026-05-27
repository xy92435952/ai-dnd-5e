from types import SimpleNamespace

import pytest

from models import Character
from services.combat_turn_limits_service import (
    _movement_squares_for_speed,
    _parse_speed,
    calculate_entity_turn_limits,
)


class FakeDb:
    def __init__(self, character=None):
        self.character = character

    async def get(self, model, entity_id):
        if model is Character:
            return self.character
        return None


def test_parse_speed_reads_numbers_from_strings():
    assert _parse_speed("40ft") == 40
    assert _parse_speed("speed 25 ft") == 25
    assert _parse_speed("unknown") == 30


def test_exhaustion_halves_or_removes_movement():
    assert _movement_squares_for_speed(30, exhaustion_level=0) == 6
    assert _movement_squares_for_speed(30, exhaustion_level=2) == 3
    assert _movement_squares_for_speed(30, exhaustion_level=5) == 0
    assert _movement_squares_for_speed(30, speed_zero=True) == 0


@pytest.mark.asyncio
async def test_calculate_entity_turn_limits_for_character_extra_attack():
    character = SimpleNamespace(
        derived={},
        char_class="Fighter",
        level=11,
        equipment={},
        condition_durations={},
    )

    attacks, movement = await calculate_entity_turn_limits(
        FakeDb(character),
        SimpleNamespace(game_state={}),
        "hero",
    )

    assert attacks == 3
    assert movement == 6


@pytest.mark.asyncio
async def test_calculate_entity_turn_limits_halves_character_speed_at_exhaustion_2():
    character = SimpleNamespace(
        derived={},
        char_class="Fighter",
        level=1,
        equipment={},
        condition_durations={"exhaustion_level": 2},
    )

    attacks, movement = await calculate_entity_turn_limits(
        FakeDb(character),
        SimpleNamespace(game_state={}),
        "hero",
    )

    assert attacks == 1
    assert movement == 3


@pytest.mark.asyncio
async def test_calculate_entity_turn_limits_zeroes_restrained_character_speed():
    character = SimpleNamespace(
        derived={},
        char_class="Fighter",
        level=1,
        equipment={},
        conditions=["restrained"],
        condition_durations={},
    )

    attacks, movement = await calculate_entity_turn_limits(
        FakeDb(character),
        SimpleNamespace(game_state={}),
        "hero",
    )

    assert attacks == 1
    assert movement == 0


@pytest.mark.asyncio
async def test_calculate_entity_turn_limits_for_enemy_speed_string():
    session = SimpleNamespace(game_state={"enemies": [{"id": "orc", "speed": "40ft"}]})

    attacks, movement = await calculate_entity_turn_limits(FakeDb(), session, "orc")

    assert attacks == 1
    assert movement == 8


@pytest.mark.asyncio
async def test_calculate_entity_turn_limits_uses_enemy_multiattack():
    session = SimpleNamespace(game_state={"enemies": [{"id": "bear", "speed": "40ft", "multiattack": 2}]})

    attacks, movement = await calculate_entity_turn_limits(FakeDb(), session, "bear")

    assert attacks == 2
    assert movement == 8


@pytest.mark.asyncio
async def test_calculate_entity_turn_limits_zeroes_enemy_speed_at_exhaustion_5():
    session = SimpleNamespace(game_state={
        "enemies": [{
            "id": "orc",
            "speed": "40ft",
            "condition_durations": {"exhaustion_level": 5},
        }],
    })

    attacks, movement = await calculate_entity_turn_limits(FakeDb(), session, "orc")

    assert attacks == 1
    assert movement == 0


@pytest.mark.asyncio
async def test_calculate_entity_turn_limits_zeroes_grappled_enemy_speed():
    session = SimpleNamespace(game_state={
        "enemies": [{
            "id": "orc",
            "speed": "40ft",
            "conditions": ["grappled"],
        }],
    })

    attacks, movement = await calculate_entity_turn_limits(FakeDb(), session, "orc")

    assert attacks == 1
    assert movement == 0
