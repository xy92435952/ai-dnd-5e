from services.encounter_balance_service import estimate_encounter_difficulty, monster_xp


def test_monster_xp_reads_explicit_xp_before_cr():
    assert monster_xp({"xp": "1,100", "cr": "1/4"}) == 1100
    assert monster_xp({"cr": "1/2"}) == 100
    assert monster_xp({"challenge_rating": 2}) == 450
    assert monster_xp({"challenge": "0.25"}) == 50


def test_estimate_encounter_difficulty_for_four_level_one_characters():
    result = estimate_encounter_difficulty(
        [{"level": 1}, {"level": 1}, {"level": 1}, {"level": 1}],
        [{"cr": "1/4"}, {"cr": "1/4"}],
    )

    assert result["party_size"] == 4
    assert result["monster_count"] == 2
    assert result["base_xp"] == 100
    assert result["multiplier"] == 1.5
    assert result["adjusted_xp"] == 150
    assert result["thresholds"] == {"easy": 100, "medium": 200, "hard": 300, "deadly": 400}
    assert result["difficulty"] == "easy"


def test_estimate_encounter_difficulty_marks_deadly_when_adjusted_xp_exceeds_threshold():
    result = estimate_encounter_difficulty(
        [{"level": 3}, {"level": 3}, {"level": 3}, {"level": 3}],
        [{"cr": 2}, {"cr": 2}, {"cr": 2}],
    )

    assert result["base_xp"] == 1350
    assert result["multiplier"] == 2.0
    assert result["adjusted_xp"] == 2700
    assert result["thresholds"]["deadly"] == 1600
    assert result["difficulty"] == "deadly"


def test_estimate_encounter_difficulty_adjusts_multiplier_for_tiny_and_large_parties():
    tiny = estimate_encounter_difficulty([{"level": 2}], [{"cr": "1/4"}, {"cr": "1/4"}])
    large = estimate_encounter_difficulty([{"level": 2}] * 6, [{"cr": "1/4"}, {"cr": "1/4"}])

    assert tiny["multiplier"] == 2.0
    assert large["multiplier"] == 1.0


def test_estimate_encounter_difficulty_returns_none_without_party_or_monsters():
    assert estimate_encounter_difficulty([], [{"cr": 1}])["difficulty"] == "none"
    assert estimate_encounter_difficulty([{"level": 1}], [])["difficulty"] == "none"
