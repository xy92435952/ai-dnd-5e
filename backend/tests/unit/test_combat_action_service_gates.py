from types import SimpleNamespace

import pytest


class FakeDb:
    def __init__(self, actor):
        self.actor = actor

    async def get(self, _model, entity_id):
        return self.actor if str(entity_id) in {"actor-1", "player-1"} else None


def _actor(**overrides):
    defaults = {
        "id": "actor-1",
        "name": "Actor",
        "char_class": "Fighter",
        "level": 5,
        "hp_current": 20,
        "conditions": [],
        "derived": {
            "proficiency_bonus": 3,
            "ability_modifiers": {"str": 4, "dex": 2},
            "subclass_effects": {
                "battle_master": True,
                "maneuvers": ["trip"],
                "superiority_die": "d8",
            },
        },
        "proficient_skills": ["Athletics"],
        "class_resources": {"superiority_dice_remaining": 1},
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _session():
    return SimpleNamespace(
        id="sess-1",
        combat_active=True,
        player_character_id="player-1",
        game_state={
            "enemies": [{
                "id": "goblin-1",
                "name": "Goblin",
                "conditions": [],
                "derived": {"ability_modifiers": {"str": 0, "dex": 2}, "proficiency_bonus": 2},
                "ability_scores": {"str": 10, "wis": 10},
            }],
        },
    )


def _combat(actor_id="actor-1"):
    return SimpleNamespace(
        current_turn_index=0,
        turn_order=[{"character_id": actor_id}],
        turn_states={actor_id: {"action_used": False, "attacks_made": 0}},
        entity_positions={actor_id: {"x": 5, "y": 5}, "goblin-1": {"x": 6, "y": 5}},
    )


@pytest.mark.asyncio
async def test_grapple_service_rejects_incapacitated_actor():
    from services.combat_grapple_service import CombatGrappleError, resolve_grapple_shove

    actor = _actor(id="player-1", conditions=["paralyzed"])

    with pytest.raises(CombatGrappleError) as exc:
        await resolve_grapple_shove(
            FakeDb(actor),
            session=_session(),
            combat=_combat("player-1"),
            action_type="grapple",
            target_id="goblin-1",
            narrate_action_func=lambda **_kwargs: None,
        )

    assert exc.value.status_code == 400
    assert "paralyzed" in exc.value.detail


@pytest.mark.asyncio
async def test_maneuver_service_rejects_incapacitated_actor():
    from services.combat_maneuver_service import CombatManeuverError, resolve_maneuver

    actor = _actor(conditions=["stunned"])

    with pytest.raises(CombatManeuverError) as exc:
        await resolve_maneuver(
            FakeDb(actor),
            session=_session(),
            combat=_combat("actor-1"),
            maneuver_name="trip",
            target_id="goblin-1",
            flag_modified_func=lambda *_args: None,
        )

    assert exc.value.status_code == 400
    assert "stunned" in exc.value.detail
