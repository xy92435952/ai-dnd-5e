"""
单元测试：services/dnd_rules.py 核心规则引擎。

目的：锁定关键 5e 数学不变量——任何未来对引擎的改动若打破这些不变量，
pytest 会立刻红给你看。
"""
import pytest
from services.dnd_rules import (
    ability_modifier, proficiency_bonus,
    apply_racial_bonuses, get_spell_slots,
    roll_dice, roll_advantage, roll_disadvantage,
    roll_skill_check, roll_saving_throw, roll_attack,
    calc_derived, calc_hit_dice_pool,
    clamp_current_hp_to_effective_max,
    apply_character_damage,
    apply_character_healing,
    apply_character_resurrection,
    default_death_saves,
    get_effective_derived,
    get_effective_hp_base,
    get_effective_hp_max,
    get_ability_check_disadvantage_reasons,
    get_incapacitating_reasons,
    get_saving_throw_auto_fail_reasons,
    get_saving_throw_disadvantage_reasons,
    is_dead,
    is_dying,
    is_incapacitated,
    should_auto_crit_melee_target,
    stabilize_character,
    _normalize_class,
)


class TestAbilityModifier:
    @pytest.mark.parametrize("score,expected", [
        (1, -5), (3, -4), (8, -1), (10, 0), (11, 0),
        (12, 1), (14, 2), (15, 2), (16, 3), (20, 5), (30, 10),
    ])
    def test_standard_range(self, score, expected):
        assert ability_modifier(score) == expected


class TestProficiencyBonus:
    @pytest.mark.parametrize("level,expected", [
        (1, 2), (4, 2), (5, 3), (8, 3),
        (9, 4), (12, 4), (13, 5), (16, 5), (17, 6), (20, 6),
    ])
    def test_prof_by_level(self, level, expected):
        assert proficiency_bonus(level) == expected


class TestRacialBonuses:
    def test_human_gets_plus_one_all(self):
        base = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
        out  = apply_racial_bonuses(base, "Human")
        assert all(out[k] == 11 for k in base)

    def test_elf_dex_int(self):
        base = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
        out  = apply_racial_bonuses(base, "Elf")
        assert out["dex"] == 12 and out["int"] == 11


class TestSpellSlots:
    def test_wizard_lv1(self):
        slots = get_spell_slots("Wizard", 1)
        assert slots.get("1st") == 2

    def test_paladin_lv1_no_slots(self):
        """Paladin 半施法：1级没有法术位。"""
        slots = get_spell_slots("Paladin", 1)
        assert slots == {} or slots.get("1st", 0) == 0

    def test_paladin_lv2_gets_slots(self):
        slots = get_spell_slots("Paladin", 2)
        assert slots.get("1st", 0) >= 2

    def test_fighter_no_slots(self):
        slots = get_spell_slots("Fighter", 5)
        assert not any(v > 0 for v in (slots or {}).values())


class TestRollDice:
    def test_parse_expression(self):
        result = roll_dice("2d6+3")
        assert result["total"] >= 2 + 3 and result["total"] <= 12 + 3
        assert len(result["rolls"]) == 2
        # dnd_rules.roll_dice 返回的是 "bonus"（不是 "modifier"）
        assert result["bonus"] == 3

    def test_d20_single(self):
        result = roll_dice("1d20")
        assert 1 <= result["total"] <= 20

    def test_negative_modifier(self):
        result = roll_dice("1d4-1")
        assert result["total"] >= 0 and result["total"] <= 3

    def test_advantage_never_below_disadvantage(self):
        """优势的期望值高于劣势（用采样验证）。"""
        adv_total = sum(roll_advantage()["total"] for _ in range(200))
        dis_total = sum(roll_disadvantage()["total"] for _ in range(200))
        assert adv_total > dis_total


