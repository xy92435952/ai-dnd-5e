"""
LangGraph nodes for the DM Agent runtime.
"""

from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer

from services.graphs.dm_agent_messages import build_combat_user_content, build_explore_user_content
from services.graphs.dm_agent_prompts import COMBAT_SYSTEM as COMBAT_SYSTEM_PROMPT
from services.graphs.dm_agent_prompts import EXPLORE_SYSTEM as EXPLORE_SYSTEM_PROMPT
from services.graphs.dm_agent_runtime import build_pre_rolled_dice, read_combat_active
from services.graphs.dm_agent_state import DMAgentState
from services.graphs.dm_agent_utils import (
    build_input_meta,
    build_memory_context,
    build_rules_context,
    normalize_dm_output,
)
from services.llm import get_llm

logger = logging.getLogger(__name__)


def _content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(str(part.get("text") or part.get("content") or ""))
            else:
                parts.append(str(part))
        return "".join(parts)
    return str(content or "")


async def _invoke_dm_llm(messages: list, *, temperature: float, max_tokens: int, stream_tokens: bool) -> str:
    llm = get_llm(temperature=temperature, max_tokens=max_tokens)
    if not stream_tokens:
        resp = await llm.ainvoke(messages)
        return _content_to_text(resp.content)

    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = None

    if writer is None or not hasattr(llm, "astream"):
        resp = await llm.ainvoke(messages)
        return _content_to_text(resp.content)

    chunks: list[str] = []
    async for chunk in llm.astream(messages):
        text = _content_to_text(getattr(chunk, "content", ""))
        if not text:
            continue
        chunks.append(text)
        writer({"type": "llm_token", "content": text})
    return "".join(chunks)


async def input_layer(state: DMAgentState) -> dict:
    """输入层：归一化行动来源，并只对人类自由输入执行拦截。"""
    from services.input_guard import classify_player_input

    input_meta = build_input_meta(state)
    result = await classify_player_input(
        state.get("player_action", ""),
        source=input_meta["source"],
    )
    return {
        "input_meta": input_meta,
        "guard_verdict": result["verdict"],
        "guard_refusal": result["refusal"],
    }


def route_after_guard(state: DMAgentState) -> str:
    return "refuse" if state.get("guard_verdict") in ("off_topic", "rule_violation", "injection") else "proceed"


async def rules_layer(state: DMAgentState) -> dict:
    """规则层：为后续 DM LLM 提供独立的机械裁定上下文，不负责讲故事。"""
    return {"rules_context": build_rules_context(state)}


async def memory_layer(state: DMAgentState) -> dict:
    """记忆层：整理长期记忆/检索片段，避免叙事 prompt 到处拼接记忆。"""
    return {"memory_context": build_memory_context(state)}


async def refuse_and_end(state: DMAgentState) -> dict:
    """被输入审核拦截时，构造与正常流程兼容的 result，narrative 用拒绝文案。"""
    verdict = state.get("guard_verdict", "off_topic")
    refusal = state.get("guard_refusal") or "（DM）请用正常的游戏行动继续冒险。"

    fallback = {
        "action_type": "blocked_" + verdict,
        "narrative": refusal,
        "companion_reactions": "",
        "needs_check": {"required": False},
        "state_delta": {
            "characters": [],
            "enemies": [],
            "combat_end": False,
            "combat_end_result": None,
            "combat_trigger": False,
            "gold_changes": [],
        },
        "player_choices": [],
        "dice_results": [],
        "ai_turns": [],
        "combat_continues": state.get("combat_active", False),
    }
    return {"result": fallback, "error": ""}


async def pre_roll_dice(state: DMAgentState) -> dict:
    return {
        "dice_pool": json.dumps(build_pre_rolled_dice(), ensure_ascii=False),
        "combat_active": read_combat_active(state.get("game_state")),
    }


def route_by_mode(state: DMAgentState) -> str:
    return "combat_dm" if state.get("combat_active") else "explore_dm"


async def combat_dm(state: DMAgentState) -> dict:
    output = await _invoke_dm_llm(
        [
            SystemMessage(content=COMBAT_SYSTEM_PROMPT),
            HumanMessage(content=build_combat_user_content(state)),
        ],
        temperature=0.72,
        max_tokens=2000,
        stream_tokens=bool(state.get("stream_tokens")),
    )
    return {"llm_output": output}


async def explore_dm(state: DMAgentState) -> dict:
    output = await _invoke_dm_llm(
        [
            SystemMessage(content=EXPLORE_SYSTEM_PROMPT),
            HumanMessage(content=build_explore_user_content(state)),
        ],
        temperature=0.82,
        max_tokens=2000,
        stream_tokens=bool(state.get("stream_tokens")),
    )
    return {"llm_output": output}


async def parse_validate(state: DMAgentState) -> dict:
    raw = state.get("llm_output", "")
    logger.info("[parse_validate] raw len=%s, starts_with=%r", len(raw), raw[:40])
    data, error, new_messages = normalize_dm_output(raw, state.get("player_action", ""))
    return {
        "result": data,
        "error": error,
        "messages": new_messages,
    }
