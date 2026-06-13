import pytest


class FakeActor:
    id = "fighter-1"
    name = "Battle Master"
    hp_current = 44
    conditions = []
    death_saves = {}
    derived = {
        "proficiency_bonus": 3,
        "ability_modifiers": {"str": 4, "dex": 2},
        "subclass_effects": {
            "battle_master": True,
            "maneuvers": ["precision", "trip", "menacing"],
            "superiority_die": "d8",
        },
    }

    def __init__(self):
        self.class_resources = {
            "superiority_dice_remaining": 2,
            "maneuvers_known": ["trip"],
        }


class FakeDb:
    def __init__(self, actor):
        self.actor = actor

    async def get(self, model, entity_id):
        return self.actor if entity_id == "fighter-1" else None


class FakeCombat:
    current_turn_index = 0
    turn_order = [{"character_id": "fighter-1"}]


class FakeSession:
    game_state = {
        "enemies": [
            {
                "id": "orc-1",
                "name": "Orc",
                "conditions": [],
                "ability_scores": {"str": 8, "wis": 8},
            }
        ]
    }


@pytest.mark.asyncio
async def test_resolve_maneuver_uses_known_maneuver_list_when_present():
    from services.combat_maneuver_service import CombatManeuverError, resolve_maneuver

    with pytest.raises(CombatManeuverError) as exc:
        await resolve_maneuver(
            FakeDb(FakeActor()),
            session=FakeSession(),
            combat=FakeCombat(),
            maneuver_name="menacing",
            target_id="orc-1",
        )

    assert exc.value.status_code == 400
    assert "trip" in exc.value.detail
