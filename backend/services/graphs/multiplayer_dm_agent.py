"""Deterministic Multiplayer DM coordinator.

Simple cases stay deterministic. Complex table-management cases can use a thin
v2 decision layer before the existing base DM Agent is invoked.
"""

from __future__ import annotations

import inspect
import json
import logging
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from models import Session
from services.graphs.dm_agent_output_normalizer import strip_code_block
from services.graphs.multiplayer_dm_context import build_multiplayer_dm_context
from services.graphs.multiplayer_dm_prompts import (
    MULTIPLAYER_TABLE_SYSTEM,
    build_table_decision_user_content,
)
from services.graphs.multiplayer_dm_state import MultiplayerDMDecision, MultiplayerTableDecision

logger = logging.getLogger(__name__)

TableDecider = Callable[[dict, str], Any]

_TABLE_DECISION_KEYWORDS = (
    "同时",
    "一起",
    "分头",
    "切镜头",
    "切到",
    "转到",
    "镜头",
    "秘密",
    "悄悄",
    "私下",
    "等一下",
    "先等",
    "先看",
)


async def run_multiplayer_dm_agent(
    *,
    db: AsyncSession,
    session: Session,
    actor_user_id: str,
    action_text: str,
    table_decider: TableDecider | None = None,
) -> MultiplayerDMDecision:
    """Build the effective action text and room updates for a multiplayer turn."""
    context = await build_multiplayer_dm_context(db, session, actor_user_id)
    v1_decision = _build_deterministic_decision(action_text, context)
    if not _should_use_table_decision(context, action_text):
        return v1_decision

    try:
        table_decision = await _run_table_decision(
            context,
            action_text,
            table_decider=table_decider,
        )
        return _apply_table_decision(
            table_decision=table_decision,
            action_text=action_text,
            context=context,
            fallback=v1_decision,
        )
    except Exception as exc:
        logger.warning("Multiplayer DM table decision failed; falling back to v1: %s", exc)
        return v1_decision


def _build_deterministic_decision(action_text: str, context: dict) -> MultiplayerDMDecision:
    """Build the v1 deterministic decision for simple/safe multiplayer actions."""
    focus_group = context.get("focus_group")
    focus_group_id = context.get("focus_group_id")
    focus_pending = context.get("focus_pending_actions") or []
    actor_group = context.get("actor_group")
    effective_action = _build_effective_action_text(action_text, context)

    clear_group_ids = [focus_group_id] if focus_group_id and focus_pending else []
    room_updates = {}
    if actor_group and actor_group.get("id") != (context.get("room") or {}).get("active_group_id"):
        room_updates["active_group_id"] = actor_group.get("id")

    visible_to = focus_group.get("member_user_ids", []) if focus_group else []
    return MultiplayerDMDecision(
        should_call_base_dm=True,
        effective_action_text=effective_action,
        actor_group_id=actor_group.get("id") if actor_group else None,
        focus_group_id=focus_group_id,
        clear_pending_group_ids=clear_group_ids,
        room_updates=room_updates,
        visibility={
            "scope": "group" if visible_to else "party",
            "group_id": focus_group_id,
            "visible_to_user_ids": visible_to,
        },
    )


def _should_use_table_decision(context: dict, action_text: str) -> bool:
    """Return True only when multiplayer table order needs a v2 decision."""
    groups = context.get("groups") or []
    if len(groups) <= 1:
        return False

    normalized_action = (action_text or "").strip()
    if any(keyword in normalized_action for keyword in _TABLE_DECISION_KEYWORDS):
        return True

    if _readiness_policy_can_stay_deterministic(context):
        return False

    has_focus_pending = bool(context.get("focus_pending_actions"))
    has_other_pending = bool(context.get("other_pending_counts"))
    return has_focus_pending and has_other_pending


def _readiness_policy_can_stay_deterministic(context: dict) -> bool:
    """Avoid v2 when readiness makes the table order obvious."""
    focus_group = context.get("focus_group") or {}
    focus_group_id = context.get("focus_group_id")
    if not focus_group_id or not context.get("focus_pending_actions"):
        return False

    group_readiness = context.get("group_readiness") or {}
    if not _group_all_ready(focus_group, group_readiness):
        return False

    groups = context.get("groups") or []
    pending_by_group = context.get("pending_by_group") or {}
    for group in groups:
        group_id = group.get("id")
        if group_id == focus_group_id:
            continue
        if not pending_by_group.get(group_id):
            continue
        if _group_all_ready(group, group_readiness):
            return False
    return True


