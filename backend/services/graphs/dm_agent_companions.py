"""Companion reaction helpers and LangGraph node for the DM agent."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from services.graphs.dm_agent_state import DMAgentState
from services.graphs.dm_agent_utils import strip_code_block
from services.llm import get_llm

logger = logging.getLogger(__name__)


COMPANION_REACTION_SYSTEM = """
You write only AI companion reactions for the exact same story beat the DM just narrated.

Rules:
- Stay inside the current beat. Do not advance the plot, reveal new facts, or change state.
- Only speak for companions explicitly provided to you.
- Keep every companion distinct in personality, speech style, and tone.
- Prefer 0-2 speakers total. If the brief allows one speaker, choose the single best voice.
- Use concise reactions. No markdown, no JSON, no narration outside the companions.
- Output either an empty string or one or more lines in this format:
  [Name]: reaction text
"""


def _safe_json_loads(text: str | None, default: Any):
    try:
        return json.loads(text or "")
    except (TypeError, json.JSONDecodeError):
        return default


def _collect_ai_companions(game_state_text: str | None) -> list[dict]:
    game_state = _safe_json_loads(game_state_text, {})
    characters = game_state.get("characters", []) if isinstance(game_state, dict) else []
    if not isinstance(characters, list):
        return []

    companions = []
    for char in characters:
        if not isinstance(char, dict):
            continue
        if char.get("is_player") is False and char.get("name"):
            companions.append({
                "id": char.get("id"),
                "name": char.get("name"),
                "personality": char.get("personality", ""),
                "speech_style": char.get("speech_style", ""),
                "combat_preference": char.get("combat_preference", ""),
                "catchphrase": char.get("catchphrase", ""),
                "backstory": (char.get("backstory", "") or "")[:240],
            })
    return companions


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
        return default
    if value is None:
        return default
    return bool(value)


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(number, maximum))


def _normalize_companion_brief(raw_brief: Any, result: dict) -> dict:
    brief = raw_brief if isinstance(raw_brief, dict) else {}
    needs_check = result.get("needs_check") if isinstance(result.get("needs_check"), dict) else {}
    state_delta = result.get("state_delta") if isinstance(result.get("state_delta"), dict) else {}
    fallback_enabled = (
        result.get("action_type") not in {"movement", "rest"}
        and not bool(needs_check.get("required"))
        and not bool(state_delta.get("combat_trigger"))
    )

    enabled = _coerce_bool(brief.get("enabled", fallback_enabled), fallback_enabled)
    speaker_limit = _bounded_int(brief.get("speaker_limit"), 1 if enabled else 0, 0, 2)
    max_words = _bounded_int(brief.get("max_words"), 36 if enabled else 0, 0, 120)
    return {
        "enabled": enabled,
        "scene_type": str(brief.get("scene_type", "quiet"))[:32],
        "emotion": str(brief.get("emotion", "neutral"))[:32],
        "focus": str(brief.get("focus", result.get("narrative", "")[:120]))[:240],
        "speaker_limit": speaker_limit,
        "max_words": max_words,
    }


def route_after_parse(state: DMAgentState) -> str:
    if state.get("combat_active"):
        return "end"

    result = state.get("result") or {}
    brief = _normalize_companion_brief(result.get("companion_brief"), result)
    companions = _collect_ai_companions(state.get("game_state", "{}"))
    if brief.get("enabled") and brief.get("speaker_limit", 0) > 0 and companions:
        return "generate_companion_reactions"
    return "end"


async def generate_companion_reactions(state: DMAgentState) -> dict:
    result = dict(state.get("result") or {})
    companions = _collect_ai_companions(state.get("game_state", "{}"))
    brief = _normalize_companion_brief(result.get("companion_brief"), result)

    if not companions or not brief.get("enabled") or brief.get("speaker_limit", 0) <= 0:
        result["companion_reactions"] = ""
        return {"result": result}

    llm = get_llm(temperature=0.9, max_tokens=450)

    history_lines = []
    for msg in (state.get("messages") or [])[-4:]:
        role = "player" if isinstance(msg, HumanMessage) else "dm"
        history_lines.append(f"[{role}] {msg.content[:220]}")

    compact_companions = companions[: max(brief.get("speaker_limit", 1) + 1, 2)]
    user_content = f"""Current player action:
{state.get("player_action", "")}

DM narrative for this beat:
{result.get("narrative", "")}

Companion brief:
{json.dumps(brief, ensure_ascii=False)}

Available AI companions:
{json.dumps(compact_companions, ensure_ascii=False)}

Recent local history:
{chr(10).join(history_lines)}

Write companion reactions only for this beat. If no one should speak, return an empty string.
"""

    try:
        resp = await llm.ainvoke([
            SystemMessage(content=COMPANION_REACTION_SYSTEM),
            HumanMessage(content=user_content),
        ])
        text = strip_code_block((resp.content or "").strip())
        if text.upper() == "NONE":
            text = ""
        result["companion_reactions"] = text
    except Exception as exc:
        logger.warning("[generate_companion_reactions] fallback to empty: %s", exc)
        result["companion_reactions"] = ""

    return {"result": result}
