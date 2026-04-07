"""
Action Parser — 自然语言战斗行动解析器
=======================================
将玩家的自然语言输入解析为结构化的行动指令列表，
由本地规则引擎逐步执行（骰点、距离检查、伤害计算）。

流程：
  玩家输入 "移动到队友身边并攻击最近的敌人"
  → AI 解析为 [{type:"move", ...}, {type:"attack", ...}]
  → 本地引擎执行每个行动
  → 返回完整结果 + DM 叙事包装

支持的行动类型：
  - move: 移动到指定位置或目标旁边
  - attack: 近战/远程攻击指定目标
  - spell: 施放法术
  - creative: 创意行动（环境交互、即兴武器等），需要检定
  - dodge: 闪避
  - dash: 冲刺
  - disengage: 脱离接战
  - help: 协助盟友
"""

import json
import logging
import asyncio
from typing import Optional

from services.llm import get_llm
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

PARSE_PROMPT = """你是一个 DnD 5e 战斗行动解析器。你的任务是将玩家的自然语言描述拆解为结构化的行动指令列表。

## 当前战场状态
{game_state}

## 玩家角色信息
ID: {player_id}
名称: {player_name}
位置: ({player_x}, {player_y})
HP: {player_hp}/{player_hp_max}
AC: {player_ac}

## 规则约束
- 每回合只有1个标准动作（攻击/施法/闪避/冲刺/脱离/协助/创意行动）
- 每回合只有1个附赠动作
- 移动力最多 {move_remaining} 格（{move_remaining_ft}ft）
- 近战攻击需要与目标相邻（距离≤1格=5ft）
- 所有骰点由引擎执行，你不要决定结果

## 你的任务
将玩家的描述拆解为有序的行动列表。每个行动是以下类型之一：

1. **move** — 移动
   {{"type": "move", "target_id": "移动到某实体旁边的ID", "target_pos": null, "reason": "靠近敌人"}}
   或 {{"type": "move", "target_pos": {{"x": 5, "y": 3}}, "target_id": null, "reason": "移动到掩体后"}}

2. **attack** — 近战/远程攻击
   {{"type": "attack", "target_id": "敌人ID", "is_ranged": false, "reason": "挥剑斩击"}}

3. **spell** — 施放法术
   {{"type": "spell", "spell_name": "法术名", "spell_level": 1, "target_id": "目标ID", "reason": "施放魔法飞弹"}}

4. **creative** — 创意/环境交互行动（消耗标准动作）
   {{"type": "creative", "description": "把油灯扔向蛛网", "check_type": "dex", "dc": 12, "damage_dice": "1d4", "damage_type": "火焰", "target_id": "enemy_1", "effect_on_success": "蛛网着火，范围内敌人受火焰伤害", "effect_on_fail": "油灯偏离目标"}}

5. **dodge/dash/disengage/help** — 标准战术动作
   {{"type": "dodge"}} 或 {{"type": "dash"}} 或 {{"type": "disengage"}} 或 {{"type": "help", "target_id": "盟友ID"}}

## 输出格式
只返回 JSON，不要有其他文字：
{{
  "actions": [行动1, 行动2, ...],
  "narrative_hint": "一句话描述玩家想做什么（供叙事用）"
}}

## 重要规则
- 移动应排在攻击之前（先靠近再打）
- 不要超过1个标准动作
- 如果玩家描述了不可能的事（如飞行但没有飞行能力），将其转化为最接近的合理行动
- target_id 必须是战场上实际存在的实体 ID
- 如果无法确定目标，选择最近的或最合理的

## 玩家输入
{player_input}
"""


async def parse_combat_action(
    player_input: str,
    game_state: dict,
    player_id: str,
    player_data: dict,
    positions: dict,
    move_remaining: int = 6,
) -> dict:
    """
    将自然语言战斗输入解析为结构化行动列表。

    Returns:
        {
            "actions": [{"type": "move", ...}, {"type": "attack", ...}],
            "narrative_hint": "玩家想做什么",
            "_fallback": False
        }
    """
    try:
        player_pos = positions.get(str(player_id), {})

        # 构建简化的战场信息给 AI
        battlefield = []
        for eid, pos in positions.items():
            # 从 game_state 找实体信息
            entity_info = None
            for char in game_state.get("characters", []):
                if str(char.get("id")) == str(eid):
                    entity_info = f"{char.get('name','?')} (队友, HP:{char.get('hp_current',0)}/{char.get('hp_max',0)})"
                    break
            if not entity_info:
                for enemy in game_state.get("enemies", []):
                    if str(enemy.get("id")) == str(eid):
                        entity_info = f"{enemy.get('name','?')} (敌人, HP:{enemy.get('hp_current',0)}/{enemy.get('hp_max',0)})"
                        break
            if not entity_info:
                entity_info = eid[:8]

            dist = max(abs(pos.get("x",0) - player_pos.get("x",0)),
                       abs(pos.get("y",0) - player_pos.get("y",0))) if player_pos else 999
            battlefield.append(f"  ID:{eid[:16]} | {entity_info} | 位置:({pos.get('x','?')},{pos.get('y','?')}) | 距离:{dist}格({dist*5}ft)")

        game_state_str = "\n".join(battlefield) if battlefield else "无实体信息"

        prompt = PARSE_PROMPT.format(
            game_state=game_state_str,
            player_id=player_id,
            player_name=player_data.get("name", "玩家"),
            player_x=player_pos.get("x", "?"),
            player_y=player_pos.get("y", "?"),
            player_hp=player_data.get("hp_current", 0),
            player_hp_max=player_data.get("hp_max", 0),
            player_ac=player_data.get("ac", 10),
            move_remaining=move_remaining,
            move_remaining_ft=move_remaining * 5,
            player_input=player_input,
        )

        llm = get_llm(temperature=0.3, max_tokens=500)
        resp = await asyncio.wait_for(
            llm.ainvoke([
                SystemMessage(content="你是 DnD 5e 战斗行动解析器。只返回 JSON。"),
                HumanMessage(content=prompt),
            ]),
            timeout=10.0,
        )

        raw = resp.content.strip()
        # 去除 markdown 代码块
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        result = json.loads(raw)
        result.setdefault("actions", [])
        result.setdefault("narrative_hint", "")
        result["_fallback"] = False

        # 验证 actions
        valid_types = {"move", "attack", "spell", "creative", "dodge", "dash", "disengage", "help"}
        result["actions"] = [a for a in result["actions"] if a.get("type") in valid_types]

        logger.info(f"行动解析: {player_input[:30]}... → {len(result['actions'])} 个行动")
        return result

    except asyncio.TimeoutError:
        logger.warning(f"行动解析超时: {player_input[:30]}...")
    except json.JSONDecodeError as e:
        logger.warning(f"行动解析 JSON 失败: {e}")
    except Exception as e:
        logger.warning(f"行动解析异常: {e}")

    # Fallback: 当作普通攻击
    return {
        "actions": [{"type": "attack", "target_id": None, "is_ranged": False, "reason": player_input}],
        "narrative_hint": player_input,
        "_fallback": True,
    }
