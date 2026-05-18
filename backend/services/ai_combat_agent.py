"""
AI Combat Decision Agent — 战斗 AI 决策系统
=============================================
职责：为 AI 单位（敌人/队友）生成智能战斗决策。
原则：AI 只决定"做什么"，本地引擎负责"怎么算"。
"""

import asyncio
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from services.ai_combat_agent_context import (
    build_ai_combat_context,
    chebyshev as _chebyshev,
    format_actions as _format_actions,
    format_distances as _format_distances,
    format_entity as _format_entity,
    format_spells as _format_spells,
)
from services.ai_combat_agent_parser import (
    FALLBACK_DECISION as _FALLBACK,
    ensure_valid_ai_decision_targets,
    fallback_decision,
    parse_ai_decision_response,
)
from services.ai_combat_agent_prompts import (
    ALLY_DECISION_PROMPT,
    DIFFICULTY_INSTRUCTIONS as _DIFFICULTY_INSTRUCTIONS,
    ENEMY_DECISION_PROMPT,
)
from services.llm import get_llm

logger = logging.getLogger(__name__)


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

    Returns:
        决策 dict: {action_type, target_id, action_name, spell_level, move_first, reason}
    """
    try:
        context = build_ai_combat_context(
            actor=actor,
            actor_is_enemy=actor_is_enemy,
            all_characters=all_characters,
            all_enemies=all_enemies,
            positions=positions,
        )
        targets_alive = context["targets_alive"]
        if not targets_alive:
            return fallback_decision(action_type="dodge", reason="无存活目标，进入防御")

        if actor_is_enemy:
            prompt = _build_enemy_prompt(
                actor=actor,
                context=context,
                module_difficulty=module_difficulty,
                module_tactics=module_tactics,
            )
        else:
            prompt = _build_ally_prompt(
                actor=actor,
                context=context,
                all_characters=all_characters,
                positions=positions,
                actor_personality=actor_personality,
            )

        llm = get_llm(temperature=0.6, max_tokens=300, task="fast")
        resp = await asyncio.wait_for(
            llm.ainvoke([
                SystemMessage(content="你是 DnD 5e 战斗 AI。只返回 JSON 决策，不要有任何其他文字。"),
                HumanMessage(content=prompt),
            ]),
            timeout=8.0,
        )

        decision = parse_ai_decision_response(resp.content)
        decision, target_replaced = ensure_valid_ai_decision_targets(
            decision=decision,
            targets_alive=targets_alive,
            all_characters=all_characters,
        )
        if target_replaced:
            logger.warning(f"AI 决策包含无效 target_id，回退到首个目标: {decision['target_id']}")

        logger.info(
            f"AI 决策 [{actor.get('name')}]: {decision['action_type']} → "
            f"{str(decision.get('target_id', 'none'))[:8]} | {decision.get('reason', '')}"
        )
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


def _build_enemy_prompt(
    *,
    actor: dict,
    context: dict,
    module_difficulty: str,
    module_tactics: str,
) -> str:
    actor_pos = context["actor_pos"]
    move_speed = context["move_speed"]
    return ENEMY_DECISION_PROMPT.format(
        actor_name=actor.get("name", "未知"),
        actor_hp=actor.get("hp_current", 0),
        actor_hp_max=context["actor_hp_max"],
        actor_ac=actor.get("ac") or (actor.get("derived") or {}).get("ac", 10),
        actor_x=actor_pos.get("x", "?"),
        actor_y=actor_pos.get("y", "?"),
        actor_actions=_format_actions(actor.get("actions", [])),
        tactics=module_tactics or "无特殊战术指令",
        difficulty_instructions=_DIFFICULTY_INSTRUCTIONS.get(
            module_difficulty,
            _DIFFICULTY_INSTRUCTIONS["normal"],
        ),
        targets_info=context["targets_info"],
        allies_info=context["allies_info"],
        distance_info=context["distance_info"],
        move_speed=move_speed,
        move_speed_ft=move_speed * 5,
    )


def _build_ally_prompt(
    *,
    actor: dict,
    context: dict,
    all_characters: list,
    positions: dict,
    actor_personality: str,
) -> str:
    actor_pos = context["actor_pos"]
    move_speed = context["move_speed"]
    combat_pref = (actor.get("derived") or {}).get("combat_preference", "平衡")
    return ALLY_DECISION_PROMPT.format(
        actor_name=actor.get("name", "未知"),
        actor_class=actor.get("char_class", ""),
        actor_level=actor.get("level", 1),
        actor_hp=actor.get("hp_current", 0),
        actor_hp_max=context["actor_hp_max"],
        actor_ac=(actor.get("derived") or {}).get("ac", 10),
        actor_x=actor_pos.get("x", "?"),
        actor_y=actor_pos.get("y", "?"),
        personality=actor_personality or "无特殊性格",
        combat_preference=combat_pref,
        spell_info=_format_spells(actor),
        actor_actions=_format_actions(actor.get("actions") or (actor.get("equipment") or {}).get("weapons") or []),
        allies_info="\n".join(
            _format_entity(a, positions.get(str(a.get("id"))))
            for a in all_characters
            if a.get("hp_current", 0) > 0
        ),
        targets_info=context["targets_info"],
        distance_info=context["distance_info"],
        move_speed=move_speed,
        move_speed_ft=move_speed * 5,
    )


def calc_difficulty(parsed: dict) -> str:
    """根据模组的 level_min 和 tone 判断难度"""
    level_min = parsed.get("level_min", 3)
    tone = (parsed.get("tone", "") or "").lower()

    if level_min <= 2 or any(k in tone for k in ["轻松", "入门", "简单", "easy", "beginner"]):
        return "easy"
    if level_min >= 7 or any(k in tone for k in ["致命", "困难", "deadly", "hard"]):
        return "hard"
    return "normal"


__all__ = [
    "ALLY_DECISION_PROMPT",
    "ENEMY_DECISION_PROMPT",
    "_DIFFICULTY_INSTRUCTIONS",
    "_FALLBACK",
    "_chebyshev",
    "_format_actions",
    "_format_distances",
    "_format_entity",
    "_format_spells",
    "calc_difficulty",
    "get_ai_decision",
]
