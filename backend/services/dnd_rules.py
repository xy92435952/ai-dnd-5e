"""
DnD 5e 规则计算引擎
所有规则计算在本地完成，不依赖 AI
"""
import random
from typing import Optional

# ── 基础数据 ──────────────────────────────────────────────

ABILITY_SCORE_COSTS = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]

HIT_DICE = {
    "Barbarian": 12, "Fighter": 10, "Paladin": 10, "Ranger": 10,
    "Monk": 8, "Rogue": 8, "Bard": 8, "Cleric": 8, "Druid": 8, "Warlock": 8,
    "Sorcerer": 6, "Wizard": 6,
}

BASE_AC = {
    "Fighter": 16, "Paladin": 18, "Barbarian": 14,
    "Rogue": 13, "Ranger": 14, "Monk": 14,
    "Wizard": 12, "Sorcerer": 12, "Warlock": 13,
    "Cleric": 16, "Druid": 14, "Bard": 13,
}

SPELLCASTING_ABILITY = {
    "Wizard": "int", "Sorcerer": "cha", "Warlock": "cha",
    "Cleric": "wis", "Druid": "wis", "Bard": "cha",
    "Paladin": "cha", "Ranger": "wis",
}

# ── 法术位表（按施法者类型分三张表）────────────────────────

# 全职施法者：法师/牧师/德鲁伊/术士/吟游诗人（1-9环，按等级）
SPELL_SLOTS_FULL = {
    1:  {"1st":2,"2nd":0,"3rd":0,"4th":0,"5th":0,"6th":0,"7th":0,"8th":0,"9th":0},
    2:  {"1st":3,"2nd":0,"3rd":0,"4th":0,"5th":0,"6th":0,"7th":0,"8th":0,"9th":0},
    3:  {"1st":4,"2nd":2,"3rd":0,"4th":0,"5th":0,"6th":0,"7th":0,"8th":0,"9th":0},
    4:  {"1st":4,"2nd":3,"3rd":0,"4th":0,"5th":0,"6th":0,"7th":0,"8th":0,"9th":0},
    5:  {"1st":4,"2nd":3,"3rd":2,"4th":0,"5th":0,"6th":0,"7th":0,"8th":0,"9th":0},
    6:  {"1st":4,"2nd":3,"3rd":3,"4th":0,"5th":0,"6th":0,"7th":0,"8th":0,"9th":0},
    7:  {"1st":4,"2nd":3,"3rd":3,"4th":1,"5th":0,"6th":0,"7th":0,"8th":0,"9th":0},
    8:  {"1st":4,"2nd":3,"3rd":3,"4th":2,"5th":0,"6th":0,"7th":0,"8th":0,"9th":0},
    9:  {"1st":4,"2nd":3,"3rd":3,"4th":3,"5th":1,"6th":0,"7th":0,"8th":0,"9th":0},
    10: {"1st":4,"2nd":3,"3rd":3,"4th":3,"5th":2,"6th":0,"7th":0,"8th":0,"9th":0},
    11: {"1st":4,"2nd":3,"3rd":3,"4th":3,"5th":2,"6th":1,"7th":0,"8th":0,"9th":0},
    12: {"1st":4,"2nd":3,"3rd":3,"4th":3,"5th":2,"6th":1,"7th":0,"8th":0,"9th":0},
    13: {"1st":4,"2nd":3,"3rd":3,"4th":3,"5th":2,"6th":1,"7th":1,"8th":0,"9th":0},
    14: {"1st":4,"2nd":3,"3rd":3,"4th":3,"5th":2,"6th":1,"7th":1,"8th":0,"9th":0},
    15: {"1st":4,"2nd":3,"3rd":3,"4th":3,"5th":2,"6th":1,"7th":1,"8th":1,"9th":0},
    16: {"1st":4,"2nd":3,"3rd":3,"4th":3,"5th":2,"6th":1,"7th":1,"8th":1,"9th":0},
    17: {"1st":4,"2nd":3,"3rd":3,"4th":3,"5th":2,"6th":1,"7th":1,"8th":1,"9th":1},
    18: {"1st":4,"2nd":3,"3rd":3,"4th":3,"5th":3,"6th":1,"7th":1,"8th":1,"9th":1},
    19: {"1st":4,"2nd":3,"3rd":3,"4th":3,"5th":3,"6th":2,"7th":1,"8th":1,"9th":1},
    20: {"1st":4,"2nd":3,"3rd":3,"4th":3,"5th":3,"6th":2,"7th":2,"8th":1,"9th":1},
}

# 半职施法者：圣武士/游侠（2级起，最高5环）
SPELL_SLOTS_HALF = {
    1:  {"1st":0,"2nd":0,"3rd":0,"4th":0,"5th":0},
    2:  {"1st":2,"2nd":0,"3rd":0,"4th":0,"5th":0},
    3:  {"1st":3,"2nd":0,"3rd":0,"4th":0,"5th":0},
    4:  {"1st":3,"2nd":0,"3rd":0,"4th":0,"5th":0},
    5:  {"1st":4,"2nd":2,"3rd":0,"4th":0,"5th":0},
    6:  {"1st":4,"2nd":2,"3rd":0,"4th":0,"5th":0},
    7:  {"1st":4,"2nd":3,"3rd":0,"4th":0,"5th":0},
    8:  {"1st":4,"2nd":3,"3rd":0,"4th":0,"5th":0},
    9:  {"1st":4,"2nd":3,"3rd":2,"4th":0,"5th":0},
    10: {"1st":4,"2nd":3,"3rd":2,"4th":0,"5th":0},
    11: {"1st":4,"2nd":3,"3rd":3,"4th":0,"5th":0},
    12: {"1st":4,"2nd":3,"3rd":3,"4th":0,"5th":0},
    13: {"1st":4,"2nd":3,"3rd":3,"4th":1,"5th":0},
    14: {"1st":4,"2nd":3,"3rd":3,"4th":1,"5th":0},
    15: {"1st":4,"2nd":3,"3rd":3,"4th":2,"5th":0},
    16: {"1st":4,"2nd":3,"3rd":3,"4th":2,"5th":0},
    17: {"1st":4,"2nd":3,"3rd":3,"4th":3,"5th":1},
    18: {"1st":4,"2nd":3,"3rd":3,"4th":3,"5th":1},
    19: {"1st":4,"2nd":3,"3rd":3,"4th":3,"5th":2},
    20: {"1st":4,"2nd":3,"3rd":3,"4th":3,"5th":2},
}

# 邪术师契约魔法（法术位少但等级高，短休复原）
# {"slots": 位数, "slot_level": 法术位等级}
SPELL_SLOTS_WARLOCK = {
    1:  {"slots":1,"slot_level":"1st"},
    2:  {"slots":2,"slot_level":"1st"},
    3:  {"slots":2,"slot_level":"2nd"},
    4:  {"slots":2,"slot_level":"2nd"},
    5:  {"slots":2,"slot_level":"3rd"},
    6:  {"slots":2,"slot_level":"3rd"},
    7:  {"slots":2,"slot_level":"4th"},
    8:  {"slots":2,"slot_level":"4th"},
    9:  {"slots":2,"slot_level":"5th"},
    10: {"slots":2,"slot_level":"5th"},
    11: {"slots":3,"slot_level":"5th"},
    12: {"slots":3,"slot_level":"5th"},
    13: {"slots":3,"slot_level":"5th"},
    14: {"slots":3,"slot_level":"5th"},
    15: {"slots":3,"slot_level":"5th"},
    16: {"slots":3,"slot_level":"5th"},
    17: {"slots":4,"slot_level":"5th"},
    18: {"slots":4,"slot_level":"5th"},
    19: {"slots":4,"slot_level":"5th"},
    20: {"slots":4,"slot_level":"5th"},
}

# 职业 → 施法者类型
CASTER_TYPE = {
    "Wizard": "full", "Cleric": "full", "Druid": "full",
    "Sorcerer": "full", "Bard": "full",
    "Paladin": "half", "Ranger": "half",
    "Warlock": "pact",
    # 非施法者
    "Fighter": None, "Barbarian": None, "Monk": None,
    "Rogue": None,
}

# 各职业每级可知/可备戏法数
CANTRIPS_KNOWN = {
    "Wizard":   {1:3, 4:4, 10:5},
    "Cleric":   {1:3, 4:4, 10:5},
    "Druid":    {1:2, 4:3, 10:4},
    "Sorcerer": {1:4, 4:5, 10:6},
    "Bard":     {1:2, 4:3, 10:4},
    "Warlock":  {1:2, 4:3, 10:4},
}

# 各施法职业1级时的起始已知法术数（不含戏法）
STARTING_SPELLS_COUNT: dict[str, int] = {
    "Wizard":    6,   # 法术书：3+INT修正，简化为6
    "Cleric":    4,   # 准备施法，取前4个
    "Druid":     4,
    "Sorcerer":  2,
    "Bard":      4,
    "Warlock":   2,
    "Paladin":   0,   # 半施法者，1级无法术位
    "Ranger":    0,
    "Fighter":   0,
    "Barbarian": 0,
    "Rogue":     0,
    "Monk":      0,
}

# 有施法能力的职业（戏法或已知法术 > 0）
SPELLCASTER_CLASSES = [
    "Wizard", "Cleric", "Druid", "Sorcerer", "Bard", "Warlock",
]

# ── 种族能力值加值表（SRD 5.1）────────────────────────────

RACIAL_ABILITY_BONUSES: dict[str, dict[str, int]] = {
    # 英文名
    "Human":      {"str":1,"dex":1,"con":1,"int":1,"wis":1,"cha":1},
    "Elf":        {"dex":2,"int":1},        # 高精灵，SRD默认
    "Dwarf":      {"con":2},                # 丘陵矮人（+1 WIS 含在种族特性里）
    "Halfling":   {"dex":2},
    "Gnome":      {"int":2},                # 森林侏儒 +1 DEX 含在种族特性里
    "Half-Elf":   {"cha":2,"dex":1,"wis":1},  # 另外+1+1玩家自选，默认给DEX+WIS
    "Half-Orc":   {"str":2,"con":1},
    "Dragonborn": {"str":2,"cha":1},
    "Tiefling":   {"int":1,"cha":2},
    # 中文名（相同数值）
    "人类":   {"str":1,"dex":1,"con":1,"int":1,"wis":1,"cha":1},
    "精灵":   {"dex":2,"int":1},
    "矮人":   {"con":2},
    "半身人": {"dex":2},
    "侏儒":   {"int":2},
    "半精灵": {"cha":2,"dex":1,"wis":1},
    "半兽人": {"str":2,"con":1},
    "龙裔":   {"str":2,"cha":1},
    "提夫林": {"int":1,"cha":2},
}

# ── 职业豁免熟练（SRD 标准）────────────────────────────────

