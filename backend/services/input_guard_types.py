from __future__ import annotations

from typing import Literal, TypedDict

Verdict = Literal["in_game", "off_topic", "rule_violation", "injection"]
ActionSource = Literal["human_input", "ai_generated_choice", "system_action", "ai_takeover"]


class GuardResult(TypedDict):
    verdict: Verdict
    reason: str
    refusal: str