class TestSkillCheck:
    def test_proficient_adds_prof_bonus(self):
        """熟练技能应加上熟练加值。"""
        char = {
            "name": "Tester",
            "ability_scores": {"str": 14, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
            "derived": {
                "ability_modifiers": {"str": 2, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
                "proficiency_bonus": 2,
            },
            "proficient_skills": ["运动"],
            "level": 1,
        }
        result = roll_skill_check(char, "运动", dc=10)
        # modifier 应 = str_mod(2) + prof(2) = 4
        assert result["modifier"] == 4
        assert result["proficient"] is True

    def test_non_proficient_no_prof_bonus(self):
        char = {
            "name": "Tester",
            "ability_scores": {"str": 14, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
            "derived": {
                "ability_modifiers": {"str": 2, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
                "proficiency_bonus": 2,
            },
            "proficient_skills": [],  # 不熟练
            "level": 1,
        }
        result = roll_skill_check(char, "运动", dc=10)
        assert result["modifier"] == 2  # 只有 str_mod
        assert result["proficient"] is False

    def test_exhaustion_level_1_gives_skill_check_disadvantage(self):
        char = {
            "name": "Tired Tester",
            "derived": {
                "ability_modifiers": {"str": 2},
                "proficiency_bonus": 2,
            },
            "proficient_skills": ["运动"],
            "condition_durations": {"exhaustion_level": 1},
        }

        result = roll_skill_check(char, "运动", dc=10)

        assert result["modifier"] == 4
        assert result["disadvantage"] is True
        assert result["exhaustion_disadvantage"] is True

    @pytest.mark.parametrize("condition", ["poisoned", "frightened"])
    def test_conditions_give_skill_check_disadvantage(self, condition):
        char = {
            "derived": {
                "ability_modifiers": {"str": 2},
                "proficiency_bonus": 2,
            },
            "proficient_skills": ["杩愬姩"],
            "conditions": [condition],
        }

        result = roll_skill_check(char, "杩愬姩", dc=10)

        assert result["disadvantage"] is True
        assert result["exhaustion_disadvantage"] is False
        assert result["condition_disadvantage_reasons"] == [condition]
        assert get_ability_check_disadvantage_reasons(char) == [condition]

    def test_raw_ability_check_uses_matching_ability_modifier(self):
        char = {
            "derived": {
                "ability_modifiers": {"str": 4, "wis": -1},
                "proficiency_bonus": 2,
            },
            "proficient_skills": [],
        }

        result = roll_skill_check(char, "str", dc=10)

        assert result["ability"] == "str"
        assert result["modifier"] == 4

    def test_skill_check_falls_back_to_ability_scores(self):
        char = {
            "ability_scores": {"dex": 16},
            "derived": {"proficiency_bonus": 2},
            "proficient_skills": [],
        }

        result = roll_skill_check(char, "dex", dc=10)

        assert result["ability"] == "dex"
        assert result["modifier"] == 3


class TestSavingThrow:
    def test_exhaustion_level_3_gives_saving_throw_disadvantage(self):
        char = {
            "derived": {
                "ability_modifiers": {"con": 2},
                "saving_throws": {"con": 4},
            },
            "condition_durations": {"exhaustion_level": 3},
        }

        result = roll_saving_throw(char, "con", dc=10)

        assert result["modifier"] == 4
        assert result["disadvantage"] is True
        assert result["exhaustion_disadvantage"] is True

    def test_restrained_gives_dex_save_disadvantage(self):
        char = {
            "derived": {
                "ability_modifiers": {"dex": 2},
                "saving_throws": {"dex": 2},
            },
            "conditions": ["restrained"],
        }

        result = roll_saving_throw(char, "dex", dc=10)

        assert result["disadvantage"] is True
        assert result["condition_disadvantage_reasons"] == ["restrained"]
        assert get_saving_throw_disadvantage_reasons(char, "dex") == ["restrained"]

    def test_saving_throw_falls_back_to_ability_scores(self):
        char = {
            "ability_scores": {"dex": 16},
            "derived": {},
        }

        result = roll_saving_throw(
            char,
            "dex",
            dc=10,
            d20_roller=lambda _expr: {"rolls": [7], "total": 7},
        )

        assert result["modifier"] == 3
        assert result["total"] == 10
        assert result["success"] is True

    @pytest.mark.parametrize("condition", ["paralyzed", "stunned", "unconscious", "petrified"])
    @pytest.mark.parametrize("ability", ["str", "dex"])
    def test_incapacitating_conditions_auto_fail_str_and_dex_saves(self, condition, ability):
        char = {
            "derived": {
                "ability_modifiers": {ability: 20},
                "saving_throws": {ability: 20},
            },
            "conditions": [condition],
        }

        result = roll_saving_throw(
            char,
            ability,
            dc=10,
            d20_roller=lambda _expr: {"rolls": [20], "total": 20},
        )

        assert result["total"] == 40
        assert result["success"] is False
        assert result["auto_fail"] is True
        assert result["auto_fail_reasons"] == [condition]
        assert get_saving_throw_auto_fail_reasons(char, ability) == [condition]

    def test_paralyzed_does_not_auto_fail_con_save(self):
        char = {
            "derived": {
                "ability_modifiers": {"con": 4},
                "saving_throws": {"con": 4},
            },
            "conditions": ["paralyzed"],
        }

        result = roll_saving_throw(
            char,
            "con",
            dc=10,
            d20_roller=lambda _expr: {"rolls": [10], "total": 10},
        )

        assert result["success"] is True
        assert result["auto_fail"] is False


class TestExhaustionHpMax:
    def test_level_4_halves_effective_hp_max_without_mutating_base(self):
        char = {
            "hp_current": 20,
            "derived": {"hp_max": 21, "ac": 15},
            "condition_durations": {"exhaustion_level": 4},
        }

        assert get_effective_hp_base(char) == 21
        assert get_effective_hp_max(char) == 10
        effective = get_effective_derived(char)
        assert effective["hp_max"] == 10
        assert effective["base_hp_max"] == 21
        assert char["derived"]["hp_max"] == 21

    def test_missing_or_invalid_exhaustion_uses_base_hp_max(self):
        assert get_effective_hp_max({"derived": {"hp_max": 13}}) == 13
        assert get_effective_hp_max({
            "derived": {"hp_max": 13},
            "condition_durations": {"exhaustion_level": "bad"},
        }) == 13

    def test_clamp_current_hp_to_effective_max(self):
        from types import SimpleNamespace

        char = SimpleNamespace(
            hp_current=18,
            derived={"hp_max": 18},
            condition_durations={"exhaustion_level": 4},
        )

        assert clamp_current_hp_to_effective_max(char) == 9
        assert char.hp_current == 9


class TestCharacterLifeState:
    def test_damage_to_zero_initializes_death_saves(self):
        from types import SimpleNamespace

        char = SimpleNamespace(hp_current=3, death_saves=None, conditions=[])

        result = apply_character_damage(char, 5)

        assert result["dropped_to_zero"] is True
        assert char.hp_current == 0
        assert char.death_saves == default_death_saves()
        assert char.conditions == ["unconscious"]
        assert is_dying(char) is True

    def test_massive_damage_at_drop_to_zero_kills_immediately(self):
        from types import SimpleNamespace

        char = SimpleNamespace(
            hp_current=3,
            death_saves=None,
            derived={"hp_max": 12},
            condition_durations={},
            conditions=[],
        )

        result = apply_character_damage(char, 15)

        assert result["instant_death"] is True
        assert result["dead"] is True
        assert char.hp_current == 0
        assert char.death_saves == {"successes": 0, "failures": 3, "stable": False}
        assert is_dead(char) is True

    def test_damage_at_zero_adds_one_failed_death_save(self):
        from types import SimpleNamespace

        char = SimpleNamespace(
            hp_current=0,
            death_saves={"successes": 1, "failures": 0, "stable": False},
            derived={"hp_max": 12},
            condition_durations={},
            conditions=["unconscious"],
        )

        result = apply_character_damage(char, 4)

        assert result["death_save_failures_added"] == 1
        assert result["instant_death"] is False
        assert char.death_saves == {"successes": 1, "failures": 1, "stable": False}

    def test_critical_damage_at_zero_adds_two_failed_death_saves(self):
        from types import SimpleNamespace

        char = SimpleNamespace(
            hp_current=0,
            death_saves={"successes": 0, "failures": 1, "stable": False},
            derived={"hp_max": 12},
            condition_durations={},
            conditions=["unconscious"],
        )

        result = apply_character_damage(char, 4, is_critical=True)

        assert result["death_save_failures_added"] == 2
        assert result["dead"] is True
        assert char.death_saves == {"successes": 0, "failures": 3, "stable": False}

    def test_massive_damage_at_zero_kills_immediately(self):
        from types import SimpleNamespace

        char = SimpleNamespace(
            hp_current=0,
            death_saves={"successes": 2, "failures": 0, "stable": True},
            derived={"hp_max": 12},
            condition_durations={},
            conditions=["unconscious"],
        )

        result = apply_character_damage(char, 12)

        assert result["instant_death"] is True
        assert result["death_save_failures_added"] == 0
        assert char.death_saves == {"successes": 0, "failures": 3, "stable": False}

    def test_healing_from_zero_clears_death_saves(self):
        from types import SimpleNamespace

        char = SimpleNamespace(
            hp_current=0,
            death_saves={"successes": 1, "failures": 2, "stable": False},
            derived={"hp_max": 12},
            condition_durations={},
            conditions=["unconscious", "poisoned"],
        )

        result = apply_character_healing(char, 4)

        assert result["revived"] is True
        assert char.hp_current == 4
        assert char.death_saves is None
        assert char.conditions == ["poisoned"]

    def test_ordinary_healing_does_not_revive_dead_character(self):
        from types import SimpleNamespace

        char = SimpleNamespace(
            hp_current=0,
            death_saves={"successes": 0, "failures": 3, "stable": False},
            derived={"hp_max": 12},
            condition_durations={},
            conditions=["unconscious"],
        )

        result = apply_character_healing(char, 8)

        assert result["revival_blocked"] is True
        assert result["revived"] is False
        assert char.hp_current == 0
        assert char.death_saves == {"successes": 0, "failures": 3, "stable": False}
        assert char.conditions == ["unconscious"]

    def test_resurrection_revives_dead_character_and_clears_death_saves(self):
        from types import SimpleNamespace

        char = SimpleNamespace(
            hp_current=0,
            death_saves={"successes": 0, "failures": 3, "stable": False},
            derived={"hp_max": 12},
            condition_durations={},
            conditions=["unconscious", "poisoned"],
        )

        result = apply_character_resurrection(char, hp=1)

        assert result["resurrected"] is True
        assert char.hp_current == 1
        assert char.death_saves is None
        assert char.conditions == ["poisoned"]

    def test_stabilized_character_is_not_dying(self):
        from types import SimpleNamespace

        char = SimpleNamespace(hp_current=0, death_saves=None, conditions=[])

        stabilize_character(char)

        assert char.death_saves == {"successes": 0, "failures": 0, "stable": True}
        assert char.conditions == ["unconscious"]
        assert is_dying(char) is False
        assert is_dead(char) is False

    def test_three_failed_death_saves_is_dead(self):
        char = {"hp_current": 0, "death_saves": {"successes": 0, "failures": 3, "stable": False}}

        assert is_dead(char) is True

    @pytest.mark.parametrize("life_state", ["dying", "stable", "dead"])
    def test_zero_hp_life_states_are_incapacitated(self, life_state):
        death_saves = {
            "dying": {"successes": 0, "failures": 0, "stable": False},
            "stable": {"successes": 0, "failures": 0, "stable": True},
            "dead": {"successes": 0, "failures": 3, "stable": False},
        }[life_state]
        char = {"hp_current": 0, "death_saves": death_saves, "conditions": []}

        assert is_incapacitated(char) is True
        assert life_state in get_incapacitating_reasons(char)

    @pytest.mark.parametrize("condition", ["unconscious", "incapacitated", "stunned", "paralyzed", "petrified"])
    def test_incapacitating_conditions_prevent_actions(self, condition):
        char = {"hp_current": 5, "death_saves": None, "conditions": [condition]}

        assert is_incapacitated(char) is True
        assert condition in get_incapacitating_reasons(char)

    def test_unconscious_target_auto_crits_only_close_melee_hits(self):
        assert should_auto_crit_melee_target(["unconscious"], distance=1, is_ranged=False) is True
        assert should_auto_crit_melee_target(["paralyzed"], distance=1, is_ranged=False) is True
        assert should_auto_crit_melee_target(["stunned"], distance=1, is_ranged=False) is False
        assert should_auto_crit_melee_target(["unconscious"], distance=2, is_ranged=False) is False
        assert should_auto_crit_melee_target(["unconscious"], distance=1, is_ranged=True) is False


class TestCalcDerived:
    def test_fighter_lv1(self):
        scores = {"str": 16, "dex": 14, "con": 15, "int": 10, "wis": 12, "cha": 8}
        d = calc_derived("Fighter", 1, scores)
        assert d["hp_max"] >= 10  # d10 hit die + con mod
        assert d["proficiency_bonus"] == 2
        assert d["ability_modifiers"]["str"] == 3

    def test_wizard_has_spell_slots(self):
        scores = {"str": 8, "dex": 14, "con": 13, "int": 16, "wis": 12, "cha": 10}
        d = calc_derived("Wizard", 1, scores)
        assert d["spell_slots_max"].get("1st") == 2
        assert d.get("caster_type") == "full"
        assert d.get("spell_save_dc") == 8 + 2 + 3  # 8 + prof + int_mod

    def test_shield_only_adds_ac_when_equipped(self):
        scores = {"str": 16, "dex": 14, "con": 15, "int": 10, "wis": 12, "cha": 8}
        unequipped = calc_derived("Fighter", 1, scores, equipment={
            "shield": {"name": "Shield", "equipped": False},
        })
        equipped = calc_derived("Fighter", 1, scores, equipment={
            "shield": {"name": "Shield", "equipped": True},
        })

        assert equipped["ac"] == unequipped["ac"] + 2


class TestNormalizeClass:
    @pytest.mark.parametrize("given,expected", [
        ("Fighter", "Fighter"),
        ("战士",     "Fighter"),
        ("Wizard",  "Wizard"),
        ("法师",     "Wizard"),
    ])
    def test_known_aliases(self, given, expected):
        # _normalize_class 按精确串名匹配（不做大小写折叠），
        # 仅保证"英文正式名"和"中文译名"两种输入都能归一到英文正式名
        assert _normalize_class(given) == expected