def _group_all_ready(group: dict, group_readiness: dict) -> bool:
    members = list(group.get("member_user_ids") or [])
    if not members:
        return False
    readiness = group_readiness.get(group.get("id")) or {}
    return all(readiness.get(user_id) == "ready" for user_id in members)


async def _run_table_decision(
    context: dict,
    action_text: str,
    *,
    table_decider: TableDecider | None = None,
) -> MultiplayerTableDecision:
    if table_decider:
        raw = table_decider(context, action_text)
        if inspect.isawaitable(raw):
            raw = await raw
        return _parse_table_decision(raw)

    from langchain_core.messages import HumanMessage, SystemMessage
    from services.llm import get_llm

    llm = get_llm(temperature=0.2, max_tokens=900)
    resp = await llm.ainvoke([
        SystemMessage(content=MULTIPLAYER_TABLE_SYSTEM),
        HumanMessage(content=build_table_decision_user_content(context, action_text)),
    ])
    return _parse_table_decision(resp.content)


def _parse_table_decision(raw: Any) -> MultiplayerTableDecision:
    if isinstance(raw, MultiplayerTableDecision):
        return raw
    if isinstance(raw, dict):
        return MultiplayerTableDecision.model_validate(raw)
    if isinstance(raw, str):
        text = strip_code_block(raw)
        return MultiplayerTableDecision.model_validate(json.loads(text))
    raise ValueError(f"unsupported table decision payload: {type(raw)!r}")


def _apply_table_decision(
    *,
    table_decision: MultiplayerTableDecision,
    action_text: str,
    context: dict,
    fallback: MultiplayerDMDecision,
) -> MultiplayerDMDecision:
    groups = context.get("groups") or []
    group_by_id = {group.get("id"): group for group in groups if group.get("id")}
    actor_group_id = (context.get("actor_group") or {}).get("id")
    active_group_id = (context.get("active_group") or {}).get("id")

    if table_decision.decision == "process_actor_group":
        focus_group_id = table_decision.focus_group_id or actor_group_id
        return _build_process_group_decision(
            table_decision=table_decision,
            action_text=action_text,
            context=context,
            focus_group_id=focus_group_id,
            fallback=fallback,
        )

    if table_decision.decision == "process_active_group":
        focus_group_id = table_decision.focus_group_id or active_group_id or actor_group_id
        return _build_process_group_decision(
            table_decision=table_decision,
            action_text=action_text,
            context=context,
            focus_group_id=focus_group_id,
            fallback=fallback,
        )

    if table_decision.decision in ("switch_focus", "wait_for_group"):
        focus_group_id = table_decision.focus_group_id or active_group_id or actor_group_id
        focus_group = group_by_id.get(focus_group_id) if focus_group_id else None
        visible_to = _resolve_visible_users(table_decision, focus_group)
        should_switch = table_decision.decision == "switch_focus" and focus_group_id
        return MultiplayerDMDecision(
            should_call_base_dm=False,
            effective_action_text="",
            table_message=table_decision.table_message or _default_table_message(table_decision, focus_group),
            table_reason=table_decision.reason,
            table_decision=_build_table_decision_payload(
                table_decision=table_decision,
                actor_group_id=actor_group_id,
                focus_group_id=focus_group_id,
            ),
            actor_group_id=actor_group_id,
            focus_group_id=focus_group_id,
            clear_pending_group_ids=[],
            room_updates={"active_group_id": focus_group_id} if should_switch else {},
            visibility={
                "scope": table_decision.knowledge_scope,
                "group_id": focus_group_id,
                "visible_to_user_ids": visible_to,
            },
        )

    return fallback


def _build_process_group_decision(
    *,
    table_decision: MultiplayerTableDecision,
    action_text: str,
    context: dict,
    focus_group_id: str | None,
    fallback: MultiplayerDMDecision,
) -> MultiplayerDMDecision:
    groups = context.get("groups") or []
    group_by_id = {group.get("id"): group for group in groups if group.get("id")}
    focus_group = group_by_id.get(focus_group_id) if focus_group_id else None
    if not focus_group:
        return fallback

    decision_context = {
        **context,
        "focus_group": focus_group,
        "focus_group_id": focus_group_id,
        "focus_pending_actions": list((context.get("pending_by_group") or {}).get(focus_group_id, [])),
        "other_pending_counts": {
            group.get("id"): len((context.get("pending_by_group") or {}).get(group.get("id"), []))
            for group in groups
            if group.get("id") != focus_group_id and (context.get("pending_by_group") or {}).get(group.get("id"))
        },
    }
    clear_group_ids = table_decision.clear_pending_group_ids or (
        [focus_group_id] if decision_context["focus_pending_actions"] else []
    )
    visible_to = _resolve_visible_users(table_decision, focus_group)
    room_updates = {}
    if focus_group_id and focus_group_id != (context.get("room") or {}).get("active_group_id"):
        room_updates["active_group_id"] = focus_group_id

    return MultiplayerDMDecision(
        should_call_base_dm=True,
        effective_action_text=_build_effective_action_text(action_text, decision_context),
        table_message=table_decision.table_message,
        table_reason=table_decision.reason,
        table_decision=_build_table_decision_payload(
            table_decision=table_decision,
            actor_group_id=(context.get("actor_group") or {}).get("id"),
            focus_group_id=focus_group_id,
        ),
        actor_group_id=(context.get("actor_group") or {}).get("id"),
        focus_group_id=focus_group_id,
        clear_pending_group_ids=clear_group_ids,
        room_updates=room_updates,
        visibility={
            "scope": table_decision.knowledge_scope,
            "group_id": focus_group_id,
            "visible_to_user_ids": visible_to,
        },
    )


