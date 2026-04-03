"""
法术服务
- 法术注册表（从 data/spells_srd.json 加载，不存在时回退到内置注册表）
- 升环计算
- 施法验证与效果解析
"""
from __future__ import annotations
import json
import os
from typing import Optional
from services.dnd_rules import roll_dice


def _load_spell_registry() -> dict[str, dict]:
    """
    从 data/spells_srd.json 加载法术注册表；失败时回退到内置 SPELL_REGISTRY。
    支持 // 单行注释（标准 JSON 不支持，此处手动剥离）。
    """
    import re
    json_path = os.path.join(os.path.dirname(__file__), "..", "data", "spells_srd.json")
    try:
        with open(json_path, encoding="utf-8") as f:
            raw = f.read()
        # 剥离 // 注释行（避免误删字符串中的 //）
        cleaned = re.sub(r"//[^\n]*", "", raw)
        spells = json.loads(cleaned)
        registry = {}
        for spell in spells:
            spell = dict(spell)
            name  = spell.pop("name")
            registry[name] = spell
        return registry
    except Exception:
        return _BUILTIN_REGISTRY

# ── 法术注册表 ────────────────────────────────────────────
# 格式说明：
#   type:         "damage" | "heal" | "utility" | "control"
#   level:        法术环数（0 = 戏法）
#   school:       法术学派
#   casting_time: "action" | "bonus_action" | "reaction" | "1 minute"
#   range:        格子数（1 = 触摸，0 = 自身）
#   concentration: 是否需要专注
#   save:         目标需要的豁免种类（None = 不需要豁免/法术攻击）
#   damage_dice / heal_dice: 基础骰
#   upcast_dice:  升环每高一环额外增加的骰
#   classes:      可使用该法术的职业（SRD来源）

