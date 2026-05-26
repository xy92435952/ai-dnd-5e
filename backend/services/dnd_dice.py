"""Dice rolling and DnD check/attack helpers."""

import random
from collections.abc import Callable

from services.dnd_data import SKILL_ABILITY_MAP
from services.dnd_character_rules import (
    get_ability_check_disadvantage_reasons,
    get_saving_throw_auto_fail_reasons,
    get_saving_throw_disadvantage_reasons,
)


def _ability_score_modifier(character: dict, ability: str) -> int:
    scores = character.get("ability_scores") or {}
    try:
        return (int(scores.get(ability, 10) or 10) - 10) // 2
    except (TypeError, ValueError):
        return 0


def roll_dice(notation: str) -> dict:
    """
    解析并掷骰子
    支持格式: 1d20, 2d6+3, 1d8-1, d20 (默认1个)
    返回 {rolls, bonus, total, notation}
    """
    import re
    notation = notation.strip().lower().replace(" ", "")
    pattern = r"^(\d*)d(\d+)([+-]\d+)?$"
    match = re.match(pattern, notation)
    if not match:
        try:
            val = int(notation)
            return {"rolls": [val], "bonus": 0, "total": val, "notation": notation}
        except ValueError:
            return {"rolls": [0], "bonus": 0, "total": 0, "notation": notation}

    count  = int(match.group(1)) if match.group(1) else 1
    sides  = int(match.group(2))
    bonus  = int(match.group(3) or "+0")
    rolls  = [random.randint(1, sides) for _ in range(count)]
    total  = sum(rolls) + bonus

    return {
        "rolls":    rolls,
        "bonus":    bonus,
        "total":    max(0, total),
        "notation": notation,
        "is_crit":   len(rolls) == 1 and sides == 20 and rolls[0] == 20,
        "is_fumble": len(rolls) == 1 and sides == 20 and rolls[0] == 1,
    }


def roll_dice_gwf(notation: str) -> dict:
    """
    Great Weapon Fighting: 伤害骰掷出 1 或 2 时可以重掷（取重掷结果）。
    仅对伤害骰本身生效，不影响 bonus 修正值。
    """
    result = roll_dice(notation)
    import re
    match = re.match(r"^(\d*)d(\d+)([+-]\d+)?$", notation.strip().lower())
    if not match:
        return result
    sides = int(match.group(2))
    new_rolls = []
    rerolled = False
    for r in result["rolls"]:
        if r <= 2:
            new_r = random.randint(1, sides)
            new_rolls.append(new_r)
            rerolled = True
        else:
            new_rolls.append(r)
    if rerolled:
        result["rolls"] = new_rolls
        result["total"] = max(0, sum(new_rolls) + result["bonus"])
        result["gwf_rerolled"] = True
    return result


def roll_advantage(notation: str = "1d20") -> dict:
    """掷骰取高（优势）"""
    r1, r2 = roll_dice(notation), roll_dice(notation)
    chosen = r1 if r1["total"] >= r2["total"] else r2
    return {**chosen, "advantage": True, "other_roll": (r2 if chosen is r1 else r1)["total"]}


def roll_disadvantage(notation: str = "1d20") -> dict:
    """掷骰取低（劣势）"""
    r1, r2 = roll_dice(notation), roll_dice(notation)
    chosen = r1 if r1["total"] <= r2["total"] else r2
    return {**chosen, "disadvantage": True, "other_roll": (r2 if chosen is r1 else r1)["total"]}


def roll_attack(
    attacker: dict,
    target: dict,
    is_ranged: bool = False,
    advantage: bool = False,
    disadvantage: bool = False,
    crit_threshold: int = 20,
) -> dict:
    """
    标准攻击流程（支持优势/劣势）
    attacker/target 需要含 derived 字段
    """
    derived  = attacker.get("derived", {})
    atk_bonus = derived.get("ranged_attack_bonus" if is_ranged else "attack_bonus", 3)
    target_ac = target.get("derived", {}).get("ac", 13)

    if advantage and not disadvantage:
        d20_result = roll_advantage("1d20")
    elif disadvantage and not advantage:
        d20_result = roll_disadvantage("1d20")
    else:
        d20_result = roll_dice("1d20")

    d20          = d20_result["rolls"][0]
    attack_total = d20 + atk_bonus
    is_crit      = d20 >= crit_threshold
    is_fumble    = d20 == 1
    hit          = (not is_fumble) and (is_crit or attack_total >= target_ac)

    return {
        "d20":          d20,
        "attack_bonus": atk_bonus,
        "attack_total": attack_total,
        "target_ac":    target_ac,
        "hit":          hit,
        "is_crit":      is_crit,
        "is_fumble":    is_fumble,
    }


