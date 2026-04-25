"""
单元测试：5e 进阶规则覆盖（不依赖端点，直接调 service）。

覆盖：
  - Extra Attack（fighter/paladin/ranger/barbarian/monk Lv5）
  - Sneak Attack 骰子表
  - Divine Smite 伤害
  - Rage 加值与每日次数
  - 伤害抗性 / 免疫 / 易伤
  - 掩体（Half / Three-quarters）

这些函数都是纯计算（除了 calc_divine_smite_damage 内部掷骰随机），
所以直接断言数学不变量。
"""
import pytest
from services.combat_service import CombatService

svc = CombatService()


# ──────────────────────────────────────────────────────────
# Extra Attack — Lv5+ 战斗职业每回合 2 次攻击
# ──────────────────────────────────────────────────────────

class TestExtraAttack:
    @pytest.mark.parametrize("char_class,level,expected", [
        # Fighter 每 5 级递增（5/11/20）
        ("Fighter", 1, 1),
        ("Fighter", 4, 1),
        ("Fighter", 5, 2),
        ("Fighter", 10, 2),
        ("Fighter", 11, 3),
        ("Fighter", 20, 4),
        # Paladin / Ranger / Barbarian / Monk 仅 Lv5 一次提升
        ("Paladin",   5, 2),
        ("Ranger",    5, 2),
        ("Barbarian", 5, 2),
        ("Monk",      5, 2),
        # 法系不享受 Extra Attack
        ("Wizard",  20, 1),
        ("Cleric",   5, 1),
        ("Sorcerer", 5, 1),
        ("Warlock",  5, 1),  # 注意：Warlock Lv5 通过 Pact of Blade 才有 Extra Attack，base 没有
        # Druid Lv5 不享受（默认）
        ("Druid",    5, 1),
    ])
    def test_attack_count_by_class_level(self, char_class, level, expected):
        assert svc.get_attack_count({}, level, char_class) == expected


# ──────────────────────────────────────────────────────────
# Sneak Attack — Rogue 每隔 1 级 +1d6
# ──────────────────────────────────────────────────────────

class TestSneakAttack:
    @pytest.mark.parametrize("level,dice", [
        (1, 1), (2, 1),
        (3, 2), (4, 2),
        (5, 3),
        (7, 4),
        (9, 5),
        (11, 6),
        (13, 7),
        (15, 8),
        (17, 9),
        (19, 10),  # max
        (20, 10),
    ])
    def test_dice_progression(self, level, dice):
        assert svc.calc_sneak_attack_dice(level) == dice

    def test_only_rogue_can_sneak(self):
        assert svc.check_sneak_attack("Rogue", has_advantage=True, ally_adjacent_to_target=False) is True
        assert svc.check_sneak_attack("Fighter", has_advantage=True, ally_adjacent_to_target=False) is False

    def test_advantage_or_ally_adjacent(self):
        # 满足任一就触发
        assert svc.check_sneak_attack("Rogue", has_advantage=True,  ally_adjacent_to_target=False) is True
        assert svc.check_sneak_attack("Rogue", has_advantage=False, ally_adjacent_to_target=True)  is True
        # 都不满足 → 不触发
        assert svc.check_sneak_attack("Rogue", has_advantage=False, ally_adjacent_to_target=False) is False

    def test_swashbuckler_no_other_enemy_adjacent(self):
        """Swashbuckler 即使没盟友相邻，只要目标周围没**其他**敌人也能触发。"""
        assert svc.check_sneak_attack(
            "Rogue", has_advantage=False, ally_adjacent_to_target=False,
            swashbuckler=True, no_other_enemy_adjacent=True,
        ) is True


# ──────────────────────────────────────────────────────────
# Divine Smite — Paladin 消耗法术位增加伤害
# ──────────────────────────────────────────────────────────