CLASS_SAVE_PROFICIENCIES: dict[str, list[str]] = {
    "Barbarian": ["str","con"],
    "Fighter":   ["str","con"],
    "Paladin":   ["wis","cha"],
    "Ranger":    ["str","dex"],
    "Rogue":     ["dex","int"],
    "Monk":      ["str","dex"],
    "Cleric":    ["wis","cha"],
    "Druid":     ["int","wis"],
    "Bard":      ["dex","cha"],
    "Wizard":    ["int","wis"],
    "Sorcerer":  ["con","cha"],
    "Warlock":   ["wis","cha"],
}

# ── 职业技能选择（可选项 + 选择数量）─────────────────────

ALL_SKILLS = [
    "运动","杂技","巧手","隐匿",
    "奥秘","历史","调查","自然","宗教",
    "驯兽","洞悉","医疗","感知","求生",
    "欺瞒","恐吓","表演","说服",
]

CLASS_SKILL_CHOICES: dict[str, dict] = {
    "Barbarian": {"count":2, "options":["运动","驯兽","恐吓","自然","感知","求生"]},
    "Fighter":   {"count":2, "options":["杂技","驯兽","历史","洞悉","恐吓","感知","运动","求生"]},
    "Paladin":   {"count":2, "options":["运动","洞悉","恐吓","医疗","说服","宗教"]},
    "Ranger":    {"count":3, "options":["驯兽","运动","洞悉","调查","自然","感知","隐匿","求生"]},
    "Rogue":     {"count":4, "options":["杂技","运动","欺瞒","洞悉","恐吓","调查","感知","表演","说服","巧手","隐匿"]},
    "Monk":      {"count":2, "options":["杂技","运动","历史","洞悉","宗教","隐匿"]},
    "Cleric":    {"count":2, "options":["历史","洞悉","医疗","说服","宗教"]},
    "Druid":     {"count":2, "options":["奥秘","驯兽","洞悉","医疗","自然","感知","宗教","求生"]},
    "Bard":      {"count":3, "options": ALL_SKILLS},  # 吟游诗人可选任意技能
    "Wizard":    {"count":2, "options":["奥秘","历史","洞悉","调查","医疗","宗教"]},
    "Sorcerer":  {"count":2, "options":["奥秘","欺瞒","洞悉","恐吓","说服","宗教"]},
    "Warlock":   {"count":2, "options":["奥秘","历史","调查","自然","宗教"]},
}

RACES = [
    "人类", "精灵", "矮人", "半身人", "侏儒", "半精灵", "半兽人", "龙裔", "提夫林",
]

CLASSES = [
    "战士", "圣武士", "野蛮人", "游侠", "游荡者", "武僧",
    "牧师", "德鲁伊", "吟游诗人",
    "法师", "术士", "邪术师",
]

BACKGROUNDS = [
    "侍从", "罪犯", "民间英雄", "贵族", "学者", "士兵", "娱乐表演者", "隐士",
    "骗子", "异乡人", "公会工匠", "流浪儿",
]

ALIGNMENTS = [
    "守序善良", "中立善良", "混乱善良",
    "守序中立", "绝对中立", "混乱中立",
    "守序邪恶", "中立邪恶", "混乱邪恶",
]

# ── 技能 → 关联能力值映射 ──────────────────────────────────

SKILL_ABILITY_MAP: dict[str, str] = {
    "运动": "str",
    "杂技": "dex", "巧手": "dex", "隐匿": "dex",
    "奥秘": "int", "历史": "int", "调查": "int", "自然": "int", "宗教": "int",
    "驯兽": "wis", "洞悉": "wis", "医疗": "wis", "感知": "wis", "求生": "wis",
    "欺瞒": "cha", "恐吓": "cha", "表演": "cha", "说服": "cha",
    # English aliases
    "Athletics": "str",
    "Acrobatics": "dex", "Sleight of Hand": "dex", "Stealth": "dex",
    "Arcana": "int", "History": "int", "Investigation": "int",
    "Nature": "int", "Religion": "int",
    "Animal Handling": "wis", "Insight": "wis", "Medicine": "wis",
    "Perception": "wis", "Survival": "wis",
    "Deception": "cha", "Intimidation": "cha",
    "Performance": "cha", "Persuasion": "cha",
}

# ── 战斗风格（Fighter Lv1, Paladin Lv2, Ranger Lv2）────────

FIGHTING_STYLES = {
    "Archery":               {"zh": "射箭", "desc": "远程武器攻击检定+2", "ranged_attack_bonus": 2},
    "Defense":               {"zh": "防御", "desc": "穿着护甲时AC+1", "ac_bonus": 1},
    "Dueling":               {"zh": "决斗", "desc": "单手持近战武器时伤害+2", "melee_damage_bonus": 2},
    "Great Weapon Fighting": {"zh": "巨武器战斗", "desc": "双手武器伤害骰1或2可重掷（取新值）", "reroll_low": True},
    "Protection":            {"zh": "护卫", "desc": "持盾时用反应使相邻敌人攻击盟友劣势", "reaction_protection": True},
    "Two-Weapon Fighting":   {"zh": "双武器战斗", "desc": "双持时副手攻击也加属性修正", "two_weapon_fighting": True},
}

FIGHTING_STYLE_CLASSES = {
    "Fighter": {"level": 1, "styles": list(FIGHTING_STYLES.keys())},
    "Paladin": {"level": 2, "styles": ["Defense", "Dueling", "Great Weapon Fighting", "Protection"]},
    "Ranger":  {"level": 2, "styles": ["Archery", "Defense", "Dueling", "Two-Weapon Fighting"]},
}

# ── 野兽形态表（Moon Druid Wild Shape）──────────────────────

WILD_SHAPE_FORMS = {
    "Wolf":    {"cr": 0.25, "hp": 11, "ac": 13, "speed": 40, "attack": {"name": "撕咬", "bonus": 4, "damage": "2d4+2", "type": "穿刺"}},
    "Bear":    {"cr": 1, "hp": 34, "ac": 11, "speed": 40, "attack": {"name": "爪击", "bonus": 5, "damage": "2d6+4", "type": "挥砍"}, "multiattack": 2},
    "Giant Spider": {"cr": 1, "hp": 26, "ac": 14, "speed": 30, "attack": {"name": "毒牙", "bonus": 5, "damage": "1d8+3", "type": "穿刺"}},
    "Giant Eagle": {"cr": 1, "hp": 26, "ac": 13, "speed": 10, "fly": 80, "attack": {"name": "利爪", "bonus": 5, "damage": "2d6+3", "type": "挥砍"}},
    "Dire Wolf": {"cr": 1, "hp": 37, "ac": 14, "speed": 50, "attack": {"name": "撕咬", "bonus": 5, "damage": "2d6+3", "type": "穿刺"}},
    "Giant Scorpion": {"cr": 3, "hp": 52, "ac": 15, "speed": 40, "attack": {"name": "钳击", "bonus": 4, "damage": "1d8+2", "type": "钝击"}, "multiattack": 3},
    "Fire Elemental": {"cr": 5, "hp": 102, "ac": 13, "speed": 50, "attack": {"name": "触碰", "bonus": 6, "damage": "2d6+3", "type": "火焰"}, "multiattack": 2, "immunities": ["火焰"], "resistances": ["钝击","穿刺","挥砍"]},
    "Earth Elemental": {"cr": 5, "hp": 126, "ac": 17, "speed": 30, "attack": {"name": "猛击", "bonus": 8, "damage": "2d8+5", "type": "钝击"}, "multiattack": 2, "immunities": ["毒素"], "resistances": ["钝击","穿刺","挥砍"]},
}

# ── 狂野魔法涌动表（Wild Magic Surge）───────────────────────

WILD_MAGIC_TABLE = [
    "你身上的皮肤变为亮蓝色，持续10分钟",
    "你周围30尺内每个生物都变得隐形，持续到下一回合",
    "你在接下来1分钟内对所有伤害获得抗性",
    "你施放了以自己为中心的火球术（3级）",
    "你恢复了一个已消耗的最低环法术位",
    "你周围30尺内的所有门窗打开",
    "你获得30天的隐形术效果，但在攻击或施法时消失",
    "你身上长出翅膀，获得30尺飞行速度，持续1分钟",
    "你对一个随机目标施放了困惑术",
    "你恢复 2d10 点生命值",
    "你变成一盆盆栽，持续到下一回合开始。你处于失能和速度为0的状态",
    "你周围10尺内每个生物受到1d10力场伤害",
    "你下一次施法不消耗法术位",
    "你的年龄变化 1d10 年（偶数变老，奇数变年轻）",
    "1d6 只猫围着你出现",
    "你获得2d10临时生命值",
    "你和一个随机可见生物互换位置",
    "你周围30尺内下起小雨，持续1分钟",
    "你的头发脱落，24小时后重新长出",
    "你接下来1分钟每说一句话都会冒出肥皂泡",
]


def roll_wild_magic_surge() -> dict:
    """Roll on the wild magic surge table. Returns effect description and any mechanical impact."""
    idx = random.randint(0, len(WILD_MAGIC_TABLE) - 1)
    effect = WILD_MAGIC_TABLE[idx]
    # Some effects have mechanical impact
    mechanical = {}
    if "火球术" in effect:
        mechanical = {"type": "damage", "damage": "8d6", "damage_type": "火焰", "range": "self_aoe_20ft"}
    elif "恢复" in effect and "法术位" in effect:
        mechanical = {"type": "recover_slot", "level": 1}
    elif "恢复" in effect and "生命" in effect:
        mechanical = {"type": "heal", "dice": "2d10"}
    elif "临时生命" in effect:
        mechanical = {"type": "temp_hp", "dice": "2d10"}
    elif "力场伤害" in effect:
        mechanical = {"type": "damage", "damage": "1d10", "damage_type": "力场", "range": "self_aoe_10ft"}
    elif "抗性" in effect:
        mechanical = {"type": "resistance_all", "duration": "1min"}
    elif "失能" in effect:
        mechanical = {"type": "condition", "condition": "失能", "duration": "1round"}
    return {"effect": effect, "mechanical": mechanical, "index": idx}


# ── 武器表（SRD 5.1）────────────────────────────────────────

