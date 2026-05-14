from services.combat_prediction_service import (
    build_combat_prediction,
    calculate_hit_and_crit_rate,
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
    assert result["damage_type"] == "切割"
    assert result["target"]["name"] == "骷髅"
    assert "远程" in result["modifiers"]
