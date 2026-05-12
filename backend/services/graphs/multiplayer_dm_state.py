"""State types for the Multiplayer DM coordinator."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MultiplayerDMDecision(BaseModel):
    """Decision returned before the base DM Agent is invoked."""

    should_call_base_dm: bool = True
    effective_action_text: str = ""
    table_message: str | None = None
    table_reason: str = ""
    table_decision: dict = Field(default_factory=dict)
    actor_group_id: str | None = None
    focus_group_id: str | None = None
    clear_pending_group_ids: list[str] = Field(default_factory=list)
    room_updates: dict = Field(default_factory=dict)
    visibility: dict = Field(default_factory=dict)


class MultiplayerTableDecision(BaseModel):
    """LLM/table-policy decision for complex multiplayer coordination."""

    decision: Literal[
        "process_actor_group",
        "process_active_group",
        "wait_for_group",
        "switch_focus",
    ] = "process_actor_group"
    focus_group_id: str | None = None
    knowledge_scope: Literal["party", "group", "private"] = "group"
    visible_to_user_ids: list[str] = Field(default_factory=list)
    clear_pending_group_ids: list[str] = Field(default_factory=list)
    table_message: str | None = None
    reason: str = ""
    reason_code: Literal[
        "process_actor_group",
        "process_active_group",
        "wait_for_group",
        "switch_focus",
        "private_coordination",
    ] | None = None