WEAPONS = {
    # ── 简易近战 ──
    "Club":         {"zh": "棍棒",   "damage": "1d4",  "damage_type": "bludgeoning", "type": "simple_melee",  "weight": 2,  "cost": 1,   "properties": ["light"]},
    "Dagger":       {"zh": "匕首",   "damage": "1d4",  "damage_type": "piercing",    "type": "simple_melee",  "weight": 1,  "cost": 2,   "properties": ["finesse", "light", "thrown(20/60)"]},
    "Greatclub":    {"zh": "巨棒",   "damage": "1d8",  "damage_type": "bludgeoning", "type": "simple_melee",  "weight": 10, "cost": 2,   "properties": ["two-handed"]},
    "Handaxe":      {"zh": "手斧",   "damage": "1d6",  "damage_type": "slashing",    "type": "simple_melee",  "weight": 2,  "cost": 5,   "properties": ["light", "thrown(20/60)"]},
    "Javelin":      {"zh": "标枪",   "damage": "1d6",  "damage_type": "piercing",    "type": "simple_melee",  "weight": 2,  "cost": 5,   "properties": ["thrown(30/120)"]},
    "Light Hammer": {"zh": "轻锤",   "damage": "1d4",  "damage_type": "bludgeoning", "type": "simple_melee",  "weight": 2,  "cost": 2,   "properties": ["light", "thrown(20/60)"]},
    "Mace":         {"zh": "钉锤",   "damage": "1d6",  "damage_type": "bludgeoning", "type": "simple_melee",  "weight": 4,  "cost": 5,   "properties": []},
    "Quarterstaff": {"zh": "长棍",   "damage": "1d6",  "damage_type": "bludgeoning", "type": "simple_melee",  "weight": 4,  "cost": 2,   "properties": ["versatile(1d8)"]},
    "Sickle":       {"zh": "镰刀",   "damage": "1d4",  "damage_type": "slashing",    "type": "simple_melee",  "weight": 2,  "cost": 1,   "properties": ["light"]},
    "Spear":        {"zh": "矛",     "damage": "1d6",  "damage_type": "piercing",    "type": "simple_melee",  "weight": 3,  "cost": 1,   "properties": ["thrown(20/60)", "versatile(1d8)"]},
    # ── 简易远程 ──
    "Light Crossbow": {"zh": "轻弩",   "damage": "1d8",  "damage_type": "piercing", "type": "simple_ranged", "weight": 5,  "cost": 25,  "properties": ["ammunition", "range(80/320)", "loading", "two-handed"]},
    "Dart":           {"zh": "飞镖",   "damage": "1d4",  "damage_type": "piercing", "type": "simple_ranged", "weight": 0.25,"cost": 0.5, "properties": ["finesse", "thrown(20/60)"]},
    "Shortbow":       {"zh": "短弓",   "damage": "1d6",  "damage_type": "piercing", "type": "simple_ranged", "weight": 2,  "cost": 25,  "properties": ["ammunition", "range(80/320)", "two-handed"]},
    "Sling":          {"zh": "投石索", "damage": "1d4",  "damage_type": "bludgeoning","type": "simple_ranged","weight": 0,  "cost": 1,   "properties": ["ammunition", "range(30/120)"]},
    # ── 军用近战 ──
    "Battleaxe":    {"zh": "战斧",   "damage": "1d8",  "damage_type": "slashing",    "type": "martial_melee", "weight": 4,  "cost": 10,  "properties": ["versatile(1d10)"]},
    "Flail":        {"zh": "连枷",   "damage": "1d8",  "damage_type": "bludgeoning", "type": "martial_melee", "weight": 2,  "cost": 10,  "properties": []},
    "Glaive":       {"zh": "薙刀",   "damage": "1d10", "damage_type": "slashing",    "type": "martial_melee", "weight": 6,  "cost": 20,  "properties": ["heavy", "reach", "two-handed"]},
    "Greataxe":     {"zh": "巨斧",   "damage": "1d12", "damage_type": "slashing",    "type": "martial_melee", "weight": 7,  "cost": 30,  "properties": ["heavy", "two-handed"]},
    "Greatsword":   {"zh": "巨剑",   "damage": "2d6",  "damage_type": "slashing",    "type": "martial_melee", "weight": 6,  "cost": 50,  "properties": ["heavy", "two-handed"]},
    "Halberd":      {"zh": "戟",     "damage": "1d10", "damage_type": "slashing",    "type": "martial_melee", "weight": 6,  "cost": 20,  "properties": ["heavy", "reach", "two-handed"]},
    "Lance":        {"zh": "骑枪",   "damage": "1d12", "damage_type": "piercing",    "type": "martial_melee", "weight": 6,  "cost": 10,  "properties": ["reach", "special"]},
    "Longsword":    {"zh": "长剑",   "damage": "1d8",  "damage_type": "slashing",    "type": "martial_melee", "weight": 3,  "cost": 15,  "properties": ["versatile(1d10)"]},
    "Maul":         {"zh": "重锤",   "damage": "2d6",  "damage_type": "bludgeoning", "type": "martial_melee", "weight": 10, "cost": 10,  "properties": ["heavy", "two-handed"]},
    "Morningstar":  {"zh": "流星锤", "damage": "1d8",  "damage_type": "piercing",    "type": "martial_melee", "weight": 4,  "cost": 15,  "properties": []},
    "Pike":         {"zh": "长矛",   "damage": "1d10", "damage_type": "piercing",    "type": "martial_melee", "weight": 18, "cost": 5,   "properties": ["heavy", "reach", "two-handed"]},
    "Rapier":       {"zh": "细剑",   "damage": "1d8",  "damage_type": "piercing",    "type": "martial_melee", "weight": 2,  "cost": 25,  "properties": ["finesse"]},
    "Scimitar":     {"zh": "弯刀",   "damage": "1d6",  "damage_type": "slashing",    "type": "martial_melee", "weight": 3,  "cost": 25,  "properties": ["finesse", "light"]},
    "Shortsword":   {"zh": "短剑",   "damage": "1d6",  "damage_type": "piercing",    "type": "martial_melee", "weight": 2,  "cost": 10,  "properties": ["finesse", "light"]},
    "Trident":      {"zh": "三叉戟", "damage": "1d6",  "damage_type": "piercing",    "type": "martial_melee", "weight": 4,  "cost": 5,   "properties": ["thrown(20/60)", "versatile(1d8)"]},
    "War Pick":     {"zh": "战镐",   "damage": "1d8",  "damage_type": "piercing",    "type": "martial_melee", "weight": 2,  "cost": 5,   "properties": []},
    "Warhammer":    {"zh": "战锤",   "damage": "1d8",  "damage_type": "bludgeoning", "type": "martial_melee", "weight": 2,  "cost": 15,  "properties": ["versatile(1d10)"]},
    "Whip":         {"zh": "鞭子",   "damage": "1d4",  "damage_type": "slashing",    "type": "martial_melee", "weight": 3,  "cost": 2,   "properties": ["finesse", "reach"]},
    # ── 军用远程 ──
    "Longbow":        {"zh": "长弓",   "damage": "1d8",  "damage_type": "piercing", "type": "martial_ranged", "weight": 2, "cost": 50, "properties": ["ammunition", "range(150/600)", "heavy", "two-handed"]},
    "Hand Crossbow":  {"zh": "手弩",   "damage": "1d6",  "damage_type": "piercing", "type": "martial_ranged", "weight": 3, "cost": 75, "properties": ["ammunition", "range(30/120)", "light", "loading"]},
    "Heavy Crossbow": {"zh": "重弩",   "damage": "1d10", "damage_type": "piercing", "type": "martial_ranged", "weight": 18,"cost": 50, "properties": ["ammunition", "range(100/400)", "heavy", "loading", "two-handed"]},
}

# ── 护甲表（SRD 5.1）────────────────────────────────────────

ARMOR = {
    # 轻甲
    "Padded":       {"zh": "棉甲",     "ac": 11, "type": "light",  "dex_bonus": "full",  "stealth_disadvantage": True,  "weight": 8,  "cost": 5},
    "Leather":      {"zh": "皮甲",     "ac": 11, "type": "light",  "dex_bonus": "full",  "stealth_disadvantage": False, "weight": 10, "cost": 10},
    "Studded Leather":{"zh": "镶嵌皮甲","ac": 12,"type": "light", "dex_bonus": "full",  "stealth_disadvantage": False, "weight": 13, "cost": 45},
    # 中甲
    "Hide":         {"zh": "兽皮甲",   "ac": 12, "type": "medium", "dex_bonus": "max2",  "stealth_disadvantage": False, "weight": 12, "cost": 10},
    "Chain Shirt":  {"zh": "链甲衫",   "ac": 13, "type": "medium", "dex_bonus": "max2",  "stealth_disadvantage": False, "weight": 20, "cost": 50},
    "Scale Mail":   {"zh": "鳞甲",     "ac": 14, "type": "medium", "dex_bonus": "max2",  "stealth_disadvantage": True,  "weight": 45, "cost": 50},
    "Breastplate":  {"zh": "胸甲",     "ac": 14, "type": "medium", "dex_bonus": "max2",  "stealth_disadvantage": False, "weight": 20, "cost": 400},
    "Half Plate":   {"zh": "半身板甲", "ac": 15, "type": "medium", "dex_bonus": "max2",  "stealth_disadvantage": True,  "weight": 40, "cost": 750},
    # 重甲
    "Ring Mail":    {"zh": "环甲",     "ac": 14, "type": "heavy",  "dex_bonus": "none",  "stealth_disadvantage": True,  "weight": 40, "cost": 30},
    "Chain Mail":   {"zh": "锁甲",     "ac": 16, "type": "heavy",  "dex_bonus": "none",  "stealth_disadvantage": True,  "weight": 55, "cost": 75},
    "Splint":       {"zh": "夹板甲",   "ac": 17, "type": "heavy",  "dex_bonus": "none",  "stealth_disadvantage": True,  "weight": 60, "cost": 200},
    "Plate":        {"zh": "全身板甲", "ac": 18, "type": "heavy",  "dex_bonus": "none",  "stealth_disadvantage": True,  "weight": 65, "cost": 1500},
    # 盾牌
    "Shield":       {"zh": "盾牌",     "ac": 2,  "type": "shield", "dex_bonus": "none",  "stealth_disadvantage": False, "weight": 6,  "cost": 10},
}

# ── 起始装备（按职业，每项为可选方案）───────────────────────

