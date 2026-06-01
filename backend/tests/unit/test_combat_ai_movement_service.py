from services.combat_ai_movement_service import choose_skirmisher_reposition


def test_skirmisher_repositions_away_from_party_after_ranged_attack():
    result = choose_skirmisher_reposition(
        actor={"id": "knife-dancer", "tactical_role": "skirmisher"},
        party=[{"id": "hero", "hp_current": 20}],
        positions={
            "knife-dancer": {"x": 5, "y": 2},
            "hero": {"x": 5, "y": 5},
        },
        turn_state={"movement_used": 0, "movement_max": 6},
        target_id="hero",
    )

    assert result is not None
    assert result["steps"] == 2
    assert result["from"] == {"x": 5, "y": 2}
    assert result["nearest_party_distance"] == 5
    assert result["y"] == 0


def test_skirmisher_does_not_leave_melee_without_safe_escape():
    result = choose_skirmisher_reposition(
        actor={"id": "knife-dancer", "tactical_role": "skirmisher"},
        party=[{"id": "hero", "hp_current": 20}],
        positions={
            "knife-dancer": {"x": 5, "y": 4},
            "hero": {"x": 5, "y": 5},
        },
        turn_state={"movement_used": 0, "movement_max": 6},
        target_id="hero",
    )

    assert result is None


def test_skirmisher_with_flyby_can_leave_melee():
    result = choose_skirmisher_reposition(
        actor={
            "id": "winged-stalker",
            "tactical_role": "skirmisher",
            "traits": [{"name": "Flyby", "description": "Does not provoke opportunity attacks."}],
        },
        party=[{"id": "hero", "hp_current": 20}],
        positions={
            "winged-stalker": {"x": 5, "y": 4},
            "hero": {"x": 5, "y": 5},
        },
        turn_state={"movement_used": 0, "movement_max": 6},
        target_id="hero",
    )

    assert result is not None
    assert result["nearest_party_distance"] > 1


def test_non_skirmisher_does_not_use_skirmisher_reposition():
    assert choose_skirmisher_reposition(
        actor={"id": "guard", "tactical_role": "defender"},
        party=[{"id": "hero", "hp_current": 20}],
        positions={
            "guard": {"x": 5, "y": 2},
            "hero": {"x": 5, "y": 5},
        },
        turn_state={"movement_used": 0, "movement_max": 6},
        target_id="hero",
    ) is None
