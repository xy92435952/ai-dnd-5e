from typing import Any

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
    resources = derived.get("class_resources", {}) or {}

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
        action_surge_left = resources.get("action_surge_remaining", 1 if level >= 2 else 0)
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
            "available": True,
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
            "available": has_slot_1,
            "reason": None if has_slot_1 else "需要 1 环法术位",
        })
    else:
        bar.append({
            "k": "dodge", "label": "闪避", "glyph": "⊙",
            "cost": "动作", "key": "4", "kind": "bonus", "available": True,
        })

    if cls == "Paladin":
        lay_left = resources.get("lay_on_hands_pool", level * 5)
        bar.append({
            "k": "lay", "label": "治疗魔掌", "glyph": "☩",
            "cost": "动作", "key": "5", "kind": "bonus",
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
        second_wind_left = resources.get("second_wind_remaining", 1)
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
            "cost": "动作", "key": "5", "kind": "bonus", "available": True,
            "dmg_hint": "2d4 + 2",
        })

    if cls == "Paladin" and level >= 3:
        bar.append({
            "k": "divine_sense", "label": "神性感知", "glyph": "◉",
            "cost": "动作", "key": "6", "kind": "bonus", "available": True,
        })
    elif cls == "Rogue":
        bar.append({
            "k": "cunning_action", "label": "狡诈行动", "glyph": "⊿",
            "cost": "附赠", "key": "6", "kind": "bonus", "available": True,
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
            "cost": "动作", "key": "6", "kind": "bonus", "available": True,
        })

    bar.append({
        "k": "dash", "label": "冲刺", "glyph": "»",
        "cost": "动作", "key": "7", "kind": "move", "available": True,
    })
    bar.append({
        "k": "disg", "label": "脱离接战", "glyph": "↶",
        "cost": "动作", "key": "8", "kind": "move", "available": True,
    })
    bar.append({
        "k": "empty", "label": "", "glyph": "", "cost": "",
        "key": "9", "kind": "empty", "available": False,
    })
    bar.append({
        "k": "pot_heal", "label": "治疗药剂", "glyph": "⚱",
        "cost": "动作", "key": "0", "kind": "bonus", "available": True,
    })

    return bar[:10]
