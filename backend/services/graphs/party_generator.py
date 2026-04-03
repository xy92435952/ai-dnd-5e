"""
WF2 — 队友生成 LangGraph 图
3 节点线性链：analyze_roles → generate_companions → calc_derived_stats
"""

import json
import re
from typing import TypedDict

from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage

from services.llm import get_llm


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# State
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PartyGeneratorState(TypedDict):
    player_class: str
    player_race: str
    player_level: int
    party_size: int
    module_data: dict
    # intermediate
    role_assignments: str
    companions_needed: int
    module_setting: str
    module_tone: str
    level: int
    llm_output: str
    # output
    companions: list
    error: str


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Constants (from Dify Code node)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ROLE_MAP = {
    'tank': ['fighter', 'paladin', 'barbarian', '战士', '圣武士', '野蛮人'],
    'healer': ['cleric', 'druid', 'bard', '牧师', '德鲁伊', '吟游诗人'],
    'arcane_dps': ['wizard', 'sorcerer', 'warlock', '法师', '术士', '魔契师', '邪术师'],
    'martial_dps': ['fighter', 'ranger', 'monk', 'rogue', '战士', '游侠', '武僧', '游荡者'],
    'utility': ['rogue', 'ranger', 'bard', '游荡者', '游侠', '吟游诗人'],
}

ROLE_FILL = {
    'tank': {'class': 'Fighter', 'subclass': 'Champion', 'role_desc': '坚守前线的护盾'},
    'healer': {'class': 'Cleric', 'subclass': 'Life Domain', 'role_desc': '支撑队伍的治愈者'},
    'arcane_dps': {'class': 'Wizard', 'subclass': 'Evocation', 'role_desc': '强力的奥术输出'},
    'utility': {'class': 'Rogue', 'subclass': 'Thief', 'role_desc': '灵活的探索专家'},
}

HIT_DICE = {
    'Barbarian': 12, 'Fighter': 10, 'Paladin': 10, 'Ranger': 10,
    'Monk': 8, 'Rogue': 8, 'Bard': 8, 'Cleric': 8, 'Druid': 8, 'Warlock': 8,
    'Sorcerer': 6, 'Wizard': 6, 'default': 8
}

BASE_AC = {
    'Barbarian': 10, 'Fighter': 16, 'Paladin': 18,
    'Rogue': 13, 'Ranger': 14, 'Monk': 10,
    'Wizard': 12, 'Sorcerer': 12, 'Warlock': 12,
    'Cleric': 16, 'Druid': 14, 'Bard': 13, 'default': 13
}

GEN_SYSTEM = """你是一个DnD 5e角色创建专家，擅长创造有深度、有个性的角色。
你需要根据要求生成AI控制的队友角色。
只返回JSON数组，不要有任何额外文字或markdown标记。"""

