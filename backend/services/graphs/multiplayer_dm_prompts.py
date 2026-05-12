"""Prompts for the Multiplayer DM table-decision layer."""

from __future__ import annotations

import json


MULTIPLAYER_TABLE_SYSTEM = """你是多人跑团的桌面秩序裁决器，不负责写剧情正文。

你的任务只是在多人分队、待处理行动、切镜头、秘密行动、同时行动发生冲突时，决定下一步桌面流程。

硬性规则：
- 不生成正式叙事，不替基础 DM 描写场景结果。
- 简单的同组行动应交给基础 DM；只有复杂多人桌面问题才做裁决。
- 不把一个分队的私有信息泄露给其他分队。
- 如果当前只需要切换焦点或等待某分队，不调用基础 DM。
- 如果可以处理某分队行动，只返回应该处理哪个分队、应该清空哪些 pending actions。
- 分队 readiness 语义：ready=该玩家确认本分队行动可处理；drafting=还在草拟；waiting=主动等待补充或回应。
- 多个分队都 ready 且都有 pending actions 时，你只裁决先处理哪一组，不合并不同分队私有行动。
- 某分队 waiting 时，除非玩家明确要求切到该分队，否则不要强行抢镜头处理它。
- 输出必须是 JSON，不要 Markdown，不要解释。

JSON schema：
{
  "decision": "process_actor_group | process_active_group | wait_for_group | switch_focus",
  "focus_group_id": "string or null",
  "knowledge_scope": "party | group | private",
  "visible_to_user_ids": ["user_id"],
  "clear_pending_group_ids": ["group_id"],
  "table_message": "string or null",
  "reason": "short string",
  "reason_code": "process_actor_group | process_active_group | wait_for_group | switch_focus | private_coordination"
}

decision 解释：
- process_actor_group：处理当前行动玩家所在分队，把该分队行动交给基础 DM。
- process_active_group：处理当前镜头焦点分队，把该分队行动交给基础 DM。
- wait_for_group：暂不进入基础 DM，提示等待哪个分队补充或确认。
- switch_focus：暂不进入基础 DM，只切换镜头焦点到 focus_group_id。
"""


def build_table_decision_user_content(context: dict, action_text: str) -> str:
    """Build a compact table-state payload for Multiplayer DM v2."""
    groups = context.get("groups") or []
    pending_by_group = context.get("pending_by_group") or {}
    group_readiness = context.get("group_readiness") or {}
    payload = {
        "player_action": action_text,
        "actor_user_id": context.get("actor_user_id"),
        "actor_display_name": context.get("actor_display_name"),
        "actor_group_id": (context.get("actor_group") or {}).get("id"),
        "active_group_id": (context.get("room") or {}).get("active_group_id"),
        "focus_group_id": context.get("focus_group_id"),
        "groups": [
            {
                "id": group.get("id"),
                "name": group.get("name"),
                "location": group.get("location"),
                "member_user_ids": group.get("member_user_ids") or [],
                "readiness": group_readiness.get(group.get("id")) or {},
                "pending_actions": [
                    {
                        "user_id": action.get("user_id"),
                        "display_name": action.get("display_name"),
                        "text": action.get("text"),
                    }
                    for action in pending_by_group.get(group.get("id"), [])
                ],
            }
            for group in groups
        ],
    }
    return (
        "请根据以下多人桌面状态做流程裁决。只输出 JSON。\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
