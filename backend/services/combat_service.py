"""
战斗规则服务
负责所有战斗数学计算，与 HTTP 层完全解耦
"""
from __future__ import annotations
from typing import Optional
from services.dnd_rules import roll_attack, roll_dice, roll_saving_throw


class AttackResult:
    """单次攻击的完整结果"""
    def __init__(
        self,
        attack_roll: dict,
        damage: int,
        damage_roll: Optional[dict],
        narration: str,
    ):
        self.attack_roll  = attack_roll
        self.damage       = damage
        self.damage_roll  = damage_roll
        self.narration    = narration

    def to_dict(self) -> dict:
        return {
            "attack_result": self.attack_roll,
            "damage":        self.damage,
            "damage_roll":   self.damage_roll,
            "narration":     self.narration,
        }


class CombatService:
    """
    5e 战斗规则服务
    所有方法均为静态/纯函数，可独立测试
    """

    # ── 攻击解析 ──────────────────────────────────────────

    @staticmethod
    def resolve_melee_attack(
        attacker_derived: dict,
        target_derived:   dict,
        advantage:        bool = False,
        disadvantage:     bool = False,
        is_ranged:        bool = False,
        is_offhand:       bool = False,  # 副手攻击：伤害不加属性修正（除非有双武器战斗特技）
    ) -> AttackResult:
        """
        解析一次攻击（支持近战/远程/副手）。
        is_offhand=True 时：无属性修正（5e PHB p.195），
        除非攻击者有 derived["two_weapon_fighting"]=True（双武器战斗特技）。
        """
        crit_threshold = attacker_derived.get("crit_threshold", 20)
        attack_roll = roll_attack(
            {"derived": attacker_derived},
            {"derived": target_derived},
            is_ranged       = is_ranged,
            advantage       = advantage,
            disadvantage    = disadvantage,
            crit_threshold  = crit_threshold,
        )

        damage       = 0
        damage_roll  = None

        if attack_roll["hit"]:
            hit_die  = attacker_derived.get("hit_die", 8)
            mods     = attacker_derived.get("ability_modifiers", {})
            raw_mod  = mods.get("dex", 0) if is_ranged else mods.get("str", 0)
            # 副手攻击不加属性修正，除非持有双武器战斗特技
            if is_offhand and not attacker_derived.get("two_weapon_fighting", False):
                dmg_mod = 0
            else:
                dmg_mod = raw_mod
            # Great Weapon Fighting: 近战非远程，使用双手/大型武器时，重掷 1/2
            style_effects = attacker_derived.get("style_effects", {})
            use_gwf = (not is_ranged and not is_offhand
                       and style_effects.get("reroll_low", False))
            if use_gwf:
                from services.dnd_rules import roll_dice_gwf
                damage_roll = roll_dice_gwf(f"1d{hit_die}+{dmg_mod}")
            else:
                damage_roll = roll_dice(f"1d{hit_die}+{dmg_mod}")
            damage      = damage_roll["total"]
            if attack_roll["is_crit"]:
                if use_gwf:
                    from services.dnd_rules import roll_dice_gwf
                    extra = roll_dice_gwf(f"1d{hit_die}")
                else:
                    extra = roll_dice(f"1d{hit_die}")
                damage += extra["total"]

        narration = CombatService._build_narration(
            attacker_derived.get("name", "施动者"),
            target_derived.get("name", "目标"),
            attack_roll, damage,
        )
        return AttackResult(attack_roll, damage, damage_roll, narration)

    @staticmethod
    def _build_narration(
        actor_name:  str,
        target_name: str,
        attack_roll: dict,
        damage:      int,
    ) -> str:
        atk   = attack_roll["attack_total"]
        ac    = attack_roll["target_ac"]
        if attack_roll["is_crit"]:
            return f"💥 暴击！{actor_name} 对 {target_name} 造成 {damage} 点伤害！"
        elif attack_roll["hit"]:
            return f"{actor_name} 攻击 {target_name}，命中！造成 {damage} 点伤害。（{atk} vs AC{ac}）"
        elif attack_roll["is_fumble"]:
            return f"💀 {actor_name} 攻击 {target_name} 时大失手！武器差点脱手。"
        else:
            diff = ac - atk
            if diff <= 2:
                return f"{actor_name} 攻击 {target_name}，险些命中！{target_name} 勉强格挡住了攻击。（{atk} vs AC{ac}）"
            elif diff <= 5:
                return f"{actor_name} 的攻击被 {target_name} 闪避。（{atk} vs AC{ac}）"
            else:
                return f"{actor_name} 的攻击完全没有威胁，{target_name} 轻松躲开。（{atk} vs AC{ac}）"

    # ── 伤害应用 ──────────────────────────────────────────

    @staticmethod
    def apply_damage(current_hp: int, damage: int, max_hp: int) -> int:
        """计算受击后 HP，不低于 0"""
        return max(0, current_hp - damage)

    @staticmethod
    def apply_heal(current_hp: int, heal: int, max_hp: int) -> int:
        """计算治疗后 HP，不超过最大值"""
        return min(max_hp, current_hp + heal)

    # ── 战斗结束判断 ──────────────────────────────────────

    @staticmethod
    def check_combat_over(
        enemies:   list[dict],
        player_hp: int,
    ) -> tuple[bool, Optional[str]]:
        """
        返回 (combat_over: bool, outcome: str|None)
        outcome = "victory" | "defeat" | None

        5e 规则：HP=0 不等于死亡，角色进入濒死状态进行死亡豁免。
        只有当所有敌人死亡时才判定胜利。
        玩家 HP=0 时不自动结束战斗（需要通过死亡豁免系统判定）。
        """
        alive_enemies = [e for e in enemies if e.get("hp_current", 0) > 0]
        if not alive_enemies:
            return True, "victory"
        # HP=0 时不结束战斗 — 玩家进入濒死状态，通过死亡豁免判定
        # 只有当玩家被标记为彻底死亡时才 defeat（由 death-save 端点处理）
        return False, None

    # ── 状态条件效果 ──────────────────────────────────────

    @staticmethod
    def get_attack_modifiers(conditions: list[str]) -> tuple[bool, bool]:
        """
        根据状态条件返回 (advantage, disadvantage)
        5e 规则：优势/劣势互相抵消
        """
        ADV_CONDITIONS  = {"invisible", "hidden"}
        # Note: exhaustion level 3+ causes attack disadvantage (handled here as generic "exhaustion" condition)
        DIS_CONDITIONS  = {"poisoned", "frightened", "prone", "blinded",
                           "restrained", "exhaustion"}
        adv = any(c in ADV_CONDITIONS for c in conditions)
        dis = any(c in DIS_CONDITIONS for c in conditions)
        return adv, dis

    @staticmethod
    def get_defense_modifiers(conditions: list[str]) -> tuple[bool, bool]:
        """
        被攻击时的优/劣势修正（攻击方获得的优/劣势）
        """
        ADV_TO_ATTACKER = {"paralyzed", "petrified", "stunned", "unconscious", "prone",
                           "blinded", "restrained"}  # 5e: blinded/restrained → attacker has advantage
        DIS_TO_ATTACKER = {"invisible", "dodging"}  # dodging: Dodge action gives disadvantage to attackers
        adv = any(c in ADV_TO_ATTACKER for c in conditions)
        dis = any(c in DIS_TO_ATTACKER for c in conditions)
        return adv, dis

    # ── 专注中断检定 ──────────────────────────────────────

    @staticmethod
    def check_concentration(character_dict: dict, damage: int) -> Optional[dict]:
        """
        专注中断检定（5e PHB p.203）
        DC = max(10, floor(damage / 2))
        character_dict 需包含: concentration, derived, proficient_saves
        War Caster 专长：专注豁免具有优势
        返回 None（不需要检定）或 {required, dc, spell_name, broke, roll_result}
        """
        if not character_dict.get("concentration") or damage <= 0:
            return None

        from services.dnd_rules import roll_saving_throw
        dc = max(10, damage // 2)

        # War Caster 专长：专注豁免具有优势
        derived = character_dict.get("derived", {})
        feat_effects = derived.get("feat_effects", {})
        has_war_caster = bool(feat_effects.get("War Caster")) or derived.get("subclass_effects", {}).get("concentration_advantage", False)
        roll_result = roll_saving_throw(character_dict, "con", dc, advantage=has_war_caster)

        return {
            "required":    True,
            "dc":          dc,
            "spell_name":  character_dict["concentration"],
            "broke":       not roll_result["success"],
            "roll_result": roll_result,
            "war_caster":  has_war_caster,
        }

    # ── 额外攻击 (Extra Attack, 5e PHB) ────────────────────

    @staticmethod
    def get_attack_count(char_derived: dict, level: int, char_class: str) -> int:
        """5e Extra Attack: martial classes get 2 attacks at level 5+, Fighter gets 3 at 11, 4 at 20"""
        cls = char_class
        if cls in ('Fighter',) and level >= 20:
            return 4
        if cls in ('Fighter',) and level >= 11:
            return 3
        if cls in ('Fighter', 'Paladin', 'Ranger', 'Barbarian', 'Monk') and level >= 5:
            return 2
        return 1

    # ── 偷袭 (Sneak Attack, 5e PHB) ─────────────────────

    @staticmethod
    def calc_sneak_attack_dice(level: int) -> int:
        """Rogue sneak attack: 1d6 per 2 levels (rounded up)"""
        return (level + 1) // 2  # 1 at L1, 2 at L3, 3 at L5, etc.

    @staticmethod
    def check_sneak_attack(attacker_class: str, has_advantage: bool, ally_adjacent_to_target: bool,
                           swashbuckler: bool = False, no_other_enemy_adjacent: bool = False) -> bool:
        """Check if sneak attack conditions are met.
        Swashbuckler: can sneak attack if no other creature is adjacent to target (Rakish Audacity).
        """
        if attacker_class not in ('Rogue', '游荡者'):
            return False
        if has_advantage or ally_adjacent_to_target:
            return True
        # Swashbuckler Rakish Audacity: sneak attack if no other enemy adjacent to target
        if swashbuckler and no_other_enemy_adjacent:
            return True
        return False

    # ── 神圣斩击 (Divine Smite, 5e PHB) ──────────────────

    @staticmethod
    def calc_divine_smite_damage(slot_level: int, target_is_undead: bool = False) -> dict:
        """Paladin Divine Smite: 2d8 + 1d8 per level above 1st, +1d8 vs undead/fiend"""
        dice_count = 1 + slot_level  # 2d8 at 1st level, 3d8 at 2nd, etc.
        if target_is_undead:
            dice_count += 1
        dice_count = min(dice_count, 6)  # max 6d8 (5th level + undead)
        result = roll_dice(f"{dice_count}d8")
        return {"damage": result["total"], "dice": f"{dice_count}d8", "roll": result}

    # ── 狂暴 (Rage, 5e PHB) ──────────────────────────────

    @staticmethod
    def get_rage_bonus(level: int) -> int:
        """Barbarian rage bonus damage by level"""
        if level >= 16:
            return 4
        if level >= 9:
            return 3
        return 2

    @staticmethod
    def get_rage_uses(level: int) -> int:
        """Barbarian rage uses per long rest"""
        if level >= 20:
            return 999  # unlimited
        if level >= 17:
            return 6
        if level >= 12:
            return 5
        if level >= 6:
            return 4
        if level >= 3:
            return 3
        return 2

    # ── 伤害抗性 (Damage Resistance, 5e PHB) ─────────────

    @staticmethod
    def apply_damage_with_resistance(
        base_damage: int,
        damage_type: str,
        resistances: list,
        immunities: list,
        vulnerabilities: list = None,
    ) -> int:
        """Apply damage resistance/immunity/vulnerability"""
        if vulnerabilities is None:
            vulnerabilities = []
        if damage_type in immunities:
            return 0
        if damage_type in vulnerabilities:
            return base_damage * 2
        if damage_type in resistances:
            return base_damage // 2
        return base_damage

    # ── 掩体 (Cover, 5e PHB p.196) ─────────────────────────

    @staticmethod
    def get_cover_bonus(grid_data: dict, attacker_pos: dict, target_pos: dict) -> int:
        """
        Calculate cover AC bonus based on obstacles between attacker and target.
        Uses simple line-of-sight: count obstacle cells along the path.
        Returns: 0 (no cover), 2 (half cover), 5 (three-quarters cover)
        """
        if not grid_data or not attacker_pos or not target_pos:
            return 0

        ax, ay = attacker_pos.get("x", 0), attacker_pos.get("y", 0)
        tx, ty = target_pos.get("x", 0), target_pos.get("y", 0)

        # Walk from attacker to target using Bresenham-like steps
        dx = tx - ax
        dy = ty - ay
        steps = max(abs(dx), abs(dy))
        if steps == 0:
            return 0

        obstacles = 0
        for i in range(1, steps):  # Skip start and end
            cx = ax + round(dx * i / steps)
            cy = ay + round(dy * i / steps)
            cell_key = f"{cx}_{cy}"
            terrain = grid_data.get(cell_key, "")
            if terrain == "wall":
                obstacles += 1
            elif terrain == "difficult":
                obstacles += 0.5

        if obstacles >= 2:
            return 5  # Three-quarters cover
        elif obstacles >= 1:
            return 2  # Half cover
        return 0

    # ── 擒抱/推撞 (Grapple/Shove, 5e PHB p.195) ─────────

    @staticmethod
    def resolve_grapple(
        attacker_derived: dict,
        target_derived: dict,
        attacker_proficient_skills: list = None,
        target_proficient_skills: list = None,
    ) -> dict:
        """
        Contested Athletics check: attacker Athletics vs target Athletics/Acrobatics.
        Returns: {success, attacker_roll, target_roll, ...}
        """
        from services.dnd_rules import roll_skill_check
        atk_check = roll_skill_check(
            {"derived": attacker_derived, "proficient_skills": attacker_proficient_skills or []},
            "运动", dc=0,
        )
        # Target chooses Athletics or Acrobatics (we pick the better modifier)
        t_skills = target_proficient_skills or []
        t_mods = target_derived.get("ability_modifiers", {})
        t_prof = target_derived.get("proficiency_bonus", 2)
        athl_mod = t_mods.get("str", 0) + (t_prof if "运动" in t_skills or "Athletics" in t_skills else 0)
        acrob_mod = t_mods.get("dex", 0) + (t_prof if "杂技" in t_skills or "Acrobatics" in t_skills else 0)
        # Use whichever is better for the target
        if acrob_mod > athl_mod:
            def_check = roll_skill_check(
                {"derived": target_derived, "proficient_skills": t_skills},
                "杂技", dc=0,
            )
        else:
            def_check = roll_skill_check(
                {"derived": target_derived, "proficient_skills": t_skills},
                "运动", dc=0,
            )
        success = atk_check["total"] >= def_check["total"]
        return {
            "success": success,
            "attacker_roll": atk_check,
            "target_roll": def_check,
        }

    @staticmethod
    def resolve_shove(
        attacker_derived: dict,
        target_derived: dict,
        attacker_proficient_skills: list = None,
        target_proficient_skills: list = None,
        shove_type: str = "prone",  # "prone" or "push"
    ) -> dict:
        """
        Contested Athletics check: same as grapple, but result is prone or push 5ft.
        """
        result = CombatService.resolve_grapple(
            attacker_derived, target_derived,
            attacker_proficient_skills, target_proficient_skills,
        )
        result["shove_type"] = shove_type
        return result

    # ── AI 决策辅助 ───────────────────────────────────────

    @staticmethod
    def choose_ai_target(
        actor_is_enemy:   bool,
        player:           Optional[dict],
        allies:           list[dict],
        enemies_alive:    list[dict],
    ) -> Optional[dict]:
        """
        简单 AI 目标选择：
        - 敌方单位 → 攻击玩家（或血量最低的队友）
        - 友方单位 → 攻击血量最低的活着的敌人
        """
        if actor_is_enemy:
            # 优先玩家
            if player and player.get("hp_current", 0) > 0:
                return player
            # 否则攻击血量最低的队友
            alive = [a for a in allies if a.get("hp_current", 0) > 0]
            return min(alive, key=lambda x: x.get("hp_current", 999), default=None)
        else:
            # 攻击血量最低的活着的敌人
            return min(enemies_alive, key=lambda x: x.get("hp_current", 999), default=None)
