import pytest


class FakeCharacter:
    id = "hero-1"
    name = "Hero"
    derived = {"hp_max": 30, "ability_modifiers": {"dex": 0}, "saving_throws": {"dex": 0}}
    conditions = []
    condition_durations = {}
    class_resources = {}
    concentration = None
    death_saves = None
    char_class = "Fighter"
    level = 1

    def __init__(self, hp_current=30):
        self.hp_current = hp_current
        self.conditions = []
        self.condition_durations = {}
        self.class_resources = {}
        self.death_saves = None
        self.concentration = None


class FakeCharacterDb:
    def __init__(self, characters):
        self.characters = {str(character.id): character for character in characters}
        self.added = []
        self.committed = False
        self.deleted = []

    async def get(self, model, entity_id):
        return self.characters.get(str(entity_id))

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.committed = True

    async def delete(self, item):
        self.deleted.append(item)

    async def execute(self, *_args, **_kwargs):
        class _Scalars:
            def first(self):
                return None

        class _Result:
            def scalars(self):
                return _Scalars()

        return _Result()


class FakeDb:
    def __init__(self, character):
        self.character = character
        self.added = []
        self.committed = False
        self.deleted = []

    async def get(self, model, entity_id):
        return self.character if str(entity_id) == self.character.id else None

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.committed = True

    async def delete(self, item):
        self.deleted.append(item)

    async def execute(self, *_args, **_kwargs):
        class _Scalars:
            def first(self):
                return None

        class _Result:
            def scalars(self):
                return _Scalars()

        return _Result()


class FakeSession:
    id = "session-1"
    combat_active = True

    def __init__(self, enemies):
        self.game_state = {"enemies": enemies}


class FakeCombat:
    entity_positions = {}
    turn_order = [{"character_id": "dragon-1"}, {"character_id": "hero-1"}]
    current_turn_index = 0
    round_number = 1
    turn_states = {"dragon-1": {"action_used": False}}


@pytest.mark.asyncio
async def test_handle_ai_special_action_uses_recharge_damage_and_spends_ability(monkeypatch):
    from api.combat.ai_turn_special import handle_ai_special_action

    character = FakeCharacter(hp_current=30)
    enemy = {
        "id": "dragon-1",
        "name": "Dragon",
        "hp_current": 50,
        "recharge_abilities": [{
            "id": "breath",
            "name": "Fire Breath",
            "threshold": 5,
            "available": True,
            "damage_dice": "6d6",
            "damage_type": "fire",
            "save": "dex",
            "save_dc": 13,
            "half_on_save": True,
        }],
    }
    db = FakeDb(character)
    combat = FakeCombat()

    monkeypatch.setattr(
        "api.combat.ai_turn_special.roll_dice",
        lambda expr: {"notation": expr, "rolls": [3, 3, 3, 3, 3, 3], "total": 18},
    )
    monkeypatch.setattr(
        "api.combat.ai_turn_special.roll_saving_throw",
        lambda *_args, **_kwargs: {"ability": "dex", "dc": 13, "total": 10, "success": False},
    )
    monkeypatch.setattr("api.combat.ai_turn_special.tick_ai_actor_conditions", lambda **_kwargs: [])

    async def fake_advance(combat, _session, _db, _turn_order, next_index):
        combat.current_turn_index = next_index

    monkeypatch.setattr("api.combat.ai_turn_special.advance_ai_turn", fake_advance)

    result = await handle_ai_special_action(
        session_id="session-1",
        db=db,
        session=FakeSession([enemy]),
        combat=combat,
        turn_order=combat.turn_order,
        next_index=1,
        actor_id="dragon-1",
        actor_name="Dragon",
        is_enemy=True,
        enemy=enemy,
        enemies=[enemy],
        all_characters=[{"id": character.id, "name": character.name, "hp_current": 30}],
        positions={"dragon-1": {"x": 0, "y": 0}, character.id: {"x": 2, "y": 0}},
        decided_target_id=character.id,
        decided_reason="test breath",
        decision={"action_type": "special", "action_name": "Fire Breath"},
    )

    assert result is not None
    assert result["damage"] == 18
    assert result["target_new_hp"] == 12
    assert character.hp_current == 12
    assert enemy["recharge_abilities"][0]["available"] is False
    assert combat.turn_states["dragon-1"]["action_used"] is True
    assert combat.current_turn_index == 1
    assert db.committed is True