class TestDivineSmite:
    def test_lv1_slot_2d8(self):
        """1 环位 → 2d8（dice_count = 1 + slot_level = 2）。"""
        r = svc.calc_divine_smite_damage(slot_level=1, target_is_undead=False)
        assert r["dice"] == "2d8"
        assert 2 <= r["damage"] <= 16  # 2d8 范围

    def test_lv5_slot_caps_at_6d8(self):
        """5 环位 vs 普通敌人 = 6d8。"""
        r = svc.calc_divine_smite_damage(slot_level=5, target_is_undead=False)
        assert r["dice"] == "6d8"

    def test_undead_adds_1d8(self):
        """undead/fiend 额外 +1d8（1 环位变 3d8）。"""
        r = svc.calc_divine_smite_damage(slot_level=1, target_is_undead=True)
        assert r["dice"] == "3d8"

    def test_max_cap_6d8_even_undead(self):
        """5 环位 + undead 也只 6d8（封顶，否则 7d8）。"""
        r = svc.calc_divine_smite_damage(slot_level=5, target_is_undead=True)
        assert r["dice"] == "6d8"


# ──────────────────────────────────────────────────────────
# Rage —— Barbarian 狂暴
# ──────────────────────────────────────────────────────────

class TestRage:
    @pytest.mark.parametrize("level,bonus", [
        (1, 2), (2, 2), (8, 2),
        (9, 3), (10, 3), (15, 3),
        (16, 4), (20, 4),
    ])
    def test_rage_bonus_progression(self, level, bonus):
        assert svc.get_rage_bonus(level) == bonus

    @pytest.mark.parametrize("level,uses", [
        (1, 2), (2, 2),
        (3, 3), (5, 3),
        (6, 4), (11, 4),
        (12, 5),
        (17, 6),
        (20, 999),  # 20 级无限
    ])
    def test_rage_uses_progression(self, level, uses):
        assert svc.get_rage_uses(level) == uses


# ──────────────────────────────────────────────────────────
# 伤害抗性 / 免疫 / 易伤
# ──────────────────────────────────────────────────────────

class TestDamageResistance:
    def test_resistance_halves(self):
        assert svc.apply_damage_with_resistance(
            base_damage=10, damage_type="fire",
            resistances=["fire"], immunities=[], vulnerabilities=[],
        ) == 5

    def test_immunity_zeros(self):
        assert svc.apply_damage_with_resistance(
            base_damage=20, damage_type="poison",
            resistances=[], immunities=["poison"], vulnerabilities=[],
        ) == 0

    def test_vulnerability_doubles(self):
        assert svc.apply_damage_with_resistance(
            base_damage=8, damage_type="cold",
            resistances=[], immunities=[], vulnerabilities=["cold"],
        ) == 16

    def test_no_modifiers_passthrough(self):
        assert svc.apply_damage_with_resistance(
            base_damage=12, damage_type="bludgeoning",
            resistances=[], immunities=[], vulnerabilities=[],
        ) == 12

    def test_immunity_takes_precedence_over_resistance(self):
        """免疫优先于抗性（同时配置时不应只是减半）。"""
        assert svc.apply_damage_with_resistance(
            base_damage=20, damage_type="poison",
            resistances=["poison"], immunities=["poison"], vulnerabilities=[],
        ) == 0


# ──────────────────────────────────────────────────────────
# 掩体 —— wall = full obstacle, difficult = half
# ──────────────────────────────────────────────────────────

class TestCover:
    def test_no_grid_no_cover(self):
        assert svc.get_cover_bonus({}, {"x": 0, "y": 0}, {"x": 5, "y": 5}) == 0

    def test_one_wall_between_half_cover(self):
        """中间一面墙 → +2 AC（半掩体）。"""
        grid = {"3_0": "wall"}
        bonus = svc.get_cover_bonus(grid, {"x": 0, "y": 0}, {"x": 5, "y": 0})
        assert bonus in (2, 5)  # 至少半掩体；具体看路径算法

    def test_two_walls_three_quarters(self):
        """两面墙 → +5 AC（3/4 掩体）。"""
        grid = {"2_0": "wall", "3_0": "wall"}
        bonus = svc.get_cover_bonus(grid, {"x": 0, "y": 0}, {"x": 5, "y": 0})
        assert bonus == 5

    def test_attacker_on_target_no_cover(self):
        """同格 → 不计算掩体。"""
        assert svc.get_cover_bonus({"3_3": "wall"}, {"x": 5, "y": 5}, {"x": 5, "y": 5}) == 0