STARTING_EQUIPMENT = {
    "Fighter": [
        {"label": "重甲战士", "items": [{"slot":"armor","name":"Chain Mail"},{"slot":"weapon","name":"Longsword"},{"slot":"offhand","name":"Shield"},{"slot":"weapon2","name":"Light Crossbow"},{"slot":"gear","name":"Explorer's Pack"}]},
        {"label": "轻装弓手", "items": [{"slot":"armor","name":"Leather"},{"slot":"weapon","name":"Longbow"},{"slot":"weapon2","name":"Two Handaxes"},{"slot":"gear","name":"Explorer's Pack"}]},
    ],
    "Paladin": [
        {"label": "重甲骑士", "items": [{"slot":"armor","name":"Chain Mail"},{"slot":"weapon","name":"Longsword"},{"slot":"offhand","name":"Shield"},{"slot":"gear","name":"Priest's Pack"}]},
        {"label": "双手武器", "items": [{"slot":"armor","name":"Chain Mail"},{"slot":"weapon","name":"Greatsword"},{"slot":"weapon2","name":"Five Javelins"},{"slot":"gear","name":"Explorer's Pack"}]},
    ],
    "Barbarian": [
        {"label": "双手斧",   "items": [{"slot":"weapon","name":"Greataxe"},{"slot":"weapon2","name":"Two Handaxes"},{"slot":"gear","name":"Explorer's Pack"}]},
        {"label": "双持战士", "items": [{"slot":"weapon","name":"Battleaxe"},{"slot":"weapon2","name":"Handaxe"},{"slot":"gear","name":"Explorer's Pack"}]},
    ],
    "Ranger": [
        {"label": "弓箭猎人", "items": [{"slot":"armor","name":"Scale Mail"},{"slot":"weapon","name":"Longbow"},{"slot":"weapon2","name":"Shortsword"},{"slot":"gear","name":"Explorer's Pack"}]},
        {"label": "双刀游侠", "items": [{"slot":"armor","name":"Leather"},{"slot":"weapon","name":"Shortsword"},{"slot":"weapon2","name":"Shortsword"},{"slot":"gear","name":"Explorer's Pack"}]},
    ],
    "Rogue": [
        {"label": "细剑窃贼", "items": [{"slot":"armor","name":"Leather"},{"slot":"weapon","name":"Rapier"},{"slot":"weapon2","name":"Shortbow"},{"slot":"gear","name":"Burglar's Pack"}]},
        {"label": "双刀暗杀", "items": [{"slot":"armor","name":"Leather"},{"slot":"weapon","name":"Shortsword"},{"slot":"weapon2","name":"Dagger"},{"slot":"gear","name":"Dungeoneer's Pack"}]},
    ],
    "Monk": [
        {"label": "短剑武僧", "items": [{"slot":"weapon","name":"Shortsword"},{"slot":"gear","name":"Dungeoneer's Pack"}]},
        {"label": "木棍武僧", "items": [{"slot":"weapon","name":"Quarterstaff"},{"slot":"gear","name":"Explorer's Pack"}]},
    ],
    "Cleric": [
        {"label": "锤盾牧师", "items": [{"slot":"armor","name":"Scale Mail"},{"slot":"weapon","name":"Mace"},{"slot":"offhand","name":"Shield"},{"slot":"gear","name":"Priest's Pack"}]},
        {"label": "链甲牧师", "items": [{"slot":"armor","name":"Chain Mail"},{"slot":"weapon","name":"Warhammer"},{"slot":"offhand","name":"Shield"},{"slot":"gear","name":"Explorer's Pack"}]},
    ],
    "Druid": [
        {"label": "皮甲德鲁伊", "items": [{"slot":"armor","name":"Leather"},{"slot":"offhand","name":"Shield"},{"slot":"weapon","name":"Scimitar"},{"slot":"gear","name":"Explorer's Pack"}]},
        {"label": "木盾德鲁伊", "items": [{"slot":"armor","name":"Hide"},{"slot":"offhand","name":"Shield"},{"slot":"weapon","name":"Quarterstaff"},{"slot":"gear","name":"Priest's Pack"}]},
    ],
    "Bard": [
        {"label": "细剑诗人", "items": [{"slot":"armor","name":"Leather"},{"slot":"weapon","name":"Rapier"},{"slot":"weapon2","name":"Dagger"},{"slot":"gear","name":"Entertainer's Pack"}]},
        {"label": "长剑诗人", "items": [{"slot":"armor","name":"Leather"},{"slot":"weapon","name":"Longsword"},{"slot":"gear","name":"Diplomat's Pack"}]},
    ],
    "Wizard": [
        {"label": "法杖法师", "items": [{"slot":"weapon","name":"Quarterstaff"},{"slot":"gear","name":"Scholar's Pack"},{"slot":"gear2","name":"Component Pouch"}]},
        {"label": "匕首法师", "items": [{"slot":"weapon","name":"Dagger"},{"slot":"gear","name":"Explorer's Pack"},{"slot":"gear2","name":"Arcane Focus"}]},
    ],
    "Sorcerer": [
        {"label": "轻弩术士", "items": [{"slot":"weapon","name":"Light Crossbow"},{"slot":"weapon2","name":"Dagger"},{"slot":"gear","name":"Dungeoneer's Pack"},{"slot":"gear2","name":"Arcane Focus"}]},
        {"label": "标枪术士", "items": [{"slot":"weapon","name":"Javelin"},{"slot":"weapon2","name":"Javelin"},{"slot":"gear","name":"Explorer's Pack"},{"slot":"gear2","name":"Component Pouch"}]},
    ],
    "Warlock": [
        {"label": "轻弩邪术", "items": [{"slot":"armor","name":"Leather"},{"slot":"weapon","name":"Light Crossbow"},{"slot":"weapon2","name":"Dagger"},{"slot":"gear","name":"Scholar's Pack"},{"slot":"gear2","name":"Arcane Focus"}]},
        {"label": "近战邪术", "items": [{"slot":"armor","name":"Leather"},{"slot":"weapon","name":"Rapier"},{"slot":"weapon2","name":"Dagger"},{"slot":"gear","name":"Dungeoneer's Pack"},{"slot":"gear2","name":"Component Pouch"}]},
    ],
}

# ── 背景特性（技能/语言/工具/特性）──────────────────────────

BACKGROUND_FEATURES = {
    # 中文键（前端使用）
    "侍从":       {"skills": ["洞悉", "宗教"],   "languages": 2, "tools": [],                                    "feature": "信仰庇护", "feature_desc": "你可以在神殿获得免费治疗和照料，信徒会为你提供食宿"},
    "罪犯":       {"skills": ["欺骗", "隐匿"],   "languages": 0, "tools": ["盗贼工具", "赌具"],                   "feature": "犯罪联络人", "feature_desc": "你在黑社会有可靠联络人，可传递消息和获取情报"},
    "民间英雄":   {"skills": ["驯兽", "求生"],   "languages": 0, "tools": ["工匠工具", "陆用载具"],               "feature": "质朴好客", "feature_desc": "平民会为你提供庇护和食宿，甚至冒险隐藏你"},
    "贵族":       {"skills": ["历史", "说服"],   "languages": 1, "tools": ["赌具"],                               "feature": "特权地位", "feature_desc": "贵族和上流社会欢迎你，平民尽力配合你"},
    "学者":       {"skills": ["奥秘", "历史"],   "languages": 2, "tools": [],                                    "feature": "研究者", "feature_desc": "你知道去哪里寻找信息，即使不知道答案也知道谁会知道"},
    "士兵":       {"skills": ["运动", "威吓"],   "languages": 0, "tools": ["赌具", "陆用载具"],                   "feature": "军衔", "feature_desc": "军事组织承认你的军衔，你可以指挥下级士兵"},
    "娱乐表演者": {"skills": ["杂技", "表演"],   "languages": 0, "tools": ["易容工具", "乐器"],                   "feature": "众望所归", "feature_desc": "你总能在酒馆或类似场所找到表演场地和免费食宿"},
    "隐士":       {"skills": ["医药", "宗教"],   "languages": 1, "tools": ["草药工具"],                           "feature": "发现", "feature_desc": "你在隐居中发现了一个重大秘密或真理"},
    "骗子":       {"skills": ["欺骗", "巧手"],   "languages": 0, "tools": ["易容工具", "伪造工具"],               "feature": "假身份", "feature_desc": "你有备用身份，包括文件和伪装"},
    "异乡人":     {"skills": ["运动", "求生"],   "languages": 1, "tools": ["乐器"],                               "feature": "流浪者", "feature_desc": "你拥有出色的方向感和记忆力，总能找到食物和淡水"},
    "公会工匠":   {"skills": ["洞悉", "说服"],   "languages": 1, "tools": ["工匠工具"],                           "feature": "公会会员", "feature_desc": "公会为你提供食宿、法律援助和社交网络"},
    "流浪儿":     {"skills": ["巧手", "隐匿"],   "languages": 0, "tools": ["易容工具", "盗贼工具"],               "feature": "城市秘径", "feature_desc": "你知道城市中的秘密通道，旅行速度翻倍"},
    # 英文键（兼容旧数据）
    "Acolyte":      {"skills": ["洞悉", "宗教"],   "languages": 2, "tools": [],                                    "feature": "信仰庇护", "feature_desc": "你可以在神殿获得免费治疗和照料，信徒会为你提供食宿"},
    "Criminal":     {"skills": ["欺骗", "隐匿"],   "languages": 0, "tools": ["盗贼工具", "赌具"],                   "feature": "犯罪联络人", "feature_desc": "你在黑社会有可靠联络人，可传递消息和获取情报"},
    "Soldier":      {"skills": ["运动", "威吓"],   "languages": 0, "tools": ["赌具", "陆用载具"],                   "feature": "军衔", "feature_desc": "军事组织承认你的军衔，你可以指挥下级士兵"},
    "Sage":         {"skills": ["奥秘", "历史"],   "languages": 2, "tools": [],                                    "feature": "研究者", "feature_desc": "你知道去哪里寻找信息，即使不知道答案也知道谁会知道"},
    "Folk Hero":    {"skills": ["驯兽", "求生"],   "languages": 0, "tools": ["工匠工具", "陆用载具"],               "feature": "质朴好客", "feature_desc": "平民会为你提供庇护和食宿，甚至冒险隐藏你"},
    "Noble":        {"skills": ["历史", "说服"],   "languages": 1, "tools": ["赌具"],                               "feature": "特权地位", "feature_desc": "贵族和上流社会欢迎你，平民尽力配合你"},
    "Entertainer":  {"skills": ["杂技", "表演"],   "languages": 0, "tools": ["易容工具", "乐器"],                   "feature": "众望所归", "feature_desc": "你总能在酒馆或类似场所找到表演场地和免费食宿"},
    "Hermit":       {"skills": ["医药", "宗教"],   "languages": 1, "tools": ["草药工具"],                           "feature": "发现", "feature_desc": "你在隐居中发现了一个重大秘密或真理"},
}

# ── 种族语言 ─────────────────────────────────────────────────

RACIAL_LANGUAGES = {
    "Human":      {"fixed": ["Common"],             "bonus": 1},
    "Elf":        {"fixed": ["Common", "Elvish"],    "bonus": 0},
    "Dwarf":      {"fixed": ["Common", "Dwarvish"],  "bonus": 0},
    "Halfling":   {"fixed": ["Common", "Halfling"],  "bonus": 0},
    "Gnome":      {"fixed": ["Common", "Gnomish"],   "bonus": 0},
    "Half-Elf":   {"fixed": ["Common", "Elvish"],    "bonus": 1},
    "Half-Orc":   {"fixed": ["Common", "Orc"],       "bonus": 0},
    "Dragonborn": {"fixed": ["Common", "Draconic"],  "bonus": 0},
    "Tiefling":   {"fixed": ["Common", "Infernal"],  "bonus": 0},
    # 中文别名
    "人类":       {"fixed": ["Common"],             "bonus": 1},
    "精灵":       {"fixed": ["Common", "Elvish"],    "bonus": 0},
    "矮人":       {"fixed": ["Common", "Dwarvish"],  "bonus": 0},
    "半身人":     {"fixed": ["Common", "Halfling"],  "bonus": 0},
    "侏儒":       {"fixed": ["Common", "Gnomish"],   "bonus": 0},
    "半精灵":     {"fixed": ["Common", "Elvish"],    "bonus": 1},
    "半兽人":     {"fixed": ["Common", "Orc"],       "bonus": 0},
    "龙裔":       {"fixed": ["Common", "Draconic"],  "bonus": 0},
    "提夫林":     {"fixed": ["Common", "Infernal"],  "bonus": 0},
}

ALL_LANGUAGES = [
    "Common", "Dwarvish", "Elvish", "Giant", "Gnomish", "Goblin", "Halfling", "Orc",
    "Abyssal", "Celestial", "Draconic", "Deep Speech", "Infernal", "Primordial", "Sylvan", "Undercommon",
]

