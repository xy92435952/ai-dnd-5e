"""
Runtime helpers for DM Agent graph execution.

These functions are intentionally free of LangGraph and LLM dependencies. They
prepare initial state, dice pools, and the public response wrapper around the
graph's final state.
"""

from __future__ import annotations

import json
import random


def build_pre_rolled_dice() -> dict:
    return {
        "d20": [random.randint(1, 20) for _ in range(16)],
        "adv": [max(random.randint(1, 20), random.randint(1, 20)) for _ in range(6)],
        "dis": [min(random.randint(1, 20), random.randint(1, 20)) for _ in range(6)],
        "d4": [random.randint(1, 4) for _ in range(8)],
        "d6": [random.randint(1, 6) for _ in range(12)],
        "d8": [random.randint(1, 8) for _ in range(8)],
        "d10": [random.randint(1, 10) for _ in range(6)],
        "d12": [random.randint(1, 12) for _ in range(4)],
        "d100": random.randint(1, 100),
        "hit_dice": [random.randint(1, 8) for _ in range(6)],
    }


def read_combat_active(game_state: str | None) -> bool:
    try:
        gs = json.loads(game_state or "{}")
    except (json.JSONDecodeError, TypeError):
        return False
    return bool(gs.get("combat_active", False))


def build_initial_state(
    player_action: str,
    game_state: str,
    module_context: str,
    campaign_memory: str = "",
    retrieved_context: str = "",
    action_source: str = "human_input",
) -> dict:
    return {
        "player_action": player_action,
        "action_source": action_source,
        "game_state": game_state,
        "module_context": module_context,
        "campaign_memory": campaign_memory,
        "retrieved_context": retrieved_context,
        "messages": [],
        "dice_pool": "",
        "combat_active": False,
        "llm_output": "",
        "input_meta": {},
        "rules_context": "",
        "memory_context": "",
        "guard_verdict": "",
        "guard_refusal": "",
        "result": {},
        "error": "",
    }


def _to_bool(value) -> bool:
    return str(value).lower() == "true" if isinstance(value, str) else bool(value)


def _normalize_wrapped_needs_check(needs_check) -> dict:
    if isinstance(needs_check, str):
        try:
            return json.loads(needs_check)
        except (json.JSONDecodeError, ValueError):
            return {"required": False}
    return needs_check if isinstance(needs_check, dict) else {"required": False}


def wrap_final_state(final_state: dict, session_id: str | None = None) -> dict:
    result_data = final_state.get("result", {})
    state_delta = result_data.get("state_delta", {})
    needs_check = _normalize_wrapped_needs_check(result_data.get("needs_check", {"required": False}))

    wrapped_result = {
        "action_type": result_data.get("action_type", "exploration"),
        "narrative": result_data.get("narrative", ""),
        "companion_reactions": result_data.get("companion_reactions", ""),
        "needs_check": needs_check,
        "player_choices": result_data.get("player_choices", []),
        "state_delta": state_delta,
        "dice_results": result_data.get("dice_results", []),
        "ai_turns": result_data.get("ai_turns", []),
    }

    return {
        "result": json.dumps(wrapped_result, ensure_ascii=False),
        "action_type": wrapped_result["action_type"],
        "narrative": wrapped_result["narrative"],
        "state_delta": json.dumps(state_delta, ensure_ascii=False),
        "companion_reactions": wrapped_result["companion_reactions"],
        "dice_display": wrapped_result["dice_results"],
        "needs_check": needs_check,
        "combat_trigger": _to_bool(state_delta.get("combat_trigger", False)),
        "combat_end": _to_bool(state_delta.get("combat_end", False)),
        "success": True,
        "error": final_state.get("error", ""),
        "_conversation_id": session_id or "",
    }
