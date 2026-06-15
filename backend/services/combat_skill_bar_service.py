from typing import Any

from services.combat_two_weapon_service import get_two_weapon_fighting_error
from services.dnd_rules import _normalize_class


def build_skill_bar(player: Any) -> list[dict[str, Any]]:
    """
    根据玩家职业 / 等级 / 法术位 / 资源动态生成 10 格技能栏。
    key 1-9+0 对应位置 0-9。
    """
    derived = player.derived or {}
    cls = _normalize_class(player.char_class or "")
    level = player.level or 1
    slots = player.spell_slots or {}
    has_slot_1 = slots.get("1st", 0) > 0
    resources = {
        **(derived.get("class_resources", {}) or {}),
        **(getattr(player, "class_resources", None) or {}),
    }
    conditions = {str(condition).lower() for condition in (getattr(player, "conditions", None) or [])}
    offhand_error = get_two_weapon_fighting_error(player)

    bar: list[dict[str, Any]] = []

    bar.append({
        "k": "atk", "label": "普通攻击", "glyph": "⚔", "cost": "动作",
        "key": "1", "kind": "attack", "available": True,
    })

    if cls == "Paladin":
        bar.append({
            "k": "smite", "label": "神圣斩击", "glyph": "✦",
            "cost": "附赠·1环", "key": "2", "kind": "spell",
            "available": has_slot_1,
            "reason": None if has_slot_1 else "需要 1 环法术位",
            "dmg_hint": "+2d8 光耀",
        })
    elif cls == "Rogue":
        bar.append({
            "k": "sneak", "label": "偷袭", "glyph": "✧",
            "cost": "被动", "key": "2", "kind": "attack",
            "available": True,
            "dmg_hint": f"+{(level + 1) // 2}d6（优势或盟友相邻）",
        })
    elif cls == "Fighter":
        action_surge_left = 0 if resources.get("action_surge_used") else resources.get("action_surge_remaining", 1 if level >= 2 else 0)
        bar.append({
            "k": "action_surge", "label": "行动激发", "glyph": "⚡",
            "cost": "免费", "key": "2", "kind": "bonus",
            "available": action_surge_left > 0,
            "reason": None if action_surge_left > 0 else "本长休已用完",
        })
    elif cls == "Barbarian":
        rage_left = resources.get("rage_remaining", 2)
        bar.append({
            "k": "rage", "label": "狂暴", "glyph": "☠",
            "cost": "附赠", "key": "2", "kind": "bonus",
            "available": rage_left > 0,
            "reason": None if rage_left > 0 else "本长休已用完",
        })
    elif cls == "Wizard":
        bar.append({
            "k": "firebolt", "label": "火焰射线", "glyph": "✴",
            "cost": "动作（戏法）", "key": "2", "kind": "spell",
            "available": True,
            "dmg_hint": "1d10 火焰",
        })
    elif cls == "Cleric":
        bar.append({
            "k": "sacred_flame", "label": "神焰", "glyph": "✶",
            "cost": "动作（戏法）", "key": "2", "kind": "spell",
            "available": True,
            "dmg_hint": "1d8 光耀",
        })
    elif cls == "Monk":
        ki_left = resources.get("ki_remaining", 0)
        bar.append({
            "k": "ki_flurry", "label": "连击飞拳", "glyph": "✥",
            "cost": "附赠·1气", "key": "2", "kind": "bonus",
            "available": ki_left > 0,
            "reason": None if ki_left > 0 else "需要 1 气",
        })
    else:
        bar.append({
            "k": "off_attack", "label": "副手攻击", "glyph": "⚔",
            "cost": "附赠", "key": "2", "kind": "bonus",
            "available": offhand_error is None,
            "reason": offhand_error,
        })

    bar.append({
        "k": "shove", "label": "猛力推撞", "glyph": "↦",
        "cost": "动作", "key": "3", "kind": "attack", "available": True,
    })

    if cls in ("Cleric", "Paladin", "Bard", "Druid"):
        bar.append({
            "k": "bless", "label": "祝福", "glyph": "✧",
            "cost": "动作·1环", "key": "4", "kind": "spell",
            "available": has_slot_1,
            "reason": None if has_slot_1 else "需要 1 环法术位",
        })
    elif cls == "Wizard":
        bar.append({
            "k": "shield", "label": "护盾术", "glyph": "✡",
            "cost": "反应·1环", "key": "4", "kind": "spell",
            "available": False,
            "reason": "反应法术会在被攻击时自动提示" if has_slot_1 else "需要 1 环法术位",
        })
    elif cls == "Monk" and level >= 2:
        ki_left = resources.get("ki_remaining", 0)
        bar.append({
            "k": "ki_patient_defense", "label": "Patient Defense", "glyph": "PD",
            "cost": "bonus/1 ki", "key": "4", "kind": "bonus",
            "available": ki_left > 0,
            "reason": None if ki_left > 0 else "Requires 1 ki",
        })
    else:
        bar.append({
            "k": "dodge", "label": "闪避", "glyph": "⊙",
            "cost": "动作", "key": "4", "kind": "action", "available": True,
        })

    if cls == "Paladin":
        lay_left = _lay_on_hands_remaining(resources, level)
        bar.append({
            "k": "lay", "label": "治疗魔掌", "glyph": "☩",
            "cost": "动作", "key": "5", "kind": "action",
            "available": lay_left > 0,
            "reason": None if lay_left > 0 else "已用完本日",
            "dmg_hint": f"剩余 {lay_left} HP",
        })
    elif cls in ("Cleric", "Druid", "Bard"):
        bar.append({
            "k": "heal", "label": "治疗伤口", "glyph": "✚",
            "cost": "动作·1环", "key": "5", "kind": "spell",
            "available": has_slot_1,
            "reason": None if has_slot_1 else "需要 1 环法术位",
            "dmg_hint": "1d8 + 施法能力",
        })
    elif cls == "Fighter":
        second_wind_left = 0 if resources.get("second_wind_used") else resources.get("second_wind_remaining", 1)
        bar.append({
            "k": "second_wind", "label": "再接再厉", "glyph": "✚",
            "cost": "附赠", "key": "5", "kind": "bonus",
            "available": second_wind_left > 0,
            "reason": None if second_wind_left > 0 else "本短休已用完",
            "dmg_hint": "1d10 + 等级",
        })
    else:
        bar.append({
            "k": "pot", "label": "治疗药剂", "glyph": "⚱",
            "cost": "动作", "key": "5", "kind": "item", "available": True,
            "dmg_hint": "2d4 + 2",
        })

    if cls == "Paladin" and level >= 3:
        bar.append({
            "k": "divine_sense", "label": "神性感知", "glyph": "◉",
            "cost": "动作", "key": "6", "kind": "action", "available": True,
        })
        lay_left = _lay_on_hands_remaining(resources, level)
        if lay_left >= 5 and "poisoned" in conditions:
            bar[-1] = {
                "k": "lay_on_hands_cure_poison", "label": "Cure Poison", "glyph": "LP",
                "cost": "action/5 pool", "key": "6", "kind": "action", "available": True,
            }
        elif lay_left >= 5 and ("disease" in conditions or "diseased" in conditions):
            bar[-1] = {
                "k": "lay_on_hands_cure_disease", "label": "Cure Disease", "glyph": "LD",
                "cost": "action/5 pool", "key": "6", "kind": "action", "available": True,
            }
    elif cls == "Rogue" and level >= 2:
        bar.append({
            "k": "cunning_action_hide", "label": "狡诈隐匿", "glyph": "⊿",
            "cost": "附赠", "key": "6", "kind": "bonus", "available": True,
        })
    elif cls == "Bard":
        inspiration_left = resources.get("bardic_inspiration_remaining", 0)
        bar.append({
            "k": "bardic_inspiration", "label": "Bardic Inspiration", "glyph": "BI",
            "cost": "bonus", "key": "6", "kind": "bonus",
            "available": inspiration_left > 0,
            "reason": None if inspiration_left > 0 else "No uses remaining",
            "requires_target": True,
            "target_type": "ally",
        })
    elif cls == "Wizard" and level >= 2:
        bar.append({
            "k": "portent", "label": "预言之兆", "glyph": "☄",
            "cost": "免费", "key": "6", "kind": "bonus",
            "available": bool(resources.get("portent_dice", [])),
        })
    else:
        bar.append({
            "k": "help", "label": "协助", "glyph": "☉",
            "cost": "动作", "key": "6", "kind": "action", "available": True,
        })

    if cls == "Monk" and level >= 2:
        ki_left = resources.get("ki_remaining", 0)
        bar.append({
            "k": "ki_step_of_the_wind_dash", "label": "Step Dash", "glyph": "SD",
            "cost": "bonus/1 ki", "key": "7", "kind": "bonus",
            "available": ki_left > 0,
            "reason": None if ki_left > 0 else "Requires 1 ki",
        })
        bar.append({
            "k": "ki_step_of_the_wind_disengage", "label": "Step Disengage", "glyph": "SW",
            "cost": "bonus/1 ki", "key": "8", "kind": "bonus",
            "available": ki_left > 0,
            "reason": None if ki_left > 0 else "Requires 1 ki",
        })
    elif cls == "Rogue" and level >= 2:
        bar.append({
            "k": "cunning_action_dash", "label": "狡诈冲刺", "glyph": "»",
            "cost": "附赠", "key": "7", "kind": "move", "available": True,
        })
        bar.append({
            "k": "cunning_action_disengage", "label": "狡诈脱离", "glyph": "↶",
            "cost": "附赠", "key": "8", "kind": "move", "available": True,
        })
    else:
        bar.append({
            "k": "dash", "label": "冲刺", "glyph": "»",
            "cost": "动作", "key": "7", "kind": "move", "available": True,
        })
        bar.append({
            "k": "disg", "label": "脱离接战", "glyph": "↶",
            "cost": "动作", "key": "8", "kind": "move", "available": True,
        })
    bar.append({
        "k": "grapple", "label": "擒抱", "glyph": "⛓",
        "cost": "动作", "key": "9", "kind": "attack", "available": True,
    })
    if "grappled" in conditions:
        bar.append({
            "k": "grapple_escape", "label": "脱困", "glyph": "↺",
            "cost": "动作", "key": "0", "kind": "action", "available": True,
            "reason": None,
            "requires_target": False,
            "target_type": "none",
        })
    else:
        bar.append({
            "k": "pot_heal", "label": "治疗药剂", "glyph": "⚱",
            "cost": "动作", "key": "0", "kind": "item", "available": True,
        })

    return bar[:10]


def _lay_on_hands_remaining(resources: dict[str, Any], level: int) -> int:
    return resources.get("lay_on_hands_remaining", resources.get("lay_on_hands_pool", level * 5))
