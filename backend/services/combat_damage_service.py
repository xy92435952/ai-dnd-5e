from typing import Optional


def apply_damage(current_hp: int, damage: int, max_hp: int) -> int:
    """计算受击后 HP，不低于 0"""
    return max(0, current_hp - damage)


def apply_heal(current_hp: int, heal: int, max_hp: int) -> int:
    """计算治疗后 HP，不超过最大值"""
    return min(max_hp, current_hp + heal)


def check_combat_over(
    enemies: list[dict],
    player_hp: int,
) -> tuple[bool, Optional[str]]:
    alive_enemies = [e for e in enemies if e.get("hp_current", 0) > 0]
    if not alive_enemies:
        return True, "victory"
    return False, None


def apply_damage_with_resistance(
    base_damage: int,
    damage_type: str,
    resistances: list,
    immunities: list,
    vulnerabilities: list = None,
) -> int:
    if vulnerabilities is None:
        vulnerabilities = []
    if damage_type in immunities:
        return 0
    if damage_type in vulnerabilities:
        return base_damage * 2
    if damage_type in resistances:
        return base_damage // 2
    return base_damage