# ── 法术准备类型 ─────────────────────────────────────────────

SPELL_PREPARATION_TYPE = {
    "Wizard":   "spellbook",   # 法术书：已知=法术书内容，准备=INT_mod+level
    "Cleric":   "prepared",    # 准备型：全职业表可选，准备=WIS_mod+level
    "Druid":    "prepared",    # 准备型：全职业表可选，准备=WIS_mod+level
    "Paladin":  "prepared",    # 准备型：全职业表可选，准备=CHA_mod+level/2
    "Sorcerer": "known",       # 已知型：有限已知，始终准备
    "Bard":     "known",       # 已知型：有限已知，始终准备
    "Warlock":  "known",       # 已知型：有限已知，始终准备
    "Ranger":   "known",       # 已知型：有限已知，始终准备
}

# ── 子职业额外法术 ───────────────────────────────────────────

SUBCLASS_BONUS_SPELLS = {
    "Life Domain":     {1: ["Bless", "Cure Wounds"], 3: ["Lesser Restoration", "Spiritual Weapon"], 5: ["Beacon of Hope", "Revivify"]},
    "Light Domain":    {1: ["Burning Hands", "Faerie Fire"], 3: ["Flaming Sphere", "Scorching Ray"], 5: ["Daylight", "Fireball"]},
    "War Domain":      {1: ["Divine Favor", "Shield of Faith"], 3: ["Magic Weapon", "Spiritual Weapon"], 5: ["Crusader's Mantle", "Spirit Guardians"]},
    "Devotion":        {3: ["Protection from Evil and Good", "Sanctuary"], 5: ["Lesser Restoration", "Zone of Truth"]},
    "Vengeance":       {3: ["Bane", "Hunter's Mark"], 5: ["Hold Person", "Misty Step"]},
    "The Fiend":       {1: ["Burning Hands", "Command"], 3: ["Blindness/Deafness", "Scorching Ray"]},
    "The Archfey":     {1: ["Faerie Fire", "Sleep"], 3: ["Calm Emotions", "Phantasmal Force"]},
    "The Great Old One":{1: ["Dissonant Whispers", "Tasha's Hideous Laughter"], 3: ["Detect Thoughts", "Phantasmal Force"]},
    "Hunter":          {},  # 游侠猎人无额外法术
    "Evocation":       {},  # 塑能法师无额外法术
    "Champion":        {},  # 冠军武士非施法者
    "Thief":           {},  # 窃贼非施法者
    "Berserker":       {},  # 狂战士非施法者
    "Lore":            {},  # 博学诗人无固定额外法术
}

# ── 专长（Feats）─────────────────────────────────────────────

ASI_LEVELS = [4, 8, 12, 16, 19]
ASI_LEVELS_FIGHTER = [4, 6, 8, 12, 14, 16, 19]  # Fighter 额外 6, 14
ASI_LEVELS_ROGUE = [4, 8, 10, 12, 16, 19]        # Rogue 额外 10

FEATS = {
    "Alert":               {"zh": "警觉", "desc": "+5先攻，不会被突袭，隐藏的攻击者不对你有优势", "effects": {"initiative_bonus": 5, "no_surprise": True}},
    "Tough":               {"zh": "坚韧", "desc": "HP每级+2（含追溯）", "effects": {"hp_per_level": 2}},
    "War Caster":          {"zh": "战争施法者", "desc": "专注豁免优势，持法器可施法，借机攻击可用法术", "effects": {"concentration_advantage": True}},
    "Great Weapon Master": {"zh": "巨武器大师", "desc": "重武器攻击-5命中+10伤害（可选），暴击/击杀后附赠攻击", "effects": {"gwm": True}},
    "Sharpshooter":        {"zh": "神射手", "desc": "远程-5命中+10伤害（可选），无视半/3/4掩体，射程不劣势", "effects": {"sharpshooter": True}},
    "Sentinel":            {"zh": "哨兵", "desc": "借机攻击命中目标速度归零，敌人攻击盟友时可借机攻击", "effects": {"sentinel": True}},
    "Polearm Master":      {"zh": "长柄武器大师", "desc": "长柄武器附赠1d4攻击，敌人进入触及时触发借机攻击", "effects": {"polearm_master": True}},
    "Shield Master":       {"zh": "盾牌大师", "desc": "附赠推撞，DEX豁免半伤可用反应减为0", "effects": {"shield_master": True}},
    "Lucky":               {"zh": "幸运", "desc": "每长休3次幸运点，可重掷任意d20", "effects": {"lucky_points": 3}},
    "Resilient":           {"zh": "坚毅", "desc": "一项属性+1并获得该属性豁免熟练", "effects": {"extra_save_prof": True}, "prereq": "选择一项属性"},
    "Observant":           {"zh": "观察者", "desc": "+5被动感知和被动调查", "effects": {"passive_perception_bonus": 5}},
    "Mobile":              {"zh": "灵活", "desc": "速度+10ft，冲刺时不受困难地形影响，攻击后不触发借机", "effects": {"speed_bonus": 2, "mobile": True}},
    "Crossbow Expert":     {"zh": "弩专家", "desc": "忽略装填特性，相邻远程不劣势，手弩附赠攻击", "effects": {"crossbow_expert": True}},
    "Magic Initiate":      {"zh": "魔法学徒", "desc": "从任一职业法术表学2戏法+1个1环法术（每长休1次）", "effects": {"magic_initiate": True}},
    "Ritual Caster":       {"zh": "仪式施法者", "desc": "可将仪式标记法术以仪式形式施放", "effects": {"ritual_caster": True}},
}

# ── 种族暗视（Darkvision）────────────────────────────────────

RACIAL_DARKVISION: dict[str, int] = {
    "Elf": 60, "Dwarf": 60, "Gnome": 60, "Half-Elf": 60,
    "Half-Orc": 60, "Tiefling": 60,
    "Dragonborn": 0, "Human": 0, "Halfling": 0,
    # 中文别名
    "精灵": 60, "矮人": 60, "侏儒": 60, "半精灵": 60,
    "半兽人": 60, "提夫林": 60,
    "龙裔": 0, "人类": 0, "半身人": 0,
}

# ── 力竭效果（Exhaustion, 5e PHB p.291）─────────────────────

EXHAUSTION_EFFECTS = {
    1: "ability_check_disadvantage",       # 能力检定劣势
    2: "speed_halved",                     # 速度减半
    3: "attack_save_disadvantage",         # 攻击检定和豁免检定劣势
    4: "hp_max_halved",                    # HP上限减半
    5: "speed_zero",                       # 速度降为0
    6: "death",                            # 死亡
}


def get_exhaustion_effects(exhaustion_level: int) -> list[str]:
    """返回当前力竭等级的所有累积效果"""
    effects = []
    for lvl in range(1, min(exhaustion_level, 6) + 1):
        effects.append(EXHAUSTION_EFFECTS[lvl])
    return effects


# ── 商店杂货/消耗品（5e PHB/SRD 物品）─────────────────────

SHOP_GEAR = {
    "Healing Potion":     {"zh": "治疗药水",     "cost": 50,   "weight": 0.5, "consumable": True, "effect": "heal", "heal_dice": "2d4+2", "description": "恢复2d4+2 HP"},
    "Greater Healing Potion": {"zh": "强效治疗药水", "cost": 150, "weight": 0.5, "consumable": True, "effect": "heal", "heal_dice": "4d4+4", "description": "恢复4d4+4 HP"},
    "Antitoxin":          {"zh": "解毒剂",       "cost": 50,   "weight": 0,   "consumable": True, "effect": "antitoxin", "description": "对毒素豁免优势，持续1小时"},
    "Rope (50ft)":        {"zh": "麻绳(50尺)",   "cost": 1,    "weight": 10,  "consumable": False, "description": "50尺麻绳"},
    "Torch":              {"zh": "火把",         "cost": 0.01, "weight": 1,   "consumable": True,  "description": "照明1小时，5尺明亮光+20尺昏暗"},
    "Rations (1 day)":    {"zh": "干粮(1天)",    "cost": 0.5,  "weight": 2,   "consumable": True,  "description": "一天的干粮"},
    "Bedroll":            {"zh": "睡袋",         "cost": 1,    "weight": 7,   "consumable": False, "description": "睡袋"},
    "Backpack":           {"zh": "背包",         "cost": 2,    "weight": 5,   "consumable": False, "description": "背包（容纳30磅）"},
    "Thieves' Tools":     {"zh": "盗贼工具",     "cost": 25,   "weight": 1,   "consumable": False, "description": "盗贼工具（开锁/拆陷阱）"},
    "Holy Symbol":        {"zh": "圣徽",         "cost": 5,    "weight": 1,   "consumable": False, "description": "圣徽（施法聚焦）"},
    "Arcane Focus":       {"zh": "奥术法器",     "cost": 10,   "weight": 1,   "consumable": False, "description": "奥术法器（施法聚焦）"},
    "Component Pouch":    {"zh": "材料包",       "cost": 25,   "weight": 2,   "consumable": False, "description": "材料包（施法材料）"},
    "Grappling Hook":     {"zh": "抓钩",         "cost": 2,    "weight": 4,   "consumable": False, "description": "抓钩"},
    "Oil (flask)":        {"zh": "灯油",         "cost": 1,    "weight": 1,   "consumable": True,  "description": "灯油（可泼洒引燃，5尺区域2d6火焰伤害）"},
    "Caltrops (bag of 20)": {"zh": "铁蒺藜(20个)", "cost": 1,  "weight": 2,   "consumable": True,  "description": "铁蒺藜（5尺区域，DEX DC15否则速度降为0）"},
    "Healer's Kit":       {"zh": "医疗包",       "cost": 5,    "weight": 3,   "consumable": True,  "uses": 10, "description": "医疗包（10次使用，稳定濒死角色）"},
    "Arrows (20)":        {"zh": "箭矢(20支)",   "cost": 1,    "weight": 1,   "consumable": True,  "description": "箭矢20支"},
    "Bolts (20)":         {"zh": "弩矢(20支)",   "cost": 1,    "weight": 1.5, "consumable": True,  "description": "弩矢20支"},
    "Potion of Fire Resistance": {"zh": "火焰抗性药水", "cost": 300, "weight": 0.5, "consumable": True, "effect": "fire_resistance", "description": "火焰抗性，持续1小时"},
}

# ── 物品中文名统一查找表（合并 WEAPONS + ARMOR + SHOP_GEAR + 杂项）──

GEAR_PACK_ZH = {
    "Explorer's Pack":   "探险者背包",
    "Priest's Pack":     "牧师背包",
    "Burglar's Pack":    "窃贼背包",
    "Dungeoneer's Pack": "地城探险背包",
    "Entertainer's Pack":"艺人背包",
    "Diplomat's Pack":   "外交官背包",
    "Scholar's Pack":    "学者背包",
    "Two Handaxes":      "两把手斧",
    "Five Javelins":     "五根标枪",
    "Component Pouch":   "材料包",
    "Arcane Focus":      "奥术法器",
}


