def test_apply_defender_interception_spends_adjacent_defender_reaction():
    from services.combat_defender_reaction_service import apply_defender_interception

    class Combat:
        turn_states = {}

    def save_turn_state(combat, entity_id, turn_state):
        combat.turn_states[str(entity_id)] = turn_state

    combat = Combat()
    positions = {
        "hero-1": {"x": 0, "y": 0},
        "goblin-1": {"x": 1, "y": 0},
        "guard-1": {"x": 1, "y": 1},
    }

    result = apply_defender_interception(
        combat=combat,
        attacker_id="hero-1",
        target_id="goblin-1",
        enemies=[
            {"id": "goblin-1", "name": "Goblin", "hp_current": 7, "tactical_role": "striker"},
            {"id": "guard-1", "name": "Shield Guard", "hp_current": 18, "tactical_role": "defender"},
        ],
        positions=positions,
        save_turn_state_func=save_turn_state,
    )

    assert result == {
        "type": "defender_interception",
        "defender_id": "guard-1",
        "defender_name": "Shield Guard",
        "protected_target_id": "goblin-1",
        "attacker_id": "hero-1",
        "effect": "disadvantage",
    }
    assert combat.turn_states["guard-1"]["reaction_used"] is True
    assert combat.turn_states["guard-1"]["defender_interception"] == result


def test_apply_defender_interception_ignores_spent_or_distant_defenders():
    from services.combat_defender_reaction_service import apply_defender_interception

    class Combat:
        turn_states = {"guard-1": {"reaction_used": True}}

    def save_turn_state(combat, entity_id, turn_state):
        combat.turn_states[str(entity_id)] = turn_state

    combat = Combat()
    result = apply_defender_interception(
        combat=combat,
        attacker_id="hero-1",
        target_id="goblin-1",
        enemies=[
            {"id": "goblin-1", "name": "Goblin", "hp_current": 7, "tactical_role": "striker"},
            {"id": "guard-1", "name": "Spent Guard", "hp_current": 18, "tactical_role": "defender"},
            {"id": "guard-2", "name": "Distant Guard", "hp_current": 18, "tactical_role": "defender"},
        ],
        positions={
            "hero-1": {"x": 0, "y": 0},
            "goblin-1": {"x": 1, "y": 0},
            "guard-1": {"x": 1, "y": 1},
            "guard-2": {"x": 5, "y": 5},
        },
        save_turn_state_func=save_turn_state,
    )

    assert result is None
    assert combat.turn_states["guard-1"]["reaction_used"] is True
