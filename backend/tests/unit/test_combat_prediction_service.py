from services.combat_prediction_service import (
    build_combat_prediction,
    calculate_hit_and_crit_rate,
    get_damage_range,
)


def test_calculate_hit_rate_applies_advantage():
    hit, crit, final_adv, final_dis = calculate_hit_and_crit_rate(
        target_ac=15,
        attack_bonus=5,
        attack_advantage=True,
        attack_disadvantage=False,
        defense_advantage=False,
        defense_disadvantage=False,
    )

    assert round(hit, 4) == 0.7975
    assert round(crit, 4) == 0.0975
    assert final_adv is True
    assert final_dis is False


def test_build_prediction_uses_ranged_bonus_and_damage_map():
    result = build_combat_prediction(
        attacker_derived={
            "attack_bonus": 4,
            "ranged_attack_bonus": 7,
            "ability_modifiers": {"dex": 3, "str": 1},
        },
        attacker_conditions=[],
        target={"name": "骷髅", "hp": 9, "hp_max": 13, "ac": 14},
        action_key="sneak",
        is_ranged=True,
        attack_modifiers=(False, False),
        defense_modifiers=(False, False),
    )

    assert result["attack_bonus"] == 7
    assert result["damage_dice"] == "1d6"
    assert result["damage_min"] == 4
    assert result["damage_max"] == 9
    assert result["damage_type"] == "切割"
    assert result["target"]["name"] == "骷髅"
    assert "远程" in result["modifiers"]


def test_build_prediction_surfaces_cover_and_advantage_state():
    result = build_combat_prediction(
        attacker_derived={
            "attack_bonus": 6,
            "ability_modifiers": {"str": 3},
        },
        attacker_conditions=[],
        target={"name": "强盗", "hp": 8, "hp_max": 8, "ac": 13},
        action_key="atk",
        is_ranged=False,
        attack_modifiers=(True, False),
        defense_modifiers=(False, False),
        attack_modifier_sources=(["attacker hidden"], []),
        defense_modifier_sources=([], []),
        cover_bonus=2,
    )

    assert result["target_ac"] == 13
    assert result["effective_target_ac"] == 15
    assert result["cover_bonus"] == 2
    assert result["advantage"] is True
    assert result["disadvantage"] is False
    assert result["advantage_sources"] == ["attacker hidden"]
    assert result["disadvantage_sources"] == []
    assert "半掩护" in result["modifiers"]
    assert "优势" in result["modifiers"]


def test_build_prediction_surfaces_cancelled_advantage_sources():
    result = build_combat_prediction(
        attacker_derived={
            "attack_bonus": 5,
            "ability_modifiers": {"str": 3},
        },
        attacker_conditions=[],
        target={"name": "影卫", "hp": 8, "hp_max": 8, "ac": 13},
        action_key="atk",
        is_ranged=False,
        attack_modifiers=(True, True),
        defense_modifiers=(True, False),
        attack_modifier_sources=(["attacker invisible"], ["attacker poisoned"]),
        defense_modifier_sources=(["target restrained"], []),
    )

    assert result["advantage"] is False
    assert result["disadvantage"] is False
    assert result["advantage_sources"] == ["attacker invisible", "target restrained"]
    assert result["disadvantage_sources"] == ["attacker poisoned"]


def test_get_damage_range_handles_flat_and_multi_term_dice():
    assert get_damage_range("1d8", 3) == (4, 11)
    assert get_damage_range("2d8+4d6", 0) == (6, 40)
    assert get_damage_range("3d4+3", 0) == (6, 15)
    assert get_damage_range("—", 0) == (0, 0)