def get_item_zh(name: str) -> str:
    """根据英文物品名获取中文名，优先查 WEAPONS/ARMOR/SHOP_GEAR 的 zh 字段，再查 GEAR_PACK_ZH"""
    for table in (WEAPONS, ARMOR, SHOP_GEAR):
        entry = table.get(name)
        if entry and "zh" in entry:
            return entry["zh"]
    return GEAR_PACK_ZH.get(name, name)


def calc_passive_perception(derived: dict, proficient_skills: list, feats: list = None) -> int:
    """计算被动感知值 = 10 + WIS修正 + 熟练加值（如果熟练感知）+ 专长加值"""
    wis_mod = derived.get("ability_modifiers", {}).get("wis", 0)
    prof = derived.get("proficiency_bonus", 2)
    is_proficient = "感知" in proficient_skills or "Perception" in proficient_skills
    base = 10 + wis_mod + (prof if is_proficient else 0)
    # Observant 专长加 +5
    if feats:
        for feat_entry in feats:
            fname = feat_entry.get("name", "") if isinstance(feat_entry, dict) else str(feat_entry)
            if fname == "Observant":
                base += 5
    return base


# ── 护甲/武器熟练度 ──────────────────────────────────────────

CLASS_ARMOR_PROFICIENCY = {
    "Fighter":   ["light", "medium", "heavy", "shield"],
    "Paladin":   ["light", "medium", "heavy", "shield"],
    "Ranger":    ["light", "medium", "shield"],
    "Cleric":    ["light", "medium", "shield"],
    "Barbarian": ["light", "medium", "shield"],
    "Rogue":     ["light"],
    "Monk":      [],
    "Bard":      ["light"],
    "Druid":     ["light", "medium", "shield"],
    "Wizard":    [],
    "Sorcerer":  [],
    "Warlock":   ["light"],
}

CLASS_WEAPON_PROFICIENCY = {
    "Fighter":   ["simple", "martial"],
    "Paladin":   ["simple", "martial"],
    "Ranger":    ["simple", "martial"],
    "Barbarian": ["simple", "martial"],
    "Rogue":     ["simple", "hand_crossbow", "longsword", "rapier", "shortsword"],
    "Monk":      ["simple", "shortsword"],
    "Cleric":    ["simple"],
    "Druid":     ["club", "dagger", "dart", "javelin", "mace", "quarterstaff", "scimitar", "sickle", "sling", "spear"],
    "Bard":      ["simple", "hand_crossbow", "longsword", "rapier", "shortsword"],
    "Wizard":    ["dagger", "dart", "sling", "quarterstaff", "light_crossbow"],
    "Sorcerer":  ["dagger", "dart", "sling", "quarterstaff", "light_crossbow"],
    "Warlock":   ["simple"],
}

# ── 计算函数 ──────────────────────────────────────────────

def ability_modifier(score: int) -> int:
    return (score - 10) // 2


def proficiency_bonus(level: int) -> int:
    return 2 + (level - 1) // 4


def apply_racial_bonuses(ability_scores: dict, race: str) -> dict:
    """将种族能力值加值应用到基础属性上，返回新字典"""
    bonuses = RACIAL_ABILITY_BONUSES.get(race, {})
    result = dict(ability_scores)
    for ability, bonus in bonuses.items():
        result[ability] = result.get(ability, 10) + bonus
    return result


def get_spell_slots(char_class: str, level: int) -> dict:
    """根据职业和等级返回正确的法术位字典"""
    cls_key = _normalize_class(char_class)
    caster_type = CASTER_TYPE.get(cls_key)

    if caster_type == "full":
        raw = SPELL_SLOTS_FULL.get(min(level, 20), {})
        return {k: v for k, v in raw.items() if v > 0}
    elif caster_type == "half":
        raw = SPELL_SLOTS_HALF.get(min(level, 20), {})
        return {k: v for k, v in raw.items() if v > 0}
    elif caster_type == "pact":
        pact = SPELL_SLOTS_WARLOCK.get(min(level, 20), {})
        slot_lvl = pact.get("slot_level", "1st")
        return {slot_lvl: pact.get("slots", 0)}
    return {}


def get_cantrips_count(char_class: str, level: int) -> int:
    """返回该职业在该等级应知道的戏法数量"""
    cls_key = _normalize_class(char_class)
    table = CANTRIPS_KNOWN.get(cls_key, {})
    if not table:
        return 0
    count = 0
    for threshold, val in sorted(table.items()):
        if level >= threshold:
            count = val
    return count


