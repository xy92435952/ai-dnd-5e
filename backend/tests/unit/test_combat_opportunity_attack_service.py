from types import SimpleNamespace

import pytest


class FakeDb:
    def __init__(self, characters=None):
        self.characters = characters or {}

    async def get(self, _model, entity_id):
        return self.characters.get(str(entity_id))

    def add(self, _item):
        pass


def _combat():
    return SimpleNamespace(turn_states={}, entity_positions={})


def _session(enemies):
    return SimpleNamespace(
        id="sess-1",
        player_character_id="hero-1",
        game_state={"enemies": enemies},
    )


@pytest.mark.asyncio
async def test_incapacitated_enemy_cannot_make_opportunity_attack(monkeypatch):
    from services import combat_opportunity_attack_service as opportunity

    def fail_if_called(**_kwargs):
        raise AssertionError("incapacitated enemy should not attack")

    monkeypatch.setattr(opportunity.svc, "resolve_melee_attack", fail_if_called)

    enemies = [{
        "id": "goblin-1",
        "name": "Goblin",
        "hp_current": 7,
        "conditions": ["stunned"],
        "derived": {"attack_bonus": 4, "hp_max": 7},
    }]
    moving_char = SimpleNamespace(
        id="hero-1",
        name="Hero",
        hp_current=12,
        conditions=[],
        derived={"ac": 14, "hp_max": 12},
    )

    results = await opportunity.resolve_opportunity_attacks(
        FakeDb({"hero-1": moving_char}),
        session=_session(enemies),
        combat=_combat(),
        moving_id="hero-1",
        old_pos={"x": 5, "y": 5},
        new_pos={"x": 8, "y": 5},
        positions={
            "hero-1": {"x": 5, "y": 5},
            "goblin-1": {"x": 6, "y": 5},
        },
    )

    assert results == []
