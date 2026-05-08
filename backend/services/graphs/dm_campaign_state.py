"""
Campaign state summarization for the DM Agent stack.

This is a plain LLM call rather than a LangGraph node. Keeping it separate from
the DM graph makes the runtime path easier to reason about and test.
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from services.graphs.dm_agent_prompts import CAMPAIGN_STATE_PROMPT
from services.graphs.dm_agent_utils import strip_code_block
from services.llm import get_llm


def _valid_quest_entries(items: list) -> list[dict]:
    return [q for q in (items or []) if isinstance(q, dict) and q.get("quest")]


def _merge_campaign_states(existing: dict, new: dict) -> dict:
    merged = dict(existing) if existing else {}
    for key in ("completed_scenes", "key_decisions", "notable_items", "party_changes"):
        old_list = merged.get(key, [])
        new_list = new.get(key, [])
        merged[key] = old_list + [x for x in new_list if x not in old_list]
    for key in ("npc_registry", "world_flags"):
        old_dict = dict(merged.get(key, {}))
        new_dict = new.get(key, {})
        old_dict.update(new_dict)
        merged[key] = old_dict
    quest_map = {q["quest"]: q for q in _valid_quest_entries(merged.get("quest_log", []))}
    for q in _valid_quest_entries(new.get("quest_log", [])):
        quest_map[q["quest"]] = q
    merged["quest_log"] = list(quest_map.values())
    return merged


async def run_campaign_state_generator(
    log_text: str,
    module_summary: str,
    existing_state: dict,
) -> dict:
    llm = get_llm(temperature=0.3, max_tokens=2000)
    prompt = (
        f"{CAMPAIGN_STATE_PROMPT}\n\n"
        f"## 模组背景\n{module_summary}\n\n"
        f"## 冒险记录\n{log_text}"
    )
    try:
        resp = await llm.ainvoke([
            SystemMessage(content="你是DnD冒险记录分析专家。只输出JSON。"),
            HumanMessage(content=prompt),
        ])
        raw = strip_code_block(resp.content)
        new_state = json.loads(raw)
        return _merge_campaign_states(existing_state, new_state)
    except Exception:
        return existing_state
