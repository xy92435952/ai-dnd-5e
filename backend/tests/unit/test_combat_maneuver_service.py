import pytest


class FakeDb:
    async def get(self, model, entity_id):
        if entity_id == "fighter-1":
            return FakeActor()
        return None


class FakeActor:
    id = "fighter-1"
    name = "战士"
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
        self.class_resources = {"superiority_dice_remaining": 2}


class FakeCombat:
    current_turn_index = 0
    turn_order = [{"character_id": "fighter-1"}]


class FakeSession:
    def __init__(self):
        self.game_state = {
            "enemies": [
                {
                    "id": "orc-1",
                    "name": "兽人",
                    "conditions": [],
                    "ability_scores": {"str": 8, "wis": 8},
                }
            ]
        }


@pytest.mark.asyncio
async def test_resolve_maneuver_consumes_superiority_die_and_applies_trip(monkeypatch):
    from services import combat_maneuver_service as maneuver_service

    monkeypatch.setattr(maneuver_service, "roll_dice", lambda expr: {"formula": expr, "total": 5})
    monkeypatch.setattr(maneuver_service.random, "randint", lambda *_args: 1)

    session = FakeSession()
    actor = FakeActor()

    class Db(FakeDb):
        async def get(self, model, entity_id):
            return actor if entity_id == "fighter-1" else None

    result = await maneuver_service.resolve_maneuver(
        Db(),
        session=session,
        combat=FakeCombat(),
        maneuver_name="trip",
        target_id="orc-1",
        flag_modified_func=lambda *_args: None,
    )

    assert actor.class_resources["superiority_dice_remaining"] == 1
    assert session.game_state["enemies"][0]["conditions"] == ["prone"]
    assert result.payload["maneuver"] == "trip"
    assert result.payload["superiority_die_roll"] == 5
    assert result.payload["dice_remaining"] == 1
    assert result.payload["tripped"] is True
    assert result.payload["dice_roll"] == {"faces": 8, "result": 5, "label": "战技·trip"}
    assert "绊摔攻击" in result.narration


@pytest.mark.asyncio
async def test_resolve_maneuver_rejects_unprepared_maneuver():
    from services.combat_maneuver_service import CombatManeuverError, resolve_maneuver

    with pytest.raises(CombatManeuverError) as exc:
        await resolve_maneuver(
            FakeDb(),
            session=FakeSession(),
            combat=FakeCombat(),
            maneuver_name="pushing",
            target_id="orc-1",
        )

    assert exc.value.status_code == 400
    assert "无效战技" in exc.value.detail