def calc_derived(char_class: str, level: int, ability_scores: dict, subclass: str = None,
                 fighting_style: str = None, feats: list = None, equipment: dict = None,
                 race: str = None, proficient_skills: list = None) -> dict:
    """计算角色的所有衍生属性（输入已含种族加值的最终能力值）"""
    cls_key = _normalize_class(char_class)

    str_mod = ability_modifier(ability_scores.get("str", 10))
    dex_mod = ability_modifier(ability_scores.get("dex", 10))
    con_mod = ability_modifier(ability_scores.get("con", 10))
    int_mod = ability_modifier(ability_scores.get("int", 10))
    wis_mod = ability_modifier(ability_scores.get("wis", 10))
    cha_mod = ability_modifier(ability_scores.get("cha", 10))

    prof = proficiency_bonus(level)
    hit_die = HIT_DICE.get(cls_key, 8)
    base_ac = BASE_AC.get(cls_key, 13)

    # 野蛮人无甲AC = 10 + DEX + CON
    if cls_key == "Barbarian":
        base_ac = max(base_ac, 10 + dex_mod + con_mod)
    # 武僧无甲AC = 10 + DEX + WIS
    if cls_key == "Monk":
        base_ac = max(base_ac, 10 + dex_mod + wis_mod)

    # HP：首级 = 最大骰+CON，后续 = (hit_die/2+1)+CON
    hp_max = hit_die + con_mod + max(0, level - 1) * (hit_die // 2 + 1 + con_mod)

    # 施法属性
    spell_ability_key = SPELLCASTING_ABILITY.get(cls_key)
    spell_mod = {"str": str_mod, "dex": dex_mod, "con": con_mod,
                 "int": int_mod, "wis": wis_mod, "cha": cha_mod}.get(spell_ability_key or "", 0)
    spell_save_dc      = 8 + prof + spell_mod if spell_ability_key else 0
    spell_attack_bonus = prof + spell_mod if spell_ability_key else 0

    # 法术位（全/半/契约）
    spell_slots_max = get_spell_slots(cls_key, level)

    # ── 子职业机械效果 ─────────────────────────────────────
    crit_threshold   = 20          # 暴击阈值（默认自然20）
    bonus_healing    = False       # 生命域：治疗加成
    attack_bonus_override = None   # Hexblade: CHA-based attack bonus
    subclass_effects = {}
    if subclass:
        sub = subclass.lower()
        # 冠军武士：3级起19暴击（Improved Critical），15级起18暴击（Superior Critical）
        if cls_key == "Fighter" and ("champion" in sub or "冠军" in sub):
            if level >= 15:
                crit_threshold = 18
            elif level >= 3:
                crit_threshold = 19
            subclass_effects["improved_critical"] = True
        # 生命域牧师：治疗加值 = 2 + 法术环级
        if cls_key == "Cleric" and ("life" in sub or "生命" in sub):
            bonus_healing = True
            subclass_effects["bonus_healing"] = True
        # 狂战士野蛮人：激怒时有额外攻击次数（简化：标记 flag）
        if cls_key == "Barbarian" and ("berserker" in sub or "狂战士" in sub):
            subclass_effects["frenzy"] = True
        # 图腾战士（熊图腾）：狂暴时所有伤害类型（除心灵）减半
        if cls_key == "Barbarian" and ("totem" in sub or "图腾" in sub):
            subclass_effects["totem_warrior"] = True
            subclass_effects["bear_totem"] = True  # Default to bear (most popular)
        # 狂热者野蛮人：狂暴时每回合首次命中+1d6+半等级辐射伤害
        if cls_key == "Barbarian" and ("zealot" in sub or "狂热" in sub):
            subclass_effects["zealot"] = True
            subclass_effects["divine_fury"] = True  # +1d6+half_level radiant on first hit per turn
        # 龙族血脉术士：+1HP/级，无甲时AC=13+DEX
        if cls_key == "Sorcerer" and ("draconic" in sub or "龙族" in sub):
            subclass_effects["draconic_resilience"] = True
            hp_max += level  # +1 HP per level
            if not equipment or not equipment.get("armor"):
                base_ac = max(base_ac, 13 + dex_mod)  # Natural armor 13+DEX
        # 魔剑契约锁链术师：用CHA代替STR/DEX进行武器攻击
        if cls_key == "Warlock" and ("hexblade" in sub or "魔剑" in sub):
            subclass_effects["hexblade"] = True
            subclass_effects["hex_warrior"] = True
            if cha_mod > str_mod and cha_mod > dex_mod:
                attack_bonus_override = prof + cha_mod
        # 剑客游荡者：先攻+CHA，独对时可偷袭
        if cls_key == "Rogue" and ("swashbuckler" in sub or "剑客" in sub):
            subclass_effects["swashbuckler"] = True
            subclass_effects["rakish_audacity"] = True
            # initiative_val += cha_mod applied after initiative_val is initialized
        # 刺客游荡者：首轮对未行动目标有优势且自动暴击
        if cls_key == "Rogue" and ("assassin" in sub or "刺客" in sub):
            subclass_effects["assassin"] = True
            subclass_effects["assassinate"] = True
        # 武士战士：战意精神（优势+临时HP）
        if cls_key == "Fighter" and ("samurai" in sub or "武士" in sub):
            subclass_effects["samurai"] = True
            subclass_effects["fighting_spirit"] = True
            subclass_effects["fighting_spirit_uses"] = max(1, wis_mod)
        # 虔诚圣武士：魅惑免疫光环
        if cls_key == "Paladin" and ("devotion" in sub or "虔诚" in sub):
            subclass_effects["devotion"] = True
            subclass_effects["aura_of_devotion"] = True
        # 复仇圣武士：仇敌誓约（对标记目标优势）
        if cls_key == "Paladin" and ("vengeance" in sub or "复仇" in sub):
            subclass_effects["vengeance"] = True
            subclass_effects["vow_of_enmity"] = True
        # 恶魔契约锁链术师：击杀时获得临时HP
        if cls_key == "Warlock" and ("fiend" in sub or "恶魔" in sub):
            subclass_effects["fiend_patron"] = True
            subclass_effects["dark_ones_blessing"] = True
        # 塑能系法师：可保护友军免受 AoE（标记 flag，法术端点读取）
        if cls_key == "Wizard" and ("evocation" in sub or "塑能" in sub):
            subclass_effects["sculpt_spells"] = True
        # 风暴先驱野蛮人：狂暴时10尺光环造成元素伤害
        if cls_key == "Barbarian" and ("storm" in sub or "风暴" in sub):
            subclass_effects["storm_herald"] = True
            aura_dmg = "1d6" if level < 10 else ("2d6" if level < 15 else "3d6")
            subclass_effects["storm_aura_damage"] = aura_dmg  # 沙漠=火焰, 海洋=闪电, 苔原=临时HP
        # 虫群之主游侠：攻击时虫群附加效果
        if cls_key == "Ranger" and ("swarm" in sub or "虫群" in sub):
            subclass_effects["swarmkeeper"] = True
            swarm_die = "1d6" if level < 11 else "1d8"
            subclass_effects["gathered_swarm_die"] = swarm_die  # 额外伤害或推动/拉扯
        # 神圣灵魂术士：获取牧师法术列表+神恩（失败时+2d4）
        if cls_key == "Sorcerer" and ("divine" in sub or "神圣" in sub):
            subclass_effects["divine_soul"] = True
            subclass_effects["favored_by_gods"] = True  # 1次/短休：攻击/检定/豁免+2d4
            subclass_effects["cleric_spell_access"] = True

        # ── Batch 2: 资源追踪子职业机械效果 ──────────────────────

        # ── 战争大师（Battle Master）：优势骰系统 ──
        if cls_key == "Fighter" and ("battle master" in sub or "战争大师" in sub):
            subclass_effects["battle_master"] = True
            sd_count = 4 if level < 7 else (5 if level < 15 else 6)
            sd_die = "d8" if level < 10 else ("d10" if level < 18 else "d12")
            subclass_effects["superiority_dice_max"] = sd_count
            subclass_effects["superiority_die"] = sd_die
            subclass_effects["maneuvers"] = ["precision", "trip", "disarm", "riposte", "menacing", "pushing", "goading"]

        # ── 吟游诗人（Bard）：鼓舞骰系统 ──
        if cls_key == "Bard":
            subclass_effects["bardic_inspiration"] = True
            bi_die = "d6" if level < 5 else ("d8" if level < 10 else ("d10" if level < 15 else "d12"))
            subclass_effects["inspiration_die"] = bi_die

        if cls_key == "Bard" and ("lore" in sub or "知识" in sub):
            subclass_effects["lore_bard"] = True
            subclass_effects["cutting_words"] = True

        if cls_key == "Bard" and ("valor" in sub or "英勇" in sub):
            subclass_effects["valor_bard"] = True
            subclass_effects["combat_inspiration"] = True

        if cls_key == "Bard" and ("swords" in sub or "剑术" in sub):
            subclass_effects["swords_bard"] = True
            subclass_effects["blade_flourish"] = True

        if cls_key == "Bard" and ("glamour" in sub or "魅惑" in sub):
            subclass_effects["glamour_bard"] = True
            subclass_effects["mantle_of_inspiration"] = True

        # ── 武僧（Monk）：气系统 ──
        if cls_key == "Monk":
            if level >= 2:
                subclass_effects["ki_pool"] = True
                subclass_effects["ki_max"] = level

        if cls_key == "Monk" and ("open hand" in sub or "虚空" in sub):
            subclass_effects["open_hand"] = True
            subclass_effects["open_hand_technique"] = True

        if cls_key == "Monk" and ("shadow" in sub or "暗影" in sub):
            subclass_effects["shadow_monk"] = True
            subclass_effects["shadow_step"] = True

        if cls_key == "Monk" and ("drunken" in sub or "醉拳" in sub):
            subclass_effects["drunken_master"] = True
            subclass_effects["drunken_technique"] = True

        if cls_key == "Monk" and ("four elements" in sub or "四象" in sub):
            subclass_effects["four_elements"] = True
            subclass_effects["elemental_disciplines"] = True

        # ── 牧师领域（Cleric Domains）──
        if cls_key == "Cleric" and ("war" in sub or "战争" in sub):
            subclass_effects["war_domain"] = True
            subclass_effects["war_priest"] = True

        if cls_key == "Cleric" and ("light" in sub or "光明" in sub):
            subclass_effects["light_domain"] = True
            subclass_effects["warding_flare"] = True

        if cls_key == "Cleric" and ("knowledge" in sub or "知识" in sub):
            subclass_effects["knowledge_domain"] = True

        if cls_key == "Cleric" and ("trickery" in sub or "诡计" in sub):
            subclass_effects["trickery_domain"] = True
            subclass_effects["blessing_of_trickster"] = True

        if cls_key == "Cleric" and ("nature" in sub or "自然" in sub):
            subclass_effects["nature_domain"] = True

        if cls_key == "Cleric" and ("tempest" in sub or "暴风" in sub):
            subclass_effects["tempest_domain"] = True
            subclass_effects["wrath_of_storm"] = True
            subclass_effects["destructive_wrath"] = True

        # ── 游侠（Ranger）子职业 ──
        if cls_key == "Ranger" and ("hunter" in sub or "猎手" in sub):
            subclass_effects["hunter"] = True
            subclass_effects["colossus_slayer"] = True

        if cls_key == "Ranger" and ("gloom" in sub or "暗域" in sub):
            subclass_effects["gloom_stalker"] = True
            subclass_effects["dread_ambusher"] = True

        # ── 德鲁伊（Druid）大地之环 ──
        if cls_key == "Druid" and ("land" in sub or "大地" in sub):
            subclass_effects["circle_of_land"] = True
            subclass_effects["natural_recovery"] = True

        # ── 术士（Sorcerer）起源 ──
        if cls_key == "Sorcerer" and ("wild" in sub or "野魔" in sub):
            subclass_effects["wild_magic"] = True
            subclass_effects["tides_of_chaos"] = True

        if cls_key == "Sorcerer" and ("storm" in sub or "风暴" in sub):
            subclass_effects["storm_sorcery"] = True
            subclass_effects["tempestuous_magic"] = True

        # ── Batch 3: 复杂子职业机械效果 ──────────────────────

        # 月亮德鲁伊：增强野兽形态
        if cls_key == "Druid" and ("moon" in sub or "月亮" in sub):
            subclass_effects["circle_of_moon"] = True
            subclass_effects["combat_wild_shape"] = True  # Bonus action to transform
            # CR limit: Lv2=CR1, Lv6=CR level/3
            max_cr = 1 if level < 6 else level // 3
            subclass_effects["wild_shape_max_cr"] = max_cr
            if level >= 10:
                subclass_effects["elemental_wild_shape"] = True

        # 孢子德鲁伊：孢子光环 + 共生体
        if cls_key == "Druid" and ("spores" in sub or "孢子" in sub):
            subclass_effects["circle_of_spores"] = True
            subclass_effects["halo_of_spores"] = True  # Reaction: 1d4 poison (1d6 at 6, 1d8 at 10, 1d10 at 14)
            spore_die = "1d4" if level < 6 else ("1d6" if level < 10 else ("1d8" if level < 14 else "1d10"))
            subclass_effects["spore_damage_die"] = spore_die
            subclass_effects["symbiotic_entity"] = True  # Use wild shape for temp HP = 4 * druid level
            subclass_effects["symbiotic_temp_hp"] = 4 * level

        # 魔战士（战士）：1/3 施法者
        if cls_key == "Fighter" and ("eldritch" in sub or "魔战" in sub):
            subclass_effects["eldritch_knight"] = True
            subclass_effects["weapon_bond"] = True
            # 1/3 caster: spell slots at Lv3
            if level >= 3:
                ek_caster_level = (level - 2) // 3 + 1  # Approximate
                ek_slots = get_spell_slots("Wizard", min(ek_caster_level, 7))
                subclass_effects["ek_spell_slots"] = ek_slots
            if level >= 7:
                subclass_effects["war_magic"] = True  # Cast cantrip + bonus action attack

        # 奥法诡术师（游荡者）：1/3 施法者
        if cls_key == "Rogue" and ("arcane trickster" in sub or "奥法" in sub):
            subclass_effects["arcane_trickster"] = True
            subclass_effects["mage_hand_legerdemain"] = True
            if level >= 3:
                at_caster_level = (level - 2) // 3 + 1
                at_slots = get_spell_slots("Wizard", min(at_caster_level, 7))
                subclass_effects["at_spell_slots"] = at_slots
            if level >= 9:
                subclass_effects["magical_ambush"] = True  # Disadvantage on save if hidden

        # 防护系法师：奥术结界
        if cls_key == "Wizard" and ("abjuration" in sub or "防护" in sub):
            subclass_effects["abjuration"] = True
            subclass_effects["arcane_ward"] = True
            subclass_effects["arcane_ward_hp_max"] = level * 2 + int_mod  # Ward HP pool

        # 幻术系法师：增强微型幻象
        if cls_key == "Wizard" and ("illusion" in sub or "幻术" in sub):
            subclass_effects["illusion"] = True
            subclass_effects["improved_minor_illusion"] = True

        # 死灵系法师：死亡收割
        if cls_key == "Wizard" and ("necromancy" in sub or "死灵" in sub):
            subclass_effects["necromancy"] = True
            subclass_effects["grim_harvest"] = True  # Heal 2x spell level on kill (3x for necromancy spells)

        # 咒法系法师：次级咒法
        if cls_key == "Wizard" and ("conjuration" in sub or "咒法" in sub):
            subclass_effects["conjuration"] = True
            subclass_effects["minor_conjuration"] = True

        # 预言系法师：先兆
        if cls_key == "Wizard" and ("divination" in sub or "预言" in sub):
            subclass_effects["divination"] = True
            subclass_effects["portent"] = True  # 2 pre-rolled d20s per long rest (3 at Lv14)
            subclass_effects["portent_count"] = 2 if level < 14 else 3

        # 附魔系法师：催眠凝视
        if cls_key == "Wizard" and ("enchantment" in sub or "附魔" in sub):
            subclass_effects["enchantment"] = True
            subclass_effects["hypnotic_gaze"] = True

        # 变化系法师：变化石
        if cls_key == "Wizard" and ("transmutation" in sub or "变化" in sub):
            subclass_effects["transmutation"] = True
            subclass_effects["transmuters_stone"] = True

        # 远古誓约圣武士：守护光环（法术伤害抗性）
        if cls_key == "Paladin" and ("ancients" in sub or "远古" in sub):
            subclass_effects["ancients"] = True
            subclass_effects["aura_of_warding"] = True  # Spell damage resistance 10ft

        # 荣耀誓约圣武士：鼓舞神击
        if cls_key == "Paladin" and ("glory" in sub or "荣耀" in sub):
            subclass_effects["glory"] = True
            subclass_effects["inspiring_smite"] = True  # Distribute temp HP after smite

        # 大精灵契约邪术师：妖精现身 + 迷雾逃遁
        if cls_key == "Warlock" and ("archfey" in sub or "大精灵" in sub):
            subclass_effects["archfey"] = True
            subclass_effects["fey_presence"] = True  # Charm/frighten in cube
            subclass_effects["misty_escape"] = True  # Reaction: invisible + teleport when damaged

        # 旧日支配者契约邪术师：觉醒心灵 + 思维护盾
        if cls_key == "Warlock" and ("great old one" in sub or "旧日" in sub):
            subclass_effects["great_old_one"] = True
            subclass_effects["awakened_mind"] = True  # Telepathy 30ft
            subclass_effects["thought_shield"] = True  # Psychic damage resistance + reflect

        # 窃贼游荡者：快手 + 攀墙术
        if cls_key == "Rogue" and ("thief" in sub or "窃贼" in sub):
            subclass_effects["thief"] = True
            subclass_effects["fast_hands"] = True  # Use Object as bonus action
            subclass_effects["second_story_work"] = True  # Climbing speed = walking speed
            if level >= 13:
                subclass_effects["use_magic_device"] = True

    # 豁免调整值（含熟练）
    save_profs = CLASS_SAVE_PROFICIENCIES.get(cls_key, [])
    saving_throws = {}
    for key, mod in [("str",str_mod),("dex",dex_mod),("con",con_mod),
                     ("int",int_mod),("wis",wis_mod),("cha",cha_mod)]:
        saving_throws[key] = mod + (prof if key in save_profs else 0)

    # ── 战斗风格效果 ──────────────────────────────────────
    melee_damage_bonus = 0
    two_weapon_fighting = False
    style_effects = {}
    if fighting_style and fighting_style in FIGHTING_STYLES:
        fs = FIGHTING_STYLES[fighting_style]
        style_effects = dict(fs)
        if fs.get("ac_bonus"):
            base_ac += fs["ac_bonus"]
        if fs.get("ranged_attack_bonus"):
            pass  # 在下方 return 中直接加
        if fs.get("melee_damage_bonus"):
            melee_damage_bonus = fs["melee_damage_bonus"]
        if fs.get("two_weapon_fighting"):
            two_weapon_fighting = True

    ranged_atk_bonus = prof + dex_mod + (FIGHTING_STYLES.get(fighting_style or "", {}).get("ranged_attack_bonus", 0))

    # ── 装备效果（如果提供了装备信息）───────────────────────
    equipped_weapon_damage = None
    equipped_weapon_type = None
    armor_proficiencies = CLASS_ARMOR_PROFICIENCY.get(cls_key, [])
    weapon_proficiencies = CLASS_WEAPON_PROFICIENCY.get(cls_key, [])

    if equipment and isinstance(equipment, dict):
        # 护甲 AC
        equipped_armor = equipment.get("armor", [])
        if equipped_armor:
            armor_item = equipped_armor[0] if isinstance(equipped_armor, list) else equipped_armor
            armor_name = armor_item.get("name", "") if isinstance(armor_item, dict) else str(armor_item)
            if armor_name in ARMOR:
                a = ARMOR[armor_name]
                armor_ac = a["ac"]
                if a["dex_bonus"] == "full":
                    armor_ac += dex_mod
                elif a["dex_bonus"] == "max2":
                    armor_ac += min(2, dex_mod)
                base_ac = armor_ac
                # 重新应用战斗风格 Defense bonus（如果有护甲）
                if fighting_style == "Defense":
                    base_ac += 1
        # 盾牌
        shield_item = equipment.get("shield")
        if shield_item:
            base_ac += 2
        # 武器
        weapons = equipment.get("weapons", [])
        if weapons:
            w = weapons[0] if isinstance(weapons, list) else weapons
            if isinstance(w, dict):
                equipped_weapon_damage = w.get("damage", "1d8")
                equipped_weapon_type = w.get("type", "")

    # ── 专长效果 ──────────────────────────────────────────
    feat_effects = {}
    if feats:
        for feat_entry in feats:
            fname = feat_entry.get("name", "") if isinstance(feat_entry, dict) else str(feat_entry)
            if fname in FEATS:
                effects = FEATS[fname]["effects"]
                feat_effects[fname] = effects
                if effects.get("initiative_bonus"):
                    pass  # 在 return 中加
                if effects.get("hp_per_level"):
                    hp_max += effects["hp_per_level"] * level
                if effects.get("concentration_advantage"):
                    subclass_effects["concentration_advantage"] = True
                if effects.get("speed_bonus"):
                    pass  # movement_max 在 combat 中处理

    initiative_val = dex_mod
    for fe in feat_effects.values():
        initiative_val += fe.get("initiative_bonus", 0)
    # Swashbuckler: add CHA to initiative
    if subclass_effects.get("rakish_audacity"):
        initiative_val += cha_mod
    # Gloom Stalker: add WIS to initiative
    if subclass_effects.get("dread_ambusher"):
        initiative_val += wis_mod

    # ── 暗视 ────────────────────────────────────────────
    darkvision = RACIAL_DARKVISION.get(race or "", 0)

    # ── 被动感知 ────────────────────────────────────────
    passive_perception = calc_passive_perception(
        {"ability_modifiers": {"wis": wis_mod}, "proficiency_bonus": prof},
        proficient_skills or [],
        feats,
    )

    return {
        "hp_max":              max(1, hp_max),
        "ac":                  base_ac,
        "initiative":          initiative_val,
        "proficiency_bonus":   prof,
        "attack_bonus":        attack_bonus_override if attack_bonus_override is not None else (prof + str_mod),
        "attack_bonus_override": attack_bonus_override,
        "ranged_attack_bonus": ranged_atk_bonus,
        "melee_damage_bonus":  melee_damage_bonus,
        "spell_save_dc":       spell_save_dc,
        "spell_attack_bonus":  spell_attack_bonus,
        "spell_ability":       spell_ability_key,
        "ability_modifiers":   {
            "str": str_mod, "dex": dex_mod, "con": con_mod,
            "int": int_mod, "wis": wis_mod, "cha": cha_mod,
        },
        "saving_throws":       saving_throws,
        "spell_slots_max":     spell_slots_max,
        "hit_die":             hit_die,
        "caster_type":         CASTER_TYPE.get(cls_key),
        "cantrips_count":      get_cantrips_count(cls_key, level),
        # 子职业效果
        "crit_threshold":      crit_threshold,
        "bonus_healing":       bonus_healing,
        "subclass_effects":    subclass_effects,
        # 战斗风格
        "fighting_style":      fighting_style,
        "two_weapon_fighting": two_weapon_fighting,
        "style_effects":       style_effects,
        # 装备
        "equipped_weapon_damage": equipped_weapon_damage,
        "equipped_weapon_type":   equipped_weapon_type,
        "armor_proficiencies":    armor_proficiencies,
        "weapon_proficiencies":   weapon_proficiencies,
        # 专长
        "feat_effects":        feat_effects,
        # 感知与视觉
        "passive_perception":  passive_perception,
        "darkvision":          darkvision,
    }


def calc_hit_dice_pool(char_class: str, level: int) -> dict:
    """Calculate hit dice pool for short rest"""
    cls_key = _normalize_class(char_class)
    hit_die = HIT_DICE.get(cls_key, 8)
    return {"total": level, "remaining": level, "die": f"d{hit_die}"}


def get_class_resource_defaults(char_class: str, level: int, subclass: str = None) -> dict:
    """Return default class resource values for a class and level"""
    cls_key = _normalize_class(char_class)
    resources = {}
    if cls_key == "Fighter":
        resources["second_wind_used"] = False
        if level >= 2:
            resources["action_surge_used"] = False
        # Samurai: Fighting Spirit uses (WIS mod, minimum 1; default 1 without ability scores)
        if subclass and ("samurai" in subclass.lower() or "武士" in subclass.lower()):
            resources["fighting_spirit_remaining"] = max(1, 1)  # default 1, recalculated with actual WIS
        # Battle Master: Superiority Dice (replenish on short rest)
        if subclass and ("battle master" in subclass.lower() or "战争大师" in subclass.lower()):
            resources["superiority_dice_remaining"] = 4 if level < 7 else (5 if level < 15 else 6)
    elif cls_key == "Barbarian":
        if level >= 1:
            rage_uses = 2
            if level >= 20:
                rage_uses = 999
            elif level >= 17:
                rage_uses = 6
            elif level >= 12:
                rage_uses = 5
            elif level >= 6:
                rage_uses = 4
            elif level >= 3:
                rage_uses = 3
            resources["rage_remaining"] = rage_uses
            resources["raging"] = False
    elif cls_key == "Rogue":
        resources["cunning_action_available"] = True
    elif cls_key == "Paladin":
        resources["channel_divinity_used"] = False
        resources["lay_on_hands_remaining"] = level * 5
    elif cls_key == "Monk":
        resources["ki_remaining"] = level if level >= 2 else 0
    elif cls_key == "Bard":
        cha_mod_est = 3  # estimate, actual calculated at creation
        resources["bardic_inspiration_remaining"] = max(1, cha_mod_est)
    # Cleric resources
    elif cls_key == "Cleric":
        resources["channel_divinity_used"] = False
        if subclass and ("war" in subclass.lower() or "战争" in subclass.lower()):
            resources["war_priest_remaining"] = max(1, 1)  # WIS mod, default 1
    # Druid resources
    elif cls_key == "Druid":
        resources["wild_shape_remaining"] = 2  # 2 uses, replenish on short rest
    # Sorcerer resources
    elif cls_key == "Sorcerer":
        if subclass and ("wild" in subclass.lower() or "野蛮" in subclass.lower()):
            resources["tides_of_chaos_used"] = False
    # Wizard resources
    elif cls_key == "Wizard":
        if subclass and ("divination" in subclass.lower() or "预言" in subclass.lower()):
            resources["portent_remaining"] = 2  # 3 at Lv14+
            if level >= 14:
                resources["portent_remaining"] = 3
    return resources


def _normalize_class(char_class: str) -> str:
    """将中文/别名职业名转换为英文标准名"""
    mapping = {
        "战士": "Fighter", "圣武士": "Paladin", "野蛮人": "Barbarian",
        "游侠": "Ranger", "游荡者": "Rogue", "武僧": "Monk",
        "牧师": "Cleric", "德鲁伊": "Druid", "吟游诗人": "Bard",
        "法师": "Wizard", "术士": "Sorcerer", "邪术师": "Warlock",
        "魔契师": "Warlock",
    }
    return mapping.get(char_class, char_class)


# ── 骰子系统 ──────────────────────────────────────────────

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
) -> dict:
    """
    豁免检定
    ability: "str"/"dex"/"con"/"int"/"wis"/"cha"
    """
    derived    = character.get("derived", {})
    saves      = derived.get("saving_throws", {})
    total_mod  = saves.get(ability, derived.get("ability_modifiers", {}).get(ability, 0))

    if advantage and not disadvantage:
        d20_result = roll_advantage("1d20")
    elif disadvantage and not advantage:
        d20_result = roll_disadvantage("1d20")
    else:
        d20_result = roll_dice("1d20")

    d20   = d20_result["rolls"][0]
    total = d20 + total_mod

    return {
        "ability":  ability,
        "d20":      d20,
        "modifier": total_mod,
        "total":    total,
        "dc":       dc,
        "success":  total >= dc,
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
    derived  = character.get("derived", {})
    prof     = derived.get("proficiency_bonus", 2)
    mods     = derived.get("ability_modifiers", {})
    ability  = SKILL_ABILITY_MAP.get(skill, "wis")
    mod      = mods.get(ability, 0)

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
        "modifier":   total_mod,
        "total":      total,
        "dc":         dc,
        "success":    total >= dc,
        "proficient": is_proficient,
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
