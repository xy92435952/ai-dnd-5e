"""Post-normalization adjudication checks for DM agent output."""

from __future__ import annotations

import re
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


_HIT_TEXT_RE = re.compile(
    r"(?<!未)命中|击中|刺中|砍中|打中|\bhits\b|\bstrikes true\b|\blands? (?:a |the )?(?:solid )?hit\b|\bconnects\b",
    re.IGNORECASE,
)
_MISS_TEXT_RE = re.compile(
    r"未命中|没有命中|没有击中|落空|偏出|擦肩|\bmiss(?:es|ed)?\b|\bgoes wide\b|\bfalls short\b",
    re.IGNORECASE,
)
_CRIT_TEXT_RE = re.compile(r"暴击|重创|\bcrit(?:ical)?\b", re.IGNORECASE)
_SAVE_SUCCESS_TEXT_RE = re.compile(
    r"豁免成功|成功抵抗|\bsave succeeds\b|\bsucceeds on (?:the )?save\b|\bpasses (?:the )?save\b",
    re.IGNORECASE,
)
_SAVE_FAILURE_TEXT_RE = re.compile(
    r"豁免失败|未能抵抗|\bsave fails\b|\bfails? (?:the )?save\b",
    re.IGNORECASE,
)


def _dice_outcome_kind(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None

    outcome = str(result.get("outcome") or "").strip().lower()
    label = str(result.get("label") or "").strip().lower()
    against = str(result.get("against") or "").strip().lower()
    if not outcome:
        return None
    if "暴击" in outcome or "critical" in outcome or re.search(r"\bcrit\b", outcome):
        return "crit"
    if "失误" in outcome or "大失败" in outcome or "fumble" in outcome:
        return "miss"
    if "未命中" in outcome or "miss" in outcome:
        return "miss"
    if "命中" in outcome or re.search(r"\bhit\b", outcome):
        return "hit"

    is_save_like = (
        "豁免" in label
        or "save" in label
        or "豁免" in against
        or re.search(r"\bdc\s*\d+", against)
    )
    if is_save_like and ("成功" in outcome or "success" in outcome or "pass" in outcome):
        return "save_success"
    if is_save_like and ("失败" in outcome or "fail" in outcome):
        return "save_failure"
    return None


def _narrative_contradicts_kind(narrative: str, kind: str) -> bool:
    if not narrative:
        return False
    if kind in {"hit", "crit"}:
        return bool(_MISS_TEXT_RE.search(narrative))
    if kind == "miss":
        return bool(_HIT_TEXT_RE.search(narrative) or _CRIT_TEXT_RE.search(narrative))
    if kind == "save_success":
        return bool(_SAVE_FAILURE_TEXT_RE.search(narrative))
    if kind == "save_failure":
        return bool(_SAVE_SUCCESS_TEXT_RE.search(narrative))
    return False


def _format_authoritative_dice_summary(dice_results: list) -> str:
    summaries = []
    for result in dice_results:
        if not isinstance(result, dict):
            continue
        label = str(result.get("label") or "骰子结果").strip()
        outcome = str(result.get("outcome") or "已结算").strip()
        total = result.get("total")
        against = str(result.get("against") or "").strip()
        total_part = f" total {total}" if total not in (None, "") else ""
        against_part = f" vs {against}" if against else ""
        summaries.append(f"{label}: {outcome}{total_part}{against_part}")
    joined = "; ".join(summaries) if summaries else "骰子结果已结算"
    return f"规则结果已按后端骰子结算：{joined}。请以后端命中、伤害、豁免和 HP 变化为准。"


def _repair_narrative_against_dice(data: dict, warnings: list[str]) -> None:
    dice_results = data.get("dice_results") if isinstance(data.get("dice_results"), list) else []
    narrative = str(data.get("narrative") or "")
    if any(
        kind and _narrative_contradicts_kind(narrative, kind)
        for kind in (_dice_outcome_kind(result) for result in dice_results)
    ):
        data["narrative"] = _format_authoritative_dice_summary(dice_results)
        warnings.append("replaced combat narrative because it contradicted backend dice results")

    for turn in data.get("ai_turns", []) if isinstance(data.get("ai_turns"), list) else []:
        if not isinstance(turn, dict):
            continue
        turn_dice = turn.get("dice_results") if isinstance(turn.get("dice_results"), list) else []
        turn_narrative = str(turn.get("narrative") or "")
        if any(
            kind and _narrative_contradicts_kind(turn_narrative, kind)
            for kind in (_dice_outcome_kind(result) for result in turn_dice)
        ):
            turn["narrative"] = _format_authoritative_dice_summary(turn_dice)
            warnings.append("replaced AI combat narrative because it contradicted backend dice results")


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
        _repair_narrative_against_dice(data, warnings)

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
