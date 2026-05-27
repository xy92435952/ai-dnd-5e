from typing import Iterable, Optional


DAMAGE_TYPE_ALIASES = {
    "acid": "acid",
    "酸液": "acid",
    "酸": "acid",
    "bludgeoning": "bludgeoning",
    "钝击": "bludgeoning",
    "blunt": "bludgeoning",
    "cold": "cold",
    "冰冷": "cold",
    "寒冷": "cold",
    "fire": "fire",
    "火焰": "fire",
    "flame": "fire",
    "force": "force",
    "力场": "force",
    "lightning": "lightning",
    "闪电": "lightning",
    "雷电": "lightning",
    "necrotic": "necrotic",
    "坏死": "necrotic",
    "死灵": "necrotic",
    "piercing": "piercing",
    "穿刺": "piercing",
    "poison": "poison",
    "毒素": "poison",
    "毒": "poison",
    "psychic": "psychic",
    "心灵": "psychic",
    "精神": "psychic",
    "radiant": "radiant",
    "辐射": "radiant",
    "光耀": "radiant",
    "光辉": "radiant",
    "slashing": "slashing",
    "挥砍": "slashing",
    "挥斩": "slashing",
    "切割": "slashing",
    "thunder": "thunder",
    "雷鸣": "thunder",
    "音波": "thunder",
}


def normalize_damage_type(damage_type: str | None) -> str:
    """Return a canonical 5e damage type for English or Chinese labels."""
    value = str(damage_type or "").strip()
    if not value:
        return ""
    return DAMAGE_TYPE_ALIASES.get(value.lower(), DAMAGE_TYPE_ALIASES.get(value, value.lower()))


def _normalized_damage_types(values: Iterable | None) -> set[str]:
    return {
        normalized
        for normalized in (normalize_damage_type(value) for value in (values or []))
        if normalized
    }


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
    normalized_type = normalize_damage_type(damage_type)
    normalized_immunities = _normalized_damage_types(immunities)
    normalized_vulnerabilities = _normalized_damage_types(vulnerabilities)
    normalized_resistances = _normalized_damage_types(resistances)

    if normalized_type in normalized_immunities:
        return 0
    if normalized_type in normalized_vulnerabilities:
        return base_damage * 2
    if normalized_type in normalized_resistances:
        return base_damage // 2
    return base_damage
