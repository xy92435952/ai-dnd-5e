"""
单元测试：services/combat_service.py。

只测 **纯函数** 部分（apply_damage / apply_heal / get_*_modifiers /
check_concentration / calc_sneak_attack_dice / get_attack_count / ...）。
涉及随机骰的函数（resolve_melee_attack）只检查形状和边界。
"""
import pytest
from services.combat_service import CombatService, AttackResult


svc = CombatService()


class TestApplyDamage:
    def test_normal_hit(self):
        assert svc.apply_damage(20, 5, 30) == 15

    def test_overkill_clamped_to_zero(self):
        assert svc.apply_damage(3, 10, 20) == 0

    def test_zero_damage(self):
        assert svc.apply_damage(10, 0, 20) == 10


class TestApplyHeal:
    def test_normal_heal(self):
        assert svc.apply_heal(5, 10, 30) == 15

    def test_cannot_exceed_max(self):
        assert svc.apply_heal(25, 20, 30) == 30

    def test_heal_at_zero(self):
        assert svc.apply_heal(0, 5, 30) == 5


class TestConditionModifiers:
    def test_poisoned_gives_disadvantage_on_attack(self):
        adv, dis = svc.get_attack_modifiers(["poisoned"])
        assert dis is True
        assert adv is False

    def test_invisible_gives_advantage(self):
        adv, dis = svc.get_attack_modifiers(["invisible"])
        assert adv is True

    def test_prone_target_melee_advantage(self):
        """被攻击者 prone 时近战方有优势（defense modifier 视角）。"""
        adv, dis = svc.get_defense_modifiers(["prone"])
        assert adv is True  # 攻击这个倒地目标有优势

    def test_no_conditions_neutral(self):
        adv, dis = svc.get_attack_modifiers([])
        assert (adv, dis) == (False, False)


class TestConcentration:
    def test_no_concentration_returns_none(self):
        char = {"concentration": None, "derived": {}, "proficient_saves": []}
        assert svc.check_concentration(char, damage=5) is None

    def test_zero_damage_returns_none(self):
        char = {
            "concentration": "Bless",
            "derived": {"ability_modifiers": {"con": 2}, "proficiency_bonus": 2},
            "proficient_saves": ["con"],
        }
        assert svc.check_concentration(char, damage=0) is None

    def test_dc_floor_is_10(self):
        """伤害很低时 DC 应为 10（5e 规则：DC = max(10, 伤害 // 2)）。"""
        char = {
            "concentration": "Bless",
            "derived": {"ability_modifiers": {"con": 2}, "proficiency_bonus": 2},
            "proficient_saves": ["con"],
        }
        r = svc.check_concentration(char, damage=4)
        assert r["dc"] == 10

    def test_high_damage_scales_dc(self):
        char = {
            "concentration": "Bless",
            "derived": {"ability_modifiers": {"con": 2}, "proficiency_bonus": 2},
            "proficient_saves": ["con"],
        }
        r = svc.check_concentration(char, damage=40)
        assert r["dc"] == 20


class TestSneakAttack:
    def test_rogue_lv1_one_d6(self):
        assert svc.calc_sneak_attack_dice(1) == 1
        assert svc.calc_sneak_attack_dice(2) == 1

    def test_rogue_lv3_two_d6(self):
        assert svc.calc_sneak_attack_dice(3) == 2

    def test_rogue_lv20_ten_d6(self):
        assert svc.calc_sneak_attack_dice(20) == 10

    def test_non_rogue_returns_false(self):
        assert svc.check_sneak_attack("Fighter", has_advantage=True, ally_adjacent_to_target=False) is False

    def test_rogue_with_advantage_triggers(self):
        assert svc.check_sneak_attack("Rogue", has_advantage=True, ally_adjacent_to_target=False) is True

    def test_rogue_with_ally_adjacent_triggers(self):
        assert svc.check_sneak_attack("Rogue", has_advantage=False, ally_adjacent_to_target=True) is True

    def test_rogue_without_conditions_fails(self):
        assert svc.check_sneak_attack("Rogue", has_advantage=False, ally_adjacent_to_target=False) is False


class TestAttackCount:
    def test_fighter_lv1_one_attack(self):
        assert svc.get_attack_count({}, level=1, char_class="Fighter") == 1

    def test_fighter_lv5_extra_attack(self):
        """Fighter Lv5 获得 Extra Attack。"""
        assert svc.get_attack_count({}, level=5, char_class="Fighter") == 2

    def test_fighter_lv11_three_attacks(self):
        assert svc.get_attack_count({}, level=11, char_class="Fighter") == 3

    def test_wizard_no_extra_attack(self):
        assert svc.get_attack_count({}, level=10, char_class="Wizard") == 1


class TestCheckCombatOver:
    def test_all_enemies_dead_victory(self):
        enemies = [{"hp_current": 0}, {"hp_current": 0}]
        over, outcome = svc.check_combat_over(enemies, player_hp=10)
        assert over is True and outcome == "victory"

    def test_player_hp_zero_not_auto_defeat(self):
        """5e 规则：HP=0 不等于失败（玩家进入濒死豁免）。"""
        enemies = [{"hp_current": 5}]
        over, outcome = svc.check_combat_over(enemies, player_hp=0)
        assert over is False

    def test_ongoing_both_alive(self):
        enemies = [{"hp_current": 5}]
        over, outcome = svc.check_combat_over(enemies, player_hp=10)
        assert over is False


class TestResolveMeleeAttack:
    """带骰子的函数：验证返回 shape 和边界合理性。"""

    def test_returns_attack_result(self):
        attacker = {
            "ability_modifiers": {"str": 3, "dex": 1},
            "attack_bonus": 5, "proficiency_bonus": 2,
        }
        target = {"ac": 14}
        r = svc.resolve_melee_attack(attacker, target)
        assert isinstance(r, AttackResult)
        assert r.attack_roll["d20"] >= 1 and r.attack_roll["d20"] <= 20
        assert "hit" in r.attack_roll
        assert r.damage >= 0

    def test_hit_damages_at_least_one(self):
        """一次命中的伤害至少 1（5e 规则：暴击以外最低 1）。"""
        # 这里用硬编码攻击者命中高 AC 低的场景，保证 hit=True
        attacker = {
            "ability_modifiers": {"str": 5, "dex": 1},
            "attack_bonus": 10, "proficiency_bonus": 2,
        }
        target = {"ac": 5}  # 极低 AC
        # 做 20 次采样，命中时 damage > 0
        hits = [svc.resolve_melee_attack(attacker, target) for _ in range(20)]
        for r in hits:
            if r.attack_roll["hit"]:
                assert r.damage >= 1