def roll_saving_throw(
    character: dict,
    ability: str,
    dc: int,
    advantage: bool = False,
    disadvantage: bool = False,
    d20_roller: Callable[[str], dict] | None = None,
) -> dict:
    """
    豁免检定
    ability: "str"/"dex"/"con"/"int"/"wis"/"cha"
    """
    auto_fail_reasons = get_saving_throw_auto_fail_reasons(character, ability)
    disadvantage_reasons = get_saving_throw_disadvantage_reasons(character, ability)
    exhaustion_disadvantage = "exhaustion" in disadvantage_reasons
    disadvantage = disadvantage or bool(disadvantage_reasons)
    derived    = character.get("derived", {})
    saves      = derived.get("saving_throws", {})
    total_mod  = saves.get(
        ability,
        derived.get("ability_modifiers", {}).get(
            ability,
            _ability_score_modifier(character, ability),
        ),
    )

    if advantage and not disadvantage:
        d20_result = roll_advantage("1d20")
    elif disadvantage and not advantage:
        d20_result = roll_disadvantage("1d20")
    else:
        roller = d20_roller or roll_dice
        d20_result = roller("1d20")

    d20   = d20_result["rolls"][0]
    total = d20 + total_mod
    auto_failed = bool(auto_fail_reasons)

    return {
        "ability":  ability,
        "d20":      d20,
        "other_roll": d20_result.get("other_roll"),
        "modifier": total_mod,
        "total":    total,
        "dc":       dc,
        "success":  False if auto_failed else total >= dc,
        "advantage": bool(advantage and not disadvantage),
        "disadvantage": bool(disadvantage and not advantage),
        "exhaustion_disadvantage": exhaustion_disadvantage,
        "condition_disadvantage_reasons": [
            reason for reason in disadvantage_reasons if reason != "exhaustion"
        ],
        "auto_fail": auto_failed,
        "auto_fail_reasons": auto_fail_reasons,
    }


def roll_skill_check(
    character: dict,
    skill: str,
    dc: int,
    advantage: bool = False,
    disadvantage: bool = False,
) -> dict:
    """
    技能检定（正确检查角色是否熟练该技能）
    """
    disadvantage_reasons = get_ability_check_disadvantage_reasons(character)
    exhaustion_disadvantage = "exhaustion" in disadvantage_reasons
    disadvantage = disadvantage or bool(disadvantage_reasons)
    derived  = character.get("derived", {})
    prof     = derived.get("proficiency_bonus", 2)
    mods     = derived.get("ability_modifiers", {})
    ability  = SKILL_ABILITY_MAP.get(skill, skill if skill in {"str", "dex", "con", "int", "wis", "cha"} else "wis")
    mod      = mods.get(ability, _ability_score_modifier(character, ability))

    # 检查实际熟练（必须在角色数据里有 proficient_skills）
    proficient_skills = character.get("proficient_skills", [])
    is_proficient     = skill in proficient_skills
    total_mod         = mod + (prof if is_proficient else 0)

    if advantage and not disadvantage:
        d20_result = roll_advantage("1d20")
    elif disadvantage and not advantage:
        d20_result = roll_disadvantage("1d20")
    else:
        d20_result = roll_dice("1d20")

    d20   = d20_result["rolls"][0]
    total = d20 + total_mod

    return {
        "skill":      skill,
        "ability":    ability,
        "d20":        d20,
        "other_roll": d20_result.get("other_roll"),
        "modifier":   total_mod,
        "total":      total,
        "dc":         dc,
        "success":    total >= dc,
        "proficient": is_proficient,
        "advantage": bool(advantage and not disadvantage),
        "disadvantage": bool(disadvantage and not advantage),
        "exhaustion_disadvantage": exhaustion_disadvantage,
        "condition_disadvantage_reasons": [
            reason for reason in disadvantage_reasons if reason != "exhaustion"
        ],
    }


def roll_initiative(characters: list[dict]) -> list[dict]:
    """为所有战斗参与者掷先攻，返回排序后的列表"""
    results = []
    for char in characters:
        dex_mod    = char.get("derived", {}).get("ability_modifiers", {}).get("dex", 0)
        init_mod   = char.get("initiative", char.get("derived", {}).get("initiative", dex_mod))
        d20        = random.randint(1, 20)
        initiative = d20 + init_mod
        results.append({
            "character_id": char.get("id"),
            "name":         char.get("name"),
            "initiative":   initiative,
            "d20":          d20,
            "dex_mod":      dex_mod,
            "is_player":    char.get("is_player", False),
            "is_enemy":     char.get("is_enemy", False),
        })
    # 先攻高者先行，同值时玩家优先
    results.sort(key=lambda x: (x["initiative"], x["is_player"]), reverse=True)
    return results
