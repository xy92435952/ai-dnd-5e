from __future__ import annotations

from dataclasses import dataclass

from services.dnd_rules import get_incapacitating_reasons


@dataclass
class CombatActionRuleError(Exception):
    detail: str
    status_code: int = 400

    def __str__(self) -> str:
        return self.detail


def incapacitating_reasons(actor: dict | object | None) -> list[str]:
    return get_incapacitating_reasons(actor)


def validate_can_take_action(actor: dict | object | None) -> None:
    reasons = incapacitating_reasons(actor)
    if reasons:
        raise CombatActionRuleError(f"Character cannot act while {', '.join(reasons)}")


def validate_can_take_reaction(actor: dict | object | None) -> None:
    reasons = incapacitating_reasons(actor)
    if reasons:
        raise CombatActionRuleError(f"Character cannot react while {', '.join(reasons)}")


def can_take_reaction(actor: dict | object | None) -> bool:
    return not incapacitating_reasons(actor)