def _build_table_decision_payload(
    *,
    table_decision: MultiplayerTableDecision,
    actor_group_id: str | None,
    focus_group_id: str | None,
) -> dict:
    """Compact structured table decision for clients; no visibility authority implied."""
    reason_code = table_decision.reason_code or table_decision.decision
    waiting_group_id = focus_group_id if table_decision.decision == "wait_for_group" else None
    target_group_id = focus_group_id if table_decision.decision in {
        "switch_focus",
        "process_actor_group",
        "process_active_group",
    } else None
    return {
        "decision": table_decision.decision,
        "reason_code": reason_code,
        "target_group_id": target_group_id,
        "waiting_group_id": waiting_group_id,
        "actor_group_id": actor_group_id,
        "focus_group_id": focus_group_id,
        "knowledge_scope": table_decision.knowledge_scope,
    }


def _resolve_visible_users(table_decision: MultiplayerTableDecision, focus_group: dict | None) -> list[str]:
    if table_decision.visible_to_user_ids:
        return table_decision.visible_to_user_ids
    if table_decision.knowledge_scope == "party":
        return []
    return list((focus_group or {}).get("member_user_ids") or [])


def _default_table_message(table_decision: MultiplayerTableDecision, focus_group: dict | None) -> str:
    group_name = (focus_group or {}).get("name") or (focus_group or {}).get("id") or "目标分队"
    if table_decision.decision == "switch_focus":
        return f"镜头转向{group_name}，请该分队决定下一步行动。"
    return f"先等待{group_name}补充或确认行动。"


def _build_effective_action_text(action_text: str, context: dict) -> str:
    base = (action_text or "").strip()
    focus_group = context.get("focus_group") or {}
    focus_pending = context.get("focus_pending_actions") or []
    other_counts = context.get("other_pending_counts") or {}
    group_readiness = context.get("group_readiness") or {}
    members_by_user_id = context.get("members_by_user_id") or {}
    lines = [base]

    if focus_group:
        members = ", ".join(focus_group.get("member_user_ids") or []) or "暂无成员"
        lines.extend([
            "",
            "【多人分队上下文】",
            f"当前焦点分队：{focus_group.get('name') or focus_group.get('id') or '当前分队'}",
            f"位置：{focus_group.get('location') or '当前场景'}",
            f"成员用户：{members}",
        ])
        readiness = group_readiness.get(focus_group.get("id")) or {}
        if readiness:
            status_labels = {
                "drafting": "草拟中",
                "ready": "已确认",
                "waiting": "等待中",
            }
            summary = "；".join(
                f"{_display_name_for_user(user_id, members_by_user_id)}: {status_labels.get(status, status)}"
                for user_id, status in readiness.items()
            )
            lines.append(f"分队确认状态：{summary}")

    if focus_pending:
        lines.extend(["", "【同分队队友意图】"])
        for action in focus_pending:
            speaker = action.get("display_name") or action.get("user_id") or "队友"
            text = action.get("text") or ""
            if text:
                lines.append(f"- {speaker}：{text}")

    if other_counts:
        labels = []
        group_by_id = {group.get("id"): group for group in context.get("groups") or []}
        for group_id, count in other_counts.items():
            group_name = (group_by_id.get(group_id) or {}).get("name") or group_id
            labels.append(f"{group_name} {count} 条")
        lines.extend(["", f"其他分队待处理：{'；'.join(labels)}"])

    return "\n".join(line for line in lines if line is not None).strip()


def _display_name_for_user(user_id: str, members_by_user_id: dict) -> str:
    member = members_by_user_id.get(user_id) or {}
    return member.get("display_name") or member.get("username") or user_id
