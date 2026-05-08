"""Input metadata helpers for the DM agent."""

from __future__ import annotations

import re
from typing import Any

TRUSTED_ACTION_SOURCES: set[str] = {"ai_generated_choice", "system_action", "ai_takeover"}


def build_input_meta(state: dict[str, Any]) -> dict:
    source = state.get("action_source") or "human_input"
    action = (state.get("player_action") or "").strip()
    return {
        "source": source,
        "is_human_input": source not in TRUSTED_ACTION_SOURCES,
        "length": len(action),
        "has_structural_tags": bool(re.search(r"<[^>]+>", action)),
    }
