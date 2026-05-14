from typing import Any


ACTION_PREDICTION_MAP = {
    "atk": {"dice": "1d8", "avg": 4.5, "type": "切割", "ability": "str"},
    "smite": {"dice": "1d8+2d8", "avg": 13.5, "type": "光耀", "ability": "str"},
    "sneak": {"dice": "1d6", "avg": 3.5, "type": "切割", "ability": "dex"},
    "firebolt": {"dice": "1d10", "avg": 5.5, "type": "火焰", "ability": None},
    "sacred_flame": {"dice": "1d8", "avg": 4.5, "type": "光耀", "ability": None},
    "shove": {"dice": "—", "avg": 0.0, "type": "力量对抗", "ability": None},
}


def calculate_hit_and_crit_rate(
    *,
    target_ac: int,
    attack_bonus: int,
    attack_advantage: bool,
    attack_disadvantage: bool,
    defense_advantage: bool,
    defense_disadvantage: bool,
) -> tuple[float, float, bool, bool]:
    threshold = target_ac - attack_bonus
    if threshold <= 2:
        base_hit = 0.95
    elif threshold >= 20:
        base_hit = 0.05
    else:
        base_hit = max(0.05, min(0.95, (21 - threshold) / 20.0))

    final_advantage = (attack_advantage or defense_advantage) and not (
        attack_disadvantage or defense_disadvantage
    )
    final_disadvantage = (attack_disadvantage or defense_disadvantage) and not (
        attack_advantage or defense_advantage
    )

    if final_advantage:
        hit_rate = 1 - (1 - base_hit) ** 2
        crit_rate = 1 - (19 / 20) ** 2
    elif final_disadvantage:
        hit_rate = base_hit ** 2
        crit_rate = (1 / 20) ** 2
    else:
        hit_rate = base_hit
        crit_rate = 1 / 20

    return hit_rate, crit_rate, final_advantage, final_disadvantage


def build_combat_prediction(
    *,
    attacker_derived: dict[str, Any],
    attacker_conditions: list[str],
    target: dict[str, Any],
    action_key: str,
    is_ranged: bool,
    attack_modifiers: tuple[bool, bool],
    defense_modifiers: tuple[bool, bool],
) -> dict[str, Any]:
    if is_ranged:
        attack_bonus = attacker_derived.get(
            "ranged_attack_bonus",
            attacker_derived.get("attack_bonus", 0),
        )
    else:
        attack_bonus = attacker_derived.get("attack_bonus", 0)

    attack_advantage, attack_disadvantage = attack_modifiers
    defense_advantage, defense_disadvantage = defense_modifiers
    hit_rate, crit_rate, final_advantage, final_disadvantage = calculate_hit_and_crit_rate(
        target_ac=target["ac"],
        attack_bonus=attack_bonus,
        attack_advantage=attack_advantage,
        attack_disadvantage=attack_disadvantage,
        defense_advantage=defense_advantage,
        defense_disadvantage=defense_disadvantage,
    )

    info = ACTION_PREDICTION_MAP.get(action_key, ACTION_PREDICTION_MAP["atk"])
    ability_bonus = 0
    if info["ability"]:
        ability_bonus = attacker_derived.get("ability_modifiers", {}).get(info["ability"], 0)

    damage_average = info["avg"] + ability_bonus
    expected_damage = round(hit_rate * damage_average + crit_rate * info["avg"], 1)

    modifiers = []
    if final_advantage:
        modifiers.append("优势")
    if final_disadvantage:
        modifiers.append("劣势")
    if is_ranged:
        modifiers.append("远程")
    if attack_advantage and not attack_disadvantage:
        modifiers.append("攻击者状态+")
    if defense_advantage and not defense_disadvantage:
        modifiers.append("目标状态+")

    return {
        "target": {
            "name": target["name"],
            "hp": target["hp"],
            "hp_max": target["hp_max"],
            "ac": target["ac"],
        },
        "hit_rate": round(hit_rate, 2),
        "crit_rate": round(crit_rate, 3),
        "expected_damage": expected_damage,
        "damage_dice": info["dice"],
        "damage_type": info["type"],
        "attack_bonus": attack_bonus,
        "modifiers": modifiers,
    }
