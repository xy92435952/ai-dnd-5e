from types import SimpleNamespace

import pytest
from fastapi import HTTPException


class FakeDb:
    def __init__(self, character=None):
        self.character = character

    async def get(self, *_args):
        return self.character


@pytest.mark.asyncio
async def test_apply_stand_up_for_moving_enemy_removes_prone_and_updates_state(monkeypatch):
    from api.combat.movement import _apply_stand_up_for_moving_entity

    monkeypatch.setattr("api.combat.movement.flag_modified", lambda *_args: None)

    session = SimpleNamespace(game_state={
        "enemies": [{
            "id": "goblin-1",
            "conditions": ["倒地", "hexed"],
        }],
    })

    result = await _apply_stand_up_for_moving_entity(
        FakeDb(),
        session,
        "goblin-1",
        {"movement_used": 0, "movement_max": 6},
    )

    assert result.stood_up is True
    assert result.turn_state["movement_used"] == 3
    assert session.game_state["enemies"][0]["conditions"] == ["hexed"]


@pytest.mark.asyncio
async def test_apply_stand_up_for_moving_character_removes_prone_alias():
    from api.combat.movement import _apply_stand_up_for_moving_entity

    character = SimpleNamespace(conditions=["prone", "blessed"])
    result = await _apply_stand_up_for_moving_entity(
        FakeDb(character),
        SimpleNamespace(game_state={}),
        "hero-1",
        {"movement_used": 1, "movement_max": 6},
    )

    assert result.stood_up is True
    assert result.turn_state["movement_used"] == 4
    assert character.conditions == ["blessed"]


@pytest.mark.asyncio
async def test_apply_stand_up_for_moving_entity_raises_http_error_when_too_slow():
    from api.combat.movement import _apply_stand_up_for_moving_entity

    character = SimpleNamespace(conditions=["prone"])

    with pytest.raises(HTTPException) as exc:
        await _apply_stand_up_for_moving_entity(
            FakeDb(character),
            SimpleNamespace(game_state={}),
            "hero-1",
            {"movement_used": 6, "movement_max": 6},
        )

    assert exc.value.status_code == 400