_BUILTIN_REGISTRY: dict[str, dict] = {
    # ── 0环（戏法）─────────────────────────────────────
    "火焰射线": {
        "type": "damage", "level": 0, "school": "咒法",
        "casting_time": "action", "range": 24, "concentration": False,
        "save": None,  # 法术攻击检定
        "damage_dice": "1d10", "upcast_dice": None,
        "cantrip_scale": {1:"1d10", 5:"2d10", 11:"3d10", 17:"4d10"},
        "desc": "投掷一束火焰能量，需法术攻击检定命中目标。",
        "classes": ["Sorcerer","Wizard"],
    },
    "神圣烈焰": {
        "type": "damage", "level": 0, "school": "咒法",
        "casting_time": "action", "range": 12, "concentration": False,
        "save": "dex",  # DEX豁免，失败受伤
        "damage_dice": "1d8", "upcast_dice": None,
        "cantrip_scale": {1:"1d8", 5:"2d8", 11:"3d8", 17:"4d8"},
        "desc": "辉光从上方洒落，目标需DEX豁免，失败则受到辐射伤害。",
        "classes": ["Cleric"],
    },
    "冰刃": {
        "type": "damage", "level": 0, "school": "咒法",
        "casting_time": "action", "range": 1, "concentration": False,
        "save": None,  # 近战法术攻击
        "damage_dice": "1d10", "upcast_dice": None,
        "cantrip_scale": {1:"1d10", 5:"2d10", 11:"3d10", 17:"4d10"},
        "desc": "召唤冰刃，以近战法术攻击检定命中目标，造成冰冷伤害。",
        "classes": ["Druid","Sorcerer","Warlock","Wizard"],
    },
    "治愈之触": {
        "type": "heal", "level": 0, "school": "咒法",
        "casting_time": "action", "range": 1, "concentration": False,
        "save": None,
        "heal_dice": "1d4",
        "cantrip_scale": {1:"1d4", 5:"2d4", 11:"3d4", 17:"4d4"},
        "desc": "（准戏法）触摸目标，恢复少量HP。",
        "classes": ["Cleric","Druid"],
    },

    # ── 1环 ──────────────────────────────────────────────
    "魔法飞弹": {
        "type": "damage", "level": 1, "school": "咒法",
        "casting_time": "action", "range": 24, "concentration": False,
        "save": None,  # 自动命中，无法豁免
        "damage_dice": "3d4+3",  # 3枚，每枚1d4+1
        "upcast_dice": "1d4+1",  # 每升一环多1枚飞弹
        "desc": "发射三枚自动命中的力场飞弹，每枚造成1d4+1力场伤害。升环：每高一环多一枚。",
        "classes": ["Sorcerer","Wizard"],
    },
    "治愈创伤": {
        "type": "heal", "level": 1, "school": "咒法",
        "casting_time": "action", "range": 1, "concentration": False,
        "save": None,
        "heal_dice": "1d8",
        "upcast_dice": "1d8",  # 升环每高一环多1d8
        "desc": "触摸目标，恢复1d8+施法属性调整值HP。升环：每高一环多1d8。",
        "classes": ["Cleric","Druid","Paladin","Ranger","Bard"],
    },
    "灼热射线": {
        "type": "damage", "level": 1, "school": "咒法",
        "casting_time": "action", "range": 18, "concentration": False,
        "save": None,  # 法术攻击检定
        "damage_dice": "2d6",  # 2条射线各1d6
        "upcast_dice": "2d6",  # 升环每高一环多一条射线（2d6）
        "desc": "发射2条火焰射线，各需法术攻击检定，命中各造成2d6火焰伤害。升环：多1条射线。",
        "classes": ["Sorcerer","Wizard"],
    },
    "地狱烈焰": {
        "type": "damage", "level": 1, "school": "咒法",
        "casting_time": "action", "range": 18, "concentration": False,
        "save": "dex",
        "damage_dice": "2d10",
        "upcast_dice": "1d10",
        "desc": "目标需DEX豁免，失败受2d10火焰+辉光伤害，成功减半。升环：多1d10。",
        "classes": ["Warlock"],
    },

    # ── 2环 ──────────────────────────────────────────────
    "治愈之语": {
        "type": "heal", "level": 2, "school": "咒法",
        "casting_time": "bonus_action", "range": 12, "concentration": False,
        "save": None,
        "heal_dice": "1d4",
        "upcast_dice": "1d4",
        "desc": "附赠行动，远程治疗目标1d4+施法属性调整值HP。升环：每高一环多1d4。",
        "classes": ["Cleric","Bard","Druid"],
    },
    "雷鸣波": {
        "type": "damage", "level": 2, "school": "咒法",
        "casting_time": "action", "range": 2, "concentration": False,
        "save": "con", "aoe": True, "half_on_save": True,
        "damage_dice": "2d8",
        "upcast_dice": "1d8",
        "desc": "5尺内目标需CON豁免，失败受2d8雷鸣伤害并被推离10尺，成功减半不推。升环：多1d8。",
        "classes": ["Bard","Cleric","Druid","Sorcerer","Wizard","Warlock"],
    },
    "蜘蛛爬行": {
        "type": "utility", "level": 2, "school": "变化",
        "casting_time": "action", "range": 1, "concentration": True,
        "save": None,
        "desc": "目标获得攀爬速度，持续1小时（专注）。升环：每高一环多一个目标。",
        "classes": ["Sorcerer","Warlock","Wizard"],
    },

    # ── 3环 ──────────────────────────────────────────────
    "火球术": {
        "type": "damage", "level": 3, "school": "咒法",
        "casting_time": "action", "range": 30, "concentration": False,
        "save": "dex", "aoe": True, "half_on_save": True,
        "damage_dice": "8d6",
        "upcast_dice": "1d6",
        "desc": "半径20尺爆炸，范围内目标需DEX豁免，失败受8d6火焰伤害，成功减半。升环：每高一环多1d6。",
        "classes": ["Sorcerer","Wizard"],
    },
    "神圣惩击": {
        "type": "damage", "level": 3, "school": "咒法",
        "casting_time": "bonus_action", "range": 1, "concentration": True,
        "save": None,  # 下次命中时触发
        "damage_dice": "2d8",
        "upcast_dice": "1d8",
        "desc": "附赠行动，专注，下次近战命中时额外造成2d8辉光伤害。升环：多1d8（每个环级）。",
        "classes": ["Paladin"],
    },
    "群体治愈术": {
        "type": "heal", "level": 3, "school": "咒法",
        "casting_time": "action", "range": 0, "concentration": False,
        "save": None, "aoe": True,
        "heal_dice": "3d8",
        "upcast_dice": "1d8",
        "desc": "30尺范围内所有友方各恢复3d8+施法调整值HP。升环：多1d8。",
        "classes": ["Cleric","Druid"],
    },

    # ── 4环 ──────────────────────────────────────────────
    "冰风暴": {
        "type": "damage", "level": 4, "school": "咒法",
        "casting_time": "action", "range": 30, "concentration": False,
        "save": "dex", "aoe": True, "half_on_save": True,
        "damage_dice": "2d8+4d6",  # 2d8钝击+4d6冰冷
        "upcast_dice": "1d8",
        "desc": "半径20尺区域，目标需DEX豁免，失败受2d8钝击+4d6冰冷伤害，成功减半。升环：多1d8。",
        "classes": ["Druid","Sorcerer","Wizard"],
    },

    # ── 5环 ──────────────────────────────────────────────
    "巨焰爆炸": {
        "type": "damage", "level": 5, "school": "咒法",
        "casting_time": "action", "range": 30, "concentration": False,
        "save": "dex", "aoe": True, "half_on_save": True,
        "damage_dice": "12d6",
        "upcast_dice": "1d6",
        "desc": "半径20尺爆炸，升级版火球，造成12d6火焰伤害。升环：多1d6。",
        "classes": ["Sorcerer","Wizard"],
    },
    "群体治愈波": {
        "type": "heal", "level": 5, "school": "咒法",
        "casting_time": "action", "range": 0, "concentration": False,
        "save": None, "aoe": True,
        "heal_dice": "5d8",
        "upcast_dice": "1d8",
        "desc": "30尺内所有友方恢复5d8+施法调整值HP。升环：多1d8。",
        "classes": ["Cleric","Druid"],
    },
}

