"""Post-normalization adjudication checks for DM agent output."""

from __future__ import annotations

from typing import Any


def _list_has_items(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def _clear_list_delta(delta: dict, key: str, warnings: list[str], reason: str) -> None:
    if _list_has_items(delta.get(key)):
        delta[key] = []
        warnings.append(reason)


def _clear_flag(delta: dict, key: str, warnings: list[str], reason: str) -> None:
    if bool(delta.get(key)):
        delta[key] = False
        warnings.append(reason)


def validate_dm_output_adjudication(data: dict, state: dict | None = None) -> tuple[dict, list[str]]:
    """Repair DM output that conflicts with rule resolution boundaries.

    The LLM may narrate uncertainty, ask for a check, or explain already-resolved
    endpoint results. It should not simultaneously apply mechanical outcomes
    that have not been adjudicated by dice or by the local rule engine.
    """
    if not isinstance(data, dict):
        return data, []

    state = state or {}
    warnings: list[str] = []
    delta = data.get("state_delta")
    if not isinstance(delta, dict):
        return data, warnings

    needs_check = data.get("needs_check") if isinstance(data.get("needs_check"), dict) else {}
    if needs_check.get("required"):
        _clear_list_delta(
            delta,
            "characters",
            warnings,
            "removed character state changes because the action still requires a check",
        )
        _clear_list_delta(
            delta,
            "enemies",
            warnings,
            "removed enemy state changes because the action still requires a check",
        )
        _clear_list_delta(
            delta,
            "gold_changes",
            warnings,
            "removed gold changes because the action still requires a check",
        )
        _clear_list_delta(
            delta,
            "trap_updates",
            warnings,
            "removed trap updates because the action still requires a check",
        )
        _clear_list_delta(
            delta,
            "trap_triggers",
            warnings,
            "removed trap triggers because the action still requires a check",
        )
        _clear_list_delta(
            delta,
            "trap_attacks",
            warnings,
            "removed trap attacks because the action still requires a check",
        )
        _clear_list_delta(
            delta,
            "trap_disarms",
            warnings,
            "removed trap disarms because the action still requires a check",
        )
        _clear_flag(
            delta,
            "combat_trigger",
            warnings,
            "removed combat trigger because the action still requires a check",
        )
        _clear_flag(
            delta,
            "combat_end",
            warnings,
            "removed combat end because the action still requires a check",
        )
        if _list_has_items(data.get("ai_turns")):
            data["ai_turns"] = []
            warnings.append("removed AI turns because the player action still requires a check")

    combat_active = bool(state.get("combat_active"))
    if combat_active:
        _clear_flag(
            delta,
            "combat_trigger",
            warnings,
            "removed combat trigger because combat is already active",
        )
    else:
        _clear_flag(
            delta,
            "combat_end",
            warnings,
            "removed combat end because combat is not active",
        )
        if not bool(delta.get("combat_trigger")):
            _clear_list_delta(
                delta,
                "enemies",
                warnings,
                "removed enemy state changes outside combat without a combat trigger",
            )

    if warnings:
        data["adjudication_warnings"] = warnings
    else:
        data.pop("adjudication_warnings", None)

    return data, warnings
