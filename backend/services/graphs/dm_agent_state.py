"""
State definition for the DM Agent LangGraph.
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage


def add_messages(existing: list, new: list) -> list:
    """Append new messages, keep last 20 (10 turns)."""
    combined = (existing or []) + (new or [])
    return combined[-20:]


class DMAgentState(TypedDict):
    player_action: str
    action_source: str
    game_state: str
    module_context: str
    campaign_memory: str
    retrieved_context: str
    messages: Annotated[list[BaseMessage], add_messages]
    dice_pool: str
    combat_active: bool
    llm_output: str
    input_meta: dict
    rules_context: str
    memory_context: str
    guard_verdict: str
    guard_refusal: str
    result: dict
    error: str