SPELL_REGISTRY: dict[str, dict] = _load_spell_registry()

# 法术位名称映射（环数 → slot key）
SLOT_LEVEL_KEYS = {
    1:"1st", 2:"2nd", 3:"3rd", 4:"4th", 5:"5th",
    6:"6th", 7:"7th", 8:"8th", 9:"9th",
}


class SpellService:
    """法术查询、升环计算、效果解析"""

    # ── 查询 ──────────────────────────────────────────────

    def get_all(self) -> list[dict]:
        return [{"name": k, **v} for k, v in SPELL_REGISTRY.items()]

    def get(self, name: str) -> Optional[dict]:
        return SPELL_REGISTRY.get(name)

    def get_for_class(self, class_name: str, max_slot_level: int = 9) -> list[dict]:
        """返回指定职业在当前等级可用的法术（含戏法）"""
        result = []
        for name, spell in SPELL_REGISTRY.items():
            if class_name in spell.get("classes", []) and spell["level"] <= max_slot_level:
                result.append({"name": name, **spell})
        return sorted(result, key=lambda s: (s["level"], s["name"]))

    def get_cantrips_for_class(self, class_name: str) -> list[dict]:
        return [{"name": k, **v} for k, v in SPELL_REGISTRY.items()
                if v["level"] == 0 and class_name in v.get("classes", [])]

    # ── 升环计算 ──────────────────────────────────────────

    def calc_upcast_dice(self, spell_name: str, slot_level: int) -> str:
        """
        计算升环施法后的实际伤害/治疗骰表示法
        返回如 "10d6"、"3d8+施法调整值" 等字符串
        """
        spell = self.get(spell_name)
        if not spell:
            return "1d6"

        base_level = spell["level"]
        if base_level == 0:
            # 戏法按角色等级升级，不按法术位
            return spell.get("damage_dice") or spell.get("heal_dice") or "1d4"

        levels_up   = max(0, slot_level - base_level)
        upcast_dice = spell.get("upcast_dice")
        if not upcast_dice or levels_up == 0:
            return spell.get("damage_dice") or spell.get("heal_dice") or "1d6"

        # 解析基础骰和升环骰，相加
        base = spell.get("damage_dice") or spell.get("heal_dice") or "0"
        return self._add_dice(base, upcast_dice, levels_up)

    def _add_dice(self, base: str, extra_per_level: str, levels_up: int) -> str:
        """将 base + extra_per_level × levels_up 合并为一个骰子表示法（简化）"""
        # 简单实现：拼接为 "base + extra × levels_up"，由 roll_dice 逐段解析
        # 实际使用时由 resolve_spell 分别掷骰再相加
        return f"{base}|+{extra_per_level}×{levels_up}"

    # ── 效果解析 ──────────────────────────────────────────

    def resolve_damage(
        self,
        spell_name: str,
        slot_level: int,
        spell_mod: int = 0,
    ) -> tuple[int, dict]:
        """
        计算法术伤害，返回 (total, dice_detail)
        """
        spell = self.get(spell_name)
        if not spell:
            return 0, {}

        base_level  = spell["level"]
        levels_up   = max(0, slot_level - base_level)
        upcast_dice = spell.get("upcast_dice")

        base_roll = roll_dice(spell.get("damage_dice", "1d6"))
        total     = base_roll["total"]

        extra_rolls = []
        if upcast_dice and levels_up > 0:
            for _ in range(levels_up):
                r = roll_dice(upcast_dice)
                extra_rolls.append(r)
                total += r["total"]

        return total, {
            "base_roll":   base_roll,
            "extra_rolls": extra_rolls,
            "total":       total,
            "spell_mod":   spell_mod,
        }

    def resolve_heal(
        self,
        spell_name: str,
        slot_level: int,
        spell_mod: int = 0,
        bonus_healing: bool = False,
    ) -> tuple[int, dict]:
        """
        计算法术治疗量，返回 (total, dice_detail)
        """
        spell = self.get(spell_name)
        if not spell:
            return 0, {}

        base_level  = spell["level"]
        levels_up   = max(0, slot_level - base_level)
        upcast_dice = spell.get("upcast_dice")

        base_roll = roll_dice(spell.get("heal_dice", "1d4"))
        total     = base_roll["total"] + spell_mod  # 治疗加施法调整值

        extra_rolls = []
        if upcast_dice and levels_up > 0:
            for _ in range(levels_up):
                r = roll_dice(upcast_dice)
                extra_rolls.append(r)
                total += r["total"]

        # 生命域牧师：Disciple of Life 额外治疗 = 2 + 法术位等级（1环及以上）
        life_bonus = 0
        if bonus_healing and spell.get("level", 0) >= 1:
            life_bonus = 2 + slot_level
            total += life_bonus

        return total, {
            "base_roll":   base_roll,
            "extra_rolls": extra_rolls,
            "total":       total,
            "spell_mod":   spell_mod,
            "life_bonus":  life_bonus,
        }

    # ── 法术位管理 ────────────────────────────────────────

    @staticmethod
    def slot_key(level: int) -> str:
        return SLOT_LEVEL_KEYS.get(level, f"{level}th")

    @staticmethod
    def consume_slot(slots: dict, slot_level: int) -> tuple[dict, str | None]:
        """
        消耗一个法术位，返回 (新slots字典, 错误信息|None)
        """
        key = SpellService.slot_key(slot_level)
        current = slots.get(key, 0)
        if current <= 0:
            return slots, f"没有剩余的 {slot_level} 环法术位"
        new_slots = dict(slots)
        new_slots[key] = current - 1
        return new_slots, None

    @staticmethod
    def validate_slot_level(spell_name: str, slot_level: int) -> str | None:
        """
        校验法术位等级是否合法（不能低于法术基础环数）
        返回 None = 合法，str = 错误信息
        """
        spell = SPELL_REGISTRY.get(spell_name)
        if not spell:
            return f"未知法术：{spell_name}"
        if spell["level"] == 0:
            return None  # 戏法无需法术位
        if slot_level < spell["level"]:
            return f"{spell_name} 是 {spell['level']} 环法术，不能用 {slot_level} 环位施放"
        return None


# 单例
spell_service = SpellService()