GEN_USER = """模组世界观：{module_setting}
模组基调：{module_tone}
角色等级：{level}
职能分配：{role_assignments}

请根据以上信息，为每个职能槽生成一个AI队友角色，返回JSON数组格式：
[
  {{
    "slot": 职能槽编号,
    "name": "符合模组世界观的角色名字",
    "race": "种族（标准DnD 5e种族）",
    "class": "职业",
    "subclass": "子职业",
    "level": 等级,
    "background": "背景职业（如学者/士兵/罪犯等）",
    "alignment": "阵营（如守序善良/中立善良等）",
    "personality_traits": "性格特点（2-3句话，有具体细节）",
    "speech_style": "说话风格（如简洁干练/话多热情/冷静观察/幽默调皮）",
    "combat_preference": "战斗倾向（如激进突前/冷静支援/保护队友/机会主义）",
    "backstory": "背景故事（80字以内，与模组世界观相符）",
    "ability_scores": {{
      "str": 数值, "dex": 数值, "con": 数值,
      "int": 数值, "wis": 数值, "cha": 数值
    }},
    "catchphrase": "一句标志性口头禅"
  }}
]

要求：
- 性格要多样化，避免都是严肃类型
- 能力值总和约75-78点（体现职业侧重）
- 名字要符合世界观风格"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _mod(score: int) -> int:
    return (score - 10) // 2


def _strip_code_block(text: str) -> str:
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Graph nodes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def analyze_roles(state: PartyGeneratorState) -> dict:
    module = state.get("module_data") or {}
    level = state["player_level"]
    companions_needed = max(0, state["party_size"] - 1)

    pc_lower = state["player_class"].lower()
    covered_roles = set()
    for role, classes in ROLE_MAP.items():
        if any(c.lower() in pc_lower or pc_lower in c.lower() for c in classes):
            covered_roles.add(role)

    priority_roles = ['healer', 'tank', 'arcane_dps', 'utility']
    needed_roles = [r for r in priority_roles if r not in covered_roles]

    assigned = []
    for i in range(companions_needed):
        role = needed_roles[i] if i < len(needed_roles) else priority_roles[i % len(priority_roles)]
        fill = ROLE_FILL.get(role, ROLE_FILL['utility'])
        assigned.append({
            'slot': i + 1,
            'needed_role': role,
            'suggested_class': fill['class'],
            'suggested_subclass': fill['subclass'],
            'role_desc': fill['role_desc'],
            'level': level,
        })

    return {
        "companions_needed": companions_needed,
        "role_assignments": json.dumps(assigned, ensure_ascii=False),
        "module_setting": module.get('setting', '标准奇幻世界'),
        "module_tone": module.get('tone', '标准冒险'),
        "level": level,
    }


async def generate_companions(state: PartyGeneratorState) -> dict:
    if state["companions_needed"] <= 0:
        return {"llm_output": "[]"}

    llm = get_llm(temperature=0.85, max_tokens=4000)
    user_msg = GEN_USER.format(
        module_setting=state["module_setting"],
        module_tone=state["module_tone"],
        level=state["level"],
        role_assignments=state["role_assignments"],
    )
    resp = await llm.ainvoke([
        SystemMessage(content=GEN_SYSTEM),
        HumanMessage(content=user_msg),
    ])
    return {"llm_output": resp.content}


async def calc_derived_stats(state: PartyGeneratorState) -> dict:
    try:
        text = _strip_code_block(state.get("llm_output", "[]"))
        companions = json.loads(text)
        if not isinstance(companions, list):
            companions = []

        level = state["level"]
        prof_bonus = 2 + (level - 1) // 4

        for c in companions:
            scores = c.get('ability_scores', {})
            str_s = scores.get('str', 10)
            dex_s = scores.get('dex', 10)
            con_s = scores.get('con', 10)

            cls = c.get('class', 'default')
            hit_die = HIT_DICE.get(cls, HIT_DICE['default'])
            base_ac = BASE_AC.get(cls, BASE_AC['default'])

            c['derived'] = {
                'hp_max': hit_die + _mod(con_s) + (level - 1) * (hit_die // 2 + 1 + _mod(con_s)),
                'ac': base_ac,
                'initiative': _mod(dex_s),
                'proficiency_bonus': prof_bonus,
                'attack_bonus': prof_bonus + _mod(str_s),
                'ability_modifiers': {
                    'str': _mod(str_s), 'dex': _mod(dex_s), 'con': _mod(con_s),
                    'int': _mod(scores.get('int', 10)),
                    'wis': _mod(scores.get('wis', 10)),
                    'cha': _mod(scores.get('cha', 10)),
                }
            }
            c['hp_current'] = c['derived']['hp_max']

        return {"companions": companions, "error": ""}
    except Exception as e:
        return {"companions": [], "error": str(e)}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Build graph
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_party_generator_graph():
    g = StateGraph(PartyGeneratorState)
    g.add_node("analyze_roles", analyze_roles)
    g.add_node("generate_companions", generate_companions)
    g.add_node("calc_derived_stats", calc_derived_stats)

    g.set_entry_point("analyze_roles")
    g.add_edge("analyze_roles", "generate_companions")
    g.add_edge("generate_companions", "calc_derived_stats")
    g.add_edge("calc_derived_stats", END)

    return g.compile()


async def run_party_generator(
    player_class: str,
    player_race: str,
    player_level: int,
    party_size: int,
    module_data: dict,
) -> list[dict]:
    graph = build_party_generator_graph()
    result = await graph.ainvoke({
        "player_class": player_class,
        "player_race": player_race,
        "player_level": player_level,
        "party_size": party_size,
        "module_data": module_data,
        "role_assignments": "",
        "companions_needed": 0,
        "module_setting": "",
        "module_tone": "",
        "level": player_level,
        "llm_output": "",
        "companions": [],
        "error": "",
    })
    return result.get("companions", [])
