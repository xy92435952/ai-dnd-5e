from services.combat_condition_service import get_attack_modifiers, get_defense_modifiers
from services.dnd_rules import (
    get_ability_check_disadvantage_reasons,
    get_saving_throw_auto_fail_reasons,
    get_saving_throw_disadvantage_reasons,
    has_speed_zero_condition,
    normalize_condition,
    normalize_conditions,
    roll_attack,
    roll_saving_throw,
    should_auto_crit_melee_target,
)


def test_normalize_condition_aliases_chinese_status_names():
    assert normalize_condition("中毒") == "poisoned"
    assert normalize_condition("恐惧") == "frightened"
    assert normalize_condition("束缚") == "restrained"
    assert normalize_condition("昏迷") == "unconscious"
    assert normalize_condition("麻痹") == "paralyzed"
    assert normalize_conditions(["中毒", "poisoned", "闪避"]) == ["poisoned", "dodging"]


def test_chinese_conditions_apply_attack_and_defense_modifiers():
    assert get_attack_modifiers(["中毒"])[1] is True
    assert get_attack_modifiers(["隐形"])[0] is True
    assert get_defense_modifiers(["束缚"]) == (True, False)
    assert get_defense_modifiers(["闪避"]) == (False, True)


def test_chinese_conditions_affect_checks_saves_and_movement():
    poisoned = {"conditions": ["中毒"]}
    restrained = {"conditions": ["束缚"]}
    stunned = {"conditions": ["震慑"]}

    assert get_ability_check_disadvantage_reasons(poisoned) == ["poisoned"]
    assert get_saving_throw_disadvantage_reasons(restrained, "dex") == ["restrained"]
    assert get_saving_throw_auto_fail_reasons(stunned, "dex") == ["stunned"]
    assert has_speed_zero_condition({"conditions": ["被擒抱"]}) is True


def test_chinese_bless_and_resistance_apply_roll_modifiers():
    attack = roll_attack(
        {"conditions": ["祝福"], "derived": {"attack_bonus": 1}},
        {"derived": {"ac": 20}},
        d20_roller=lambda _expr: {"rolls": [10], "total": 10},
        modifier_roller=lambda _expr: {"rolls": [4], "total": 4, "notation": "1d4"},
    )
    save = roll_saving_throw(
        {"conditions": ["抗力"], "derived": {"ability_modifiers": {"dex": 1}}},
        "dex",
        dc=20,
        d20_roller=lambda _expr: {"rolls": [10], "total": 10},
        modifier_roller=lambda _expr: {"rolls": [3], "total": 3, "notation": "1d4"},
    )

    assert attack["condition_modifier"] == 4
    assert attack["roll_modifiers"][0]["source"] == "Bless"
    assert save["condition_modifier"] == 3
    assert save["roll_modifiers"][0]["source"] == "Resistance"


def test_chinese_unconscious_forces_close_melee_crit():
    assert should_auto_crit_melee_target(["昏迷"], distance=1, is_ranged=False) is True
    assert should_auto_crit_melee_target(["昏迷"], distance=1, is_ranged=True) is False
