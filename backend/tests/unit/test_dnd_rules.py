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
