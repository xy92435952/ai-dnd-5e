from __future__ import annotations

from dataclasses import dataclass

from services.dnd_rules import get_incapacitating_reasons, normalize_conditions


REACTION_BLOCKING_CONDITIONS = frozenset({
    "confused",
})


@dataclass
class CombatActionRuleError(Exception):
    detail: str
    status_code: int = 400

    def __str__(self) -> str:
        return self.detail


def incapacitating_reasons(actor: dict | object | None) -> list[str]:
    return get_incapacitating_reasons(actor)


def _actor_conditions(actor: dict | object | None) -> list[str]:
    if not actor:
        return []
    if isinstance(actor, dict):
        return normalize_conditions(actor.get("conditions") or [])
    return normalize_conditions(getattr(actor, "conditions", None) or [])


def reaction_blocking_reasons(actor: dict | object | None) -> list[str]:
    reasons = incapacitating_reasons(actor)
    for condition in _actor_conditions(actor):
        if condition in REACTION_BLOCKING_CONDITIONS and condition not in reasons:
            reasons.append(condition)
    return reasons


def validate_can_take_action(actor: dict | object | None) -> None:
    reasons = incapacitating_reasons(actor)
    if reasons:
        raise CombatActionRuleError(f"Character cannot act while {', '.join(reasons)}")


def validate_can_take_reaction(actor: dict | object | None) -> None:
    reasons = reaction_blocking_reasons(actor)
    if reasons:
        raise CombatActionRuleError(f"Character cannot react while {', '.join(reasons)}")


def can_take_reaction(actor: dict | object | None) -> bool:
    return not reaction_blocking_reasons(actor)
