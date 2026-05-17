from services.graphs.multiplayer_dm_state import MultiplayerTableDecision


def build_table_decision_payload(
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


def resolve_visible_users(table_decision: MultiplayerTableDecision, focus_group: dict | None) -> list[str]:
    if table_decision.visible_to_user_ids:
        return table_decision.visible_to_user_ids
    if table_decision.knowledge_scope == "party":
        return []
    return list((focus_group or {}).get("member_user_ids") or [])


def default_table_message(table_decision: MultiplayerTableDecision, focus_group: dict | None) -> str:
    group_name = (focus_group or {}).get("name") or (focus_group or {}).get("id") or "目标分队"
    if table_decision.decision == "switch_focus":
        return f"镜头转向{group_name}，请该分队决定下一步行动。"
    return f"先等待{group_name}补充或确认行动。"


def build_effective_action_text(action_text: str, context: dict) -> str:
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
                f"{display_name_for_user(user_id, members_by_user_id)}: {status_labels.get(status, status)}"
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


def display_name_for_user(user_id: str, members_by_user_id: dict) -> str:
    member = members_by_user_id.get(user_id) or {}
    return member.get("display_name") or member.get("username") or user_id
