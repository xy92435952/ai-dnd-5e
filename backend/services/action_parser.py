"""
Action Parser — 自然语言战斗行动解析器
=======================================
将玩家的自然语言输入解析为结构化的行动指令列表，
由本地规则引擎逐步执行（骰点、距离检查、伤害计算）。

本文件保留旧入口与私有符号兼容；具体 prompt、本地解析、LLM 解析与
fallback 逻辑拆到相邻模块，降低战斗入口的维护压力。
"""

import asyncio
import json
import logging

from services.action_parser_fallbacks import fallback_combat_action as _fallback_combat_action
from services.action_parser_llm import parse_with_llm as _parse_with_llm
from services.action_parser_local import (
    ATTACK_WORDS as _ATTACK_WORDS,
    MOVE_WORDS as _MOVE_WORDS,
    RANGED_WORDS as _RANGED_WORDS,
    UNREACHABLE_MELEE_HINT as _UNREACHABLE_MELEE_HINT,
    can_reach_melee_after_move as _can_reach_melee_after_move,
    dist as _dist,
    enemy_name_matches as _enemy_name_matches,
    living_enemies as _living_enemies,
    nearest_enemy as _nearest_enemy,
    parse_target_pos as _parse_target_pos,
    parse_local_combat_action as _parse_local_combat_action,
    target_ally_from_text as _target_ally_from_text,
    target_enemy_from_text as _target_enemy_from_text,
)
from services.action_parser_prompts import PARSE_PROMPT

logger = logging.getLogger(__name__)

_VALID_ACTION_TYPES = {"move", "attack", "spell", "creative", "dodge", "dash", "disengage", "help"}


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
    local = _parse_local_combat_action(
        player_input,
        game_state,
        player_id,
        positions,
        move_remaining,
    )
    if local:
        logger.info(f"本地行动解析: {player_input[:30]}... -> {len(local['actions'])} 个行动")
        return local

    try:
        result = await _parse_with_llm(
            player_input=player_input,
            game_state=game_state,
            player_id=player_id,
            player_data=player_data,
            positions=positions,
            move_remaining=move_remaining,
        )
        result["actions"] = [
            action for action in result["actions"]
            if action.get("type") in _VALID_ACTION_TYPES
        ]

        logger.info(f"行动解析: {player_input[:30]}... -> {len(result['actions'])} 个行动")
        return result

    except asyncio.TimeoutError:
        logger.warning(f"行动解析超时: {player_input[:30]}...")
    except json.JSONDecodeError as e:
        logger.warning(f"行动解析 JSON 失败: {e}")
    except Exception as e:
        logger.warning(f"行动解析异常: {e}")

    return _fallback_combat_action(
        player_input,
        game_state,
        player_id,
        positions,
        move_remaining,
    )
