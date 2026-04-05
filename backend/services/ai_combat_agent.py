"""
AI Combat Decision Agent — 战斗 AI 决策系统
=============================================
职责：为 AI 单位（敌人/队友）生成智能战斗决策。
原则：AI 只决定"做什么"，本地引擎负责"怎么算"。

两套 Prompt：
  - ENEMY_DECISION_PROMPT: 敌人策略，根据模组难度动态调节
  - ALLY_DECISION_PROMPT:  队友策略，遵循性格和战斗偏好
"""

import json
import logging
import asyncio
from typing import Optional

from services.llm import get_llm
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Difficulty descriptions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_DIFFICULTY_INSTRUCTIONS = {
    "easy": """## 难度：简单（新手友好）
你的智力有限，经常做出不太聪明的决定：
- 有 40% 概率选择次优目标（不一定打最脆弱的）
- 有时会选择较弱的攻击方式，忽略更强的法术/能力
- 绝不集火已经濒死（0HP）的角色
- 偶尔会犯蠢：攻击有掩体的目标、忘记使用特殊能力
- 不会主动配合其他敌人进行战术包围
- 低血量时不会聪明地撤退，可能继续硬冲""",

    "normal": """## 难度：普通
你有基本的战斗智慧：
- 优先攻击威胁较大或HP较低的目标
- 会使用自己的特殊能力和法术（如果有的话）
- 低血量（< 30% HP）时会考虑撤退或切换防御策略
- 不会刻意集火已倒下的角色
- 会利用基本的位置优势（远程保持距离，近战贴近）""",

    "hard": """## 难度：困难（老练战术）
你是一个经验丰富的战斗者，追求最优策略：
- 优先集火治疗者（Cleric/Druid）和施法者（Wizard/Sorcerer）
- 充分利用所有可用的法术和特殊能力
- 协同战术：与其他敌人配合包围、控制关键目标
- 利用掩体和地形优势
- 打断施法者的专注法术（攻击正在专注的角色）
- 低血量时聪明撤退到安全位置或使用控制技能拖延
- 会优先使用控制类法术（如恐惧、束缚）削弱多个目标""",
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Enemy Prompt
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ENEMY_DECISION_PROMPT = """你是一个 DnD 5e 战斗中敌方单位的战斗 AI。你需要为这个怪物选择本回合的行动。

## 你的身份
名称：{actor_name}
HP：{actor_hp}/{actor_hp_max}
AC：{actor_ac}
位置：({actor_x}, {actor_y})
可用行动：
{actor_actions}

## 战术指令
{tactics}

{difficulty_instructions}

## 战场局势
### 你的敌人（玩家方）
{targets_info}

### 你的盟友（其他敌方单位）
{allies_info}

## 位置与距离
{distance_info}

## 规则约束
- 近战攻击需要目标在相邻格（距离 ≤ 1 格 = 5ft）
- 远程攻击/法术有射程限制
- 你每回合可以移动最多 {move_speed} 格（{move_speed_ft}ft）
- 如果目标不在攻击范围内，你可以选择 "move" 靠近，或 "dash" 移动双倍距离（但不能攻击）
- 选择 "dodge" 可以让所有针对你的攻击获得劣势（防御策略）

## 输出格式
只返回以下 JSON，不要有任何其他文字：
{{
  "action_type": "attack|spell|move|dodge|dash|disengage",
  "target_id": "目标实体ID 或 null（dodge/dash/disengage 时为 null）",
  "action_name": "使用的具体攻击或法术名称（从可用行动中选择）或 null",
  "move_first": true,
  "reason": "一句话战术说明"
}}"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Ally Prompt
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ALLY_DECISION_PROMPT = """你是一个 DnD 5e 战斗中的 AI 队友。你需要根据自己的性格和职业特点选择本回合的行动。

## 你的身份
名称：{actor_name}
职业：{actor_class} Lv{actor_level}
HP：{actor_hp}/{actor_hp_max}
AC：{actor_ac}
位置：({actor_x}, {actor_y})
性格与战斗偏好：{personality}

## 你的能力
可用法术（剩余法术位）：
{spell_info}
基础攻击：
{actor_actions}

## 战场局势
### 你的队友（需要保护）
{allies_info}

### 敌人
{targets_info}

## 位置与距离
{distance_info}

## 行为原则
- 如果你是治疗职业（Cleric/Druid/Paladin）且有队友 HP < 50%，优先考虑治疗
- 如果你是施法者（Wizard/Sorcerer/Warlock），优先使用法术而非近战
- 如果你是近战职业（Fighter/Barbarian/Paladin），贴近敌人攻击
- 如果你是 Rogue，寻找偷袭机会（攻击与队友相邻的敌人以获得优势）
- 不要浪费高级法术位在可以用戏法解决的情况上
- 遵循你的战斗偏好：{combat_preference}

## 规则约束
- 近战攻击需要目标在相邻格（距离 ≤ 1 格 = 5ft）
- 法术有射程限制
- 你每回合可以移动最多 {move_speed} 格（{move_speed_ft}ft）
- 治疗法术（如 Cure Wounds）触及范围需要相邻，Healing Word 有 60ft 射程

## 输出格式
只返回以下 JSON，不要有任何其他文字：
{{
  "action_type": "attack|spell|move|dodge|dash|disengage|help",
  "target_id": "目标实体ID（攻击选敌人ID，治疗选队友ID）或 null",
  "action_name": "使用的具体攻击或法术名称 或 null",
  "spell_level": null,
  "move_first": true,
  "reason": "一句话战术说明"
}}"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helper: build context strings
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _chebyshev(a: dict, b: dict) -> int:
    if not a or not b:
        return 999
    return max(abs(a.get("x", 0) - b.get("x", 0)), abs(a.get("y", 0) - b.get("y", 0)))


def _format_entity(e: dict, pos: dict = None) -> str:
    """格式化一个实体为简短描述"""
    hp = e.get("hp_current", 0)
    hp_max = e.get("hp_max") or (e.get("derived") or {}).get("hp_max", hp)
    hp_pct = int(hp / hp_max * 100) if hp_max > 0 else 0
    conds = ", ".join(e.get("conditions", [])) or "无"
    conc = e.get("concentration", "")
    pos_str = f"({pos['x']},{pos['y']})" if pos else "未知"
    cls = e.get("char_class", e.get("type", ""))
    conc_str = f" [专注: {conc}]" if conc else ""

    return (
        f"  - ID: {e.get('id','?')} | {e.get('name','?')} ({cls}) | "
        f"HP: {hp}/{hp_max} ({hp_pct}%) | AC: {e.get('ac') or (e.get('derived') or {}).get('ac',10)} | "
        f"位置: {pos_str} | 条件: {conds}{conc_str}"
    )


def _format_actions(actions: list) -> str:
    """格式化怪物/角色的可用行动"""
    if not actions:
        return "  - 普通近战攻击"
    lines = []
    for a in actions:
        name = a.get("name", "未知")
        atype = a.get("type", "")
        dmg = a.get("damage_dice", "")
        atk = a.get("attack_bonus") or a.get("to_hit", "")
        rng = a.get("reach_or_range", a.get("reach", ""))
        extra = a.get("extra_effects", "")
        lines.append(f"  - {name} ({atype}) | 命中: +{atk} | 伤害: {dmg} | 范围: {rng}" +
                     (f" | 特殊: {extra}" if extra else ""))
    return "\n".join(lines) if lines else "  - 普通近战攻击"


def _format_spells(char: dict) -> str:
    """格式化队友的可用法术"""
    known = char.get("known_spells", []) or []
    cantrips = char.get("cantrips", []) or []
    slots = char.get("spell_slots", {}) or {}
    prepared = char.get("prepared_spells", []) or []
    all_spells = list(set(known) | set(cantrips) | set(prepared))

    if not all_spells:
        return "  无法术"

    lines = []
    if cantrips:
        lines.append(f"  戏法（无限次）: {', '.join(cantrips)}")
    for slot_level in ["1st", "2nd", "3rd", "4th", "5th"]:
        remaining = slots.get(slot_level, 0)
        if remaining > 0:
            lines.append(f"  {slot_level} 级法术位: {remaining} 剩余")
    if known:
        lines.append(f"  习得法术: {', '.join(known[:10])}")
    return "\n".join(lines) if lines else "  无法术"


def _format_distances(actor_pos: dict, entities: list, positions: dict) -> str:
    """格式化距离信息"""
    lines = []
    for e in entities:
        eid = str(e.get("id", ""))
        epos = positions.get(eid)
        if epos and actor_pos:
            dist = _chebyshev(actor_pos, epos)
            lines.append(f"  → {e.get('name','?')} (ID:{eid[:8]}): {dist} 格 ({dist*5}ft)" +
                         (" ⚔近战范围" if dist <= 1 else ""))
    return "\n".join(lines) if lines else "  无距离信息"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Core decision function
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Default fallback decision
_FALLBACK = {
    "action_type": "attack",
    "target_id": None,
    "action_name": None,
    "spell_level": None,
    "move_first": True,
    "reason": "默认攻击（AI决策失败，回退到基础逻辑）",
    "_fallback": True,
}


async def get_ai_decision(
    actor: dict,
    actor_is_enemy: bool,
    all_characters: list,
    all_enemies: list,
    positions: dict,
    module_difficulty: str = "normal",
    module_tactics: str = "",
    actor_personality: str = "",
) -> dict:
    """
    为 AI 单位生成战斗决策。

    Args:
        actor:              行动者完整数据（含 id, name, hp_current, actions 等）
        actor_is_enemy:     是否为敌方单位
        all_characters:     所有玩家+队友状态列表
        all_enemies:        所有敌人状态列表
        positions:          实体位置 {id: {x, y}}
        module_difficulty:  "easy" / "normal" / "hard"
        module_tactics:     怪物的 tactics 字段
        actor_personality:  队友的性格/战斗偏好

    Returns:
        决策 dict: {action_type, target_id, action_name, spell_level, move_first, reason}
    """
    try:
        actor_id = str(actor.get("id", ""))
        actor_pos = positions.get(actor_id, {})
        move_speed = max(actor.get("speed", 30), 20) // 5  # 转为格数

        # 构建目标列表和盟友列表
        if actor_is_enemy:
            targets = all_characters   # 敌人攻击玩家方
            allies = [e for e in all_enemies if str(e.get("id")) != actor_id and e.get("hp_current", 0) > 0]
        else:
            targets = all_enemies      # 队友攻击敌人
            allies = [c for c in all_characters if str(c.get("id")) != actor_id and c.get("hp_current", 0) > 0]

        # 过滤活着的目标
        targets_alive = [t for t in targets if t.get("hp_current", 0) > 0]
        if not targets_alive:
            return {**_FALLBACK, "action_type": "dodge", "reason": "无存活目标，进入防御"}

        # 格式化上下文
        targets_info = "\n".join(_format_entity(t, positions.get(str(t.get("id")))) for t in targets_alive)
        allies_info = "\n".join(_format_entity(a, positions.get(str(a.get("id")))) for a in allies) or "  无盟友"
        distance_info = _format_distances(actor_pos, targets_alive + allies, positions)

        actor_hp_max = actor.get("hp_max") or (actor.get("derived") or {}).get("hp_max", actor.get("hp_current", 1))

        if actor_is_enemy:
            # 敌人决策
            prompt = ENEMY_DECISION_PROMPT.format(
                actor_name=actor.get("name", "未知"),
                actor_hp=actor.get("hp_current", 0),
                actor_hp_max=actor_hp_max,
                actor_ac=actor.get("ac") or (actor.get("derived") or {}).get("ac", 10),
                actor_x=actor_pos.get("x", "?"),
                actor_y=actor_pos.get("y", "?"),
                actor_actions=_format_actions(actor.get("actions", [])),
                tactics=module_tactics or "无特殊战术指令",
                difficulty_instructions=_DIFFICULTY_INSTRUCTIONS.get(module_difficulty, _DIFFICULTY_INSTRUCTIONS["normal"]),
                targets_info=targets_info,
                allies_info=allies_info,
                distance_info=distance_info,
                move_speed=move_speed,
                move_speed_ft=move_speed * 5,
            )
        else:
            # 队友决策
            combat_pref = (actor.get("derived") or {}).get("combat_preference", "平衡")
            prompt = ALLY_DECISION_PROMPT.format(
                actor_name=actor.get("name", "未知"),
                actor_class=actor.get("char_class", ""),
                actor_level=actor.get("level", 1),
                actor_hp=actor.get("hp_current", 0),
                actor_hp_max=actor_hp_max,
                actor_ac=(actor.get("derived") or {}).get("ac", 10),
                actor_x=actor_pos.get("x", "?"),
                actor_y=actor_pos.get("y", "?"),
                personality=actor_personality or "无特殊性格",
                combat_preference=combat_pref,
                spell_info=_format_spells(actor),
                actor_actions=_format_actions(actor.get("actions") or (actor.get("equipment") or {}).get("weapons") or []),
                allies_info="\n".join(_format_entity(a, positions.get(str(a.get("id")))) for a in all_characters if a.get("hp_current", 0) > 0),
                targets_info=targets_info,
                distance_info=distance_info,
                move_speed=move_speed,
                move_speed_ft=move_speed * 5,
            )

        # LLM 调用（低温度、短输出、严格超时）
        llm = get_llm(temperature=0.6, max_tokens=300)
        resp = await asyncio.wait_for(
            llm.ainvoke([
                SystemMessage(content="你是 DnD 5e 战斗 AI。只返回 JSON 决策，不要有任何其他文字。"),
                HumanMessage(content=prompt),
            ]),
            timeout=8.0,
        )

        # 解析 JSON
        raw = resp.content.strip()
        # 去除可能的 markdown 代码块
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        decision = json.loads(raw)

        # 验证必须字段
        decision.setdefault("action_type", "attack")
        decision.setdefault("target_id", None)
        decision.setdefault("action_name", None)
        decision.setdefault("spell_level", None)
        decision.setdefault("move_first", True)
        decision.setdefault("reason", "")
        decision["_fallback"] = False

        # 验证 target_id 是否有效
        valid_ids = {str(t.get("id")) for t in targets_alive}
        ally_ids = {str(a.get("id")) for a in all_characters if a.get("hp_current", 0) > 0}
        all_valid = valid_ids | ally_ids

        if decision["target_id"] and str(decision["target_id"]) not in all_valid:
            logger.warning(f"AI 决策包含无效 target_id: {decision['target_id']}, 回退到首个目标")
            decision["target_id"] = str(targets_alive[0].get("id"))

        # 如果没有指定目标且需要目标的行动，选第一个
        if decision["action_type"] in ("attack", "spell") and not decision["target_id"]:
            decision["target_id"] = str(targets_alive[0].get("id"))

        logger.info(f"AI 决策 [{actor.get('name')}]: {decision['action_type']} → "
                     f"{decision.get('target_id', 'none')[:8]} | {decision.get('reason', '')}")
        return decision

    except asyncio.TimeoutError:
        logger.warning(f"AI 决策超时 [{actor.get('name', '?')}]，回退到默认逻辑")
        return _FALLBACK
    except json.JSONDecodeError as e:
        logger.warning(f"AI 决策 JSON 解析失败 [{actor.get('name', '?')}]: {e}")
        return _FALLBACK
    except Exception as e:
        logger.warning(f"AI 决策异常 [{actor.get('name', '?')}]: {e}")
        return _FALLBACK


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Difficulty calculator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def calc_difficulty(parsed: dict) -> str:
    """根据模组的 level_min 和 tone 判断难度"""
    level_min = parsed.get("level_min", 3)
    tone = (parsed.get("tone", "") or "").lower()

    if level_min <= 2 or any(k in tone for k in ["轻松", "入门", "简单", "easy", "beginner"]):
        return "easy"
    if level_min >= 7 or any(k in tone for k in ["致命", "困难", "deadly", "hard"]):
        return "hard"
    return "normal"
