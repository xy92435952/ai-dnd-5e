from services.combat_tactical_service import resolve_grapple, resolve_shove


def test_poisoned_attacker_rolls_grapple_with_disadvantage():
    result = resolve_grapple(
        {"ability_modifiers": {"str": 4}, "proficiency_bonus": 2},
        {"ability_modifiers": {"str": 0, "dex": 0}, "proficiency_bonus": 2},
        attacker_proficient_skills=["运动"],
        target_proficient_skills=[],
        attacker_conditions=["poisoned"],
    )

    assert result["attacker_roll"]["disadvantage"] is True
    assert result["attacker_roll"]["condition_disadvantage_reasons"] == ["poisoned"]


def test_frightened_target_rolls_shove_contest_with_disadvantage():
    result = resolve_shove(
        {"ability_modifiers": {"str": 4}, "proficiency_bonus": 2},
        {"ability_modifiers": {"str": 0, "dex": 0}, "proficiency_bonus": 2},
        attacker_proficient_skills=["运动"],
        target_proficient_skills=[],
        target_conditions=["frightened"],
    )

    assert result["target_roll"]["disadvantage"] is True
    assert result["target_roll"]["condition_disadvantage_reasons"] == ["frightened"]
