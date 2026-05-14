from types import SimpleNamespace

import pytest

from models import Character
from services.combat_turn_limits_service import (
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


@pytest.mark.asyncio
async def test_calculate_entity_turn_limits_for_character_extra_attack():
    character = SimpleNamespace(
        derived={},
        char_class="Fighter",
        level=11,
        equipment={},
    )

    attacks, movement = await calculate_entity_turn_limits(
        FakeDb(character),
        SimpleNamespace(game_state={}),
        "hero",
    )

    assert attacks == 3
    assert movement == 6


@pytest.mark.asyncio
async def test_calculate_entity_turn_limits_for_enemy_speed_string():
    session = SimpleNamespace(game_state={"enemies": [{"id": "orc", "speed": "40ft"}]})

    attacks, movement = await calculate_entity_turn_limits(FakeDb(), session, "orc")

    assert attacks == 1
    assert movement == 8
