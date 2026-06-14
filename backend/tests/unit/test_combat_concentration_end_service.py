from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_end_concentration_for_character_clears_tracked_effects():
    from services.combat_concentration_effect_service import track_concentration_condition
    from services.combat_concentration_end_service import end_concentration_for_character

    character = SimpleNamespace(
        id="caster-1",
        name="Smoke Sentinel",
        concentration="Web",
    )
    webbed_enemy = {
        "id": "webbed-goblin",
        "name": "Webbed Goblin",
        "conditions": ["restrained"],
        "condition_durations": {"restrained": 600},
    }
    track_concentration_condition(
        webbed_enemy,
        "restrained",
        caster_id="caster-1",
        spell_name="Web",
        condition_preexisting=False,
    )
    session = SimpleNamespace(game_state={"enemies": [webbed_enemy]})

    result = await end_concentration_for_character(None, session, character)

    expected_updates = [{
        "target_id": "webbed-goblin",
        "target_name": "Webbed Goblin",
        "is_enemy": True,
        "removed_conditions": ["restrained"],
        "conditions": [],
        "condition_durations": {},
    }]
    assert character.concentration is None
    assert webbed_enemy["conditions"] == []
    assert webbed_enemy["condition_durations"] == {}
    assert "condition_sources" not in webbed_enemy
    assert result.ended is True
    assert result.spell_name == "Web"
    assert result.concentration_effect_updates == expected_updates
    assert result.actor_state == {
        "target_id": "caster-1",
        "entity_id": "caster-1",
        "target_name": "Smoke Sentinel",
        "concentration": None,
        "concentration_effect_updates": expected_updates,
    }
    assert result.to_response()["concentration_ended"] is True


@pytest.mark.asyncio
async def test_end_concentration_for_character_is_idempotent_without_active_spell():
    from services.combat_concentration_end_service import end_concentration_for_character

    character = SimpleNamespace(
        id="caster-1",
        name="Smoke Sentinel",
        concentration=None,
    )
    session = SimpleNamespace(game_state={"enemies": []})

    result = await end_concentration_for_character(None, session, character)

    assert character.concentration is None
    assert result.ended is False
    assert result.spell_name is None
    assert result.concentration_effect_updates == []
    assert result.actor_state == {
        "target_id": "caster-1",
        "entity_id": "caster-1",
        "target_name": "Smoke Sentinel",
        "concentration": None,
    }
