from __future__ import annotations

from typing import Optional

from services.dnd_rules import roll_attack, roll_dice


class AttackResult:
    """单次攻击的完整结果"""

    def __init__(
        self,
        attack_roll: dict,
        damage: int,
        damage_roll: Optional[dict],
        narration: str,
    ):
        self.attack_roll = attack_roll
        self.damage = damage
        self.damage_roll = damage_roll
        self.narration = narration

    def to_dict(self) -> dict:
        return {
            "attack_result": self.attack_roll,
            "damage": self.damage,
            "damage_roll": self.damage_roll,
            "narration": self.narration,
        }


def resolve_melee_attack(
    attacker_derived: dict,
    target_derived: dict,
    advantage: bool = False,
    disadvantage: bool = False,
    is_ranged: bool = False,
    is_offhand: bool = False,
) -> AttackResult:
    crit_threshold = attacker_derived.get("crit_threshold", 20)
    attack_roll = roll_attack(
        {"derived": attacker_derived},
        {"derived": target_derived},
        is_ranged=is_ranged,
        advantage=advantage,
        disadvantage=disadvantage,
        crit_threshold=crit_threshold,
    )

    damage = 0
    damage_roll = None

    if attack_roll["hit"]:
        hit_die = attacker_derived.get("hit_die", 8)
        mods = attacker_derived.get("ability_modifiers", {})
        raw_mod = mods.get("dex", 0) if is_ranged else mods.get("str", 0)
        dmg_mod = 0 if is_offhand and not attacker_derived.get("two_weapon_fighting", False) else raw_mod
        style_effects = attacker_derived.get("style_effects", {})
        use_gwf = not is_ranged and not is_offhand and style_effects.get("reroll_low", False)
        if use_gwf:
            from services.dnd_rules import roll_dice_gwf
            damage_roll = roll_dice_gwf(f"1d{hit_die}+{dmg_mod}")
        else:
            damage_roll = roll_dice(f"1d{hit_die}+{dmg_mod}")
        damage = damage_roll["total"]
        if attack_roll["is_crit"]:
            if use_gwf:
                from services.dnd_rules import roll_dice_gwf
                extra = roll_dice_gwf(f"1d{hit_die}")
            else:
                extra = roll_dice(f"1d{hit_die}")
            damage += extra["total"]

    narration = build_attack_narration(
        attacker_derived.get("name", "施动者"),
        target_derived.get("name", "目标"),
        attack_roll,
        damage,
    )
    return AttackResult(attack_roll, damage, damage_roll, narration)


def build_attack_narration(
    actor_name: str,
    target_name: str,
    attack_roll: dict,
    damage: int,
) -> str:
    atk = attack_roll["attack_total"]
    ac = attack_roll["target_ac"]
    if attack_roll["is_crit"]:
        return f"💥 暴击！{actor_name} 对 {target_name} 造成 {damage} 点伤害！"
    if attack_roll["hit"]:
        return f"{actor_name} 攻击 {target_name}，命中！造成 {damage} 点伤害。（{atk} vs AC{ac}）"
    if attack_roll["is_fumble"]:
        return f"💀 {actor_name} 攻击 {target_name} 时大失手！武器差点脱手。"

    diff = ac - atk
    if diff <= 2:
        return f"{actor_name} 攻击 {target_name}，险些命中！{target_name} 勉强格挡住了攻击。（{atk} vs AC{ac}）"
    if diff <= 5:
        return f"{actor_name} 的攻击被 {target_name} 闪避。（{atk} vs AC{ac}）"
    return f"{actor_name} 的攻击完全没有威胁，{target_name} 轻松躲开。（{atk} vs AC{ac}）"
