from types import SimpleNamespace

import pytest


class FakeDb:
    def __init__(self, characters=None):
        self.characters = characters or {}

    async def get(self, _model, entity_id):
        return self.characters.get(str(entity_id))

    def add(self, _item):
        pass


class FakeAttackResult:
    attack_roll = {
        "hit": False,
        "is_crit": False,
        "is_fumble": False,
    }
    damage = 0

    def to_dict(self):
        return {"attack_roll": self.attack_roll, "damage": self.damage}


def _combat(turn_states=None):
    return SimpleNamespace(turn_states=turn_states or {}, entity_positions={})


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


@pytest.mark.asyncio
async def test_mobile_target_does_not_make_opportunity_attack(monkeypatch):
    from services import combat_opportunity_attack_service as opportunity

    def fail_if_called(**_kwargs):
        raise AssertionError("Mobile target should not make an opportunity attack")

    monkeypatch.setattr(opportunity.svc, "resolve_melee_attack", fail_if_called)

    enemies = [{
        "id": "goblin-1",
        "name": "Goblin",
        "hp_current": 7,
        "conditions": [],
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
        combat=_combat({
            "hero-1": {"mobile_opportunity_safe_targets": ["goblin-1"]},
        }),
        moving_id="hero-1",
        old_pos={"x": 5, "y": 5},
        new_pos={"x": 8, "y": 5},
        positions={
            "hero-1": {"x": 5, "y": 5},
            "goblin-1": {"x": 6, "y": 5},
        },
    )

    assert results == []


@pytest.mark.asyncio
async def test_excluded_actor_does_not_make_opportunity_attack(monkeypatch):
    from services import combat_opportunity_attack_service as opportunity

    def fail_if_called(**_kwargs):
        raise AssertionError("excluded actor should not make an opportunity attack")

    monkeypatch.setattr(opportunity.svc, "resolve_melee_attack", fail_if_called)

    enemies = [{
        "id": "goblin-1",
        "name": "Goblin",
        "hp_current": 7,
        "conditions": [],
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
        excluded_actor_ids=["goblin-1"],
    )

    assert results == []


@pytest.mark.asyncio
async def test_mobile_does_not_block_unattacked_opportunity_threat(monkeypatch):
    from services import combat_opportunity_attack_service as opportunity

    attacks: list[str] = []

    def fake_attack(**kwargs):
        attacks.append(str(kwargs["attacker_derived"]["id"]))
        return FakeAttackResult()

    def save_turn_state(combat, entity_id, turn_state):
        combat.turn_states[str(entity_id)] = turn_state

    monkeypatch.setattr(opportunity.svc, "resolve_melee_attack", fake_attack)
    monkeypatch.setattr(opportunity.svc, "_build_narration", lambda *_args: "Miss")
    monkeypatch.setattr(opportunity, "save_turn_state", save_turn_state)

    enemies = [
        {
            "id": "goblin-1",
            "name": "Goblin",
            "hp_current": 7,
            "conditions": [],
            "derived": {"id": "goblin-1", "attack_bonus": 4, "hp_max": 7},
        },
        {
            "id": "orc-1",
            "name": "Orc",
            "hp_current": 15,
            "conditions": [],
            "derived": {"id": "orc-1", "attack_bonus": 5, "hp_max": 15},
        },
    ]
    moving_char = SimpleNamespace(
        id="hero-1",
        name="Hero",
        hp_current=12,
        conditions=[],
        derived={"ac": 14, "hp_max": 12},
    )
    combat = _combat({
        "hero-1": {"mobile_opportunity_safe_targets": ["goblin-1"]},
    })

    results = await opportunity.resolve_opportunity_attacks(
        FakeDb({"hero-1": moving_char}),
        session=_session(enemies),
        combat=combat,
        moving_id="hero-1",
        old_pos={"x": 5, "y": 5},
        new_pos={"x": 8, "y": 5},
        positions={
            "hero-1": {"x": 5, "y": 5},
            "goblin-1": {"x": 6, "y": 5},
            "orc-1": {"x": 5, "y": 6},
        },
    )

    assert attacks == ["orc-1"]
    assert [result["attacker"] for result in results] == ["Orc"]
    assert combat.turn_states["orc-1"]["reaction_used"] is True