@pytest.mark.asyncio
async def test_handle_ai_special_action_area_recharge_hits_multiple_targets(monkeypatch):
    from api.combat.ai_turn_special import handle_ai_special_action

    hero = FakeCharacter(hp_current=30)
    ally = FakeCharacter(hp_current=30)
    ally.id = "ally-1"
    ally.name = "Ally"
    far = FakeCharacter(hp_current=30)
    far.id = "far-1"
    far.name = "Far"
    enemy = {
        "id": "dragon-1",
        "name": "Dragon",
        "hp_current": 50,
        "recharge_abilities": [{
            "id": "breath",
            "name": "Fire Breath",
            "threshold": 5,
            "available": True,
            "damage_dice": "6d6",
            "damage_type": "fire",
            "save": "dex",
            "save_dc": 13,
            "half_on_save": True,
            "area": "15 ft cone",
            "max_targets": 2,
        }],
    }
    db = FakeCharacterDb([hero, ally, far])
    combat = FakeCombat()

    monkeypatch.setattr(
        "api.combat.ai_turn_special.roll_dice",
        lambda expr: {"notation": expr, "rolls": [3, 3, 3, 3, 3, 3], "total": 18},
    )
    saves = iter([
        {"ability": "dex", "dc": 13, "total": 10, "success": False},
        {"ability": "dex", "dc": 13, "total": 16, "success": True},
    ])
    monkeypatch.setattr("api.combat.ai_turn_special.roll_saving_throw", lambda *_args, **_kwargs: next(saves))
    monkeypatch.setattr("api.combat.ai_turn_special.tick_ai_actor_conditions", lambda **_kwargs: [])

    async def fake_advance(combat, _session, _db, _turn_order, next_index):
        combat.current_turn_index = next_index

    monkeypatch.setattr("api.combat.ai_turn_special.advance_ai_turn", fake_advance)

    result = await handle_ai_special_action(
        session_id="session-1",
        db=db,
        session=FakeSession([enemy]),
        combat=combat,
        turn_order=combat.turn_order,
        next_index=1,
        actor_id="dragon-1",
        actor_name="Dragon",
        is_enemy=True,
        enemy=enemy,
        enemies=[enemy],
        all_characters=[
            {"id": hero.id, "name": hero.name, "hp_current": 30},
            {"id": ally.id, "name": ally.name, "hp_current": 30},
            {"id": far.id, "name": far.name, "hp_current": 30},
        ],
        positions={
            "dragon-1": {"x": 0, "y": 0},
            hero.id: {"x": 2, "y": 0},
            ally.id: {"x": 3, "y": 0},
            far.id: {"x": 9, "y": 0},
        },
        decided_target_id=hero.id,
        decided_reason="test breath",
        decision={"action_type": "special", "action_name": "Fire Breath"},
    )

    assert result is not None
    assert result["damage"] == 27
    assert [item["target_id"] for item in result["target_results"]] == [hero.id, ally.id]
    assert [item["damage"] for item in result["target_results"]] == [18, 9]
    assert result["aoe_results"] == result["target_results"]
    assert result["target_id"] == hero.id
    assert hero.hp_current == 12
    assert ally.hp_current == 21
    assert far.hp_current == 30
    assert enemy["recharge_abilities"][0]["available"] is False


@pytest.mark.asyncio
async def test_handle_ai_special_action_returns_none_without_available_recharge():
    from api.combat.ai_turn_special import handle_ai_special_action

    enemy = {
        "id": "dragon-1",
        "name": "Dragon",
        "recharge_abilities": [{
            "id": "breath",
            "name": "Fire Breath",
            "threshold": 5,
            "available": False,
            "damage_dice": "6d6",
        }],
    }

    result = await handle_ai_special_action(
        session_id="session-1",
        db=FakeDb(FakeCharacter()),
        session=FakeSession([enemy]),
        combat=FakeCombat(),
        turn_order=[],
        next_index=0,
        actor_id="dragon-1",
        actor_name="Dragon",
        is_enemy=True,
        enemy=enemy,
        enemies=[enemy],
        all_characters=[{"id": "hero-1", "name": "Hero", "hp_current": 30}],
        positions={"dragon-1": {"x": 0, "y": 0}, "hero-1": {"x": 2, "y": 0}},
        decided_target_id="hero-1",
        decided_reason="",
        decision={"action_type": "special", "action_name": "Fire Breath"},
    )

    assert result is None
