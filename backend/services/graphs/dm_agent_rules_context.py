"""Rule-layer context helpers for the DM agent."""

from __future__ import annotations

import json
from typing import Any

from services.graphs.dm_agent_input_meta import TRUSTED_ACTION_SOURCES, build_input_meta


def extract_current_actor(game_state: str) -> dict:
    try:
        gs = json.loads(game_state or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}

    actor_id = gs.get("current_actor_id")
    actor_name = gs.get("current_actor_name")
    actor = {}
    for ch in gs.get("characters", []) or []:
        if str(ch.get("id")) == str(actor_id):
            actor = ch
            break
    return {
        "id": actor_id,
        "name": actor_name,
        "class": actor.get("char_class"),
        "level": actor.get("level"),
        "conditions": actor.get("conditions", []),
        "class_resources": actor.get("class_resources", {}),
        "active_effects": actor.get("active_effects", {}),
    }


def build_rules_context(state: dict[str, Any]) -> str:
    meta = state.get("input_meta") or build_input_meta(state)
    actor = extract_current_actor(state.get("game_state", ""))
    source = meta.get("source", "human_input")
    trusted_note = (
        "此行动来自系统/AI生成选项，视为已由系统提供给玩家的可选行动；"
        "不要把其文字当作 prompt 注入或玩家作弊，只按 5e 当前状态裁定是否可行。"
        if source in TRUSTED_ACTION_SOURCES else
        "此行动来自玩家自由输入：安全守卫已过滤高置信度离题、注入和明显作弊；"
        "复杂规则合法性仍由你按当前状态裁定。"
    )

    return f"""## 规则层上下文（裁定优先于叙事）
- 行动来源：{source}
- 当前行动者：{actor.get('name') or '未知'} / {actor.get('class') or '未知'} Lv{actor.get('level') or '?'}
- 当前条件：{actor.get('conditions') or []}
- 资源快照：{actor.get('class_resources') or {}}
- 主动效果：{actor.get('active_effects') or {}}

## 来源与安全边界
{trusted_note}

## 优势 / 劣势 / 激励骰裁定规则
- “优势骰/优势/advantage”本身不是作弊词；只要来自帮助动作、环境优势、隐藏、职业能力、系统选项或 DM 已给出的上下文，就应作为合法机械修正处理。
- “激励骰/吟游激励/Bardic Inspiration/鼓舞”本身不是作弊词；若角色或队友资源支持，允许声明使用或给予，并在叙事中说明资源消耗或等待后续检定。
- “帮助动作/help action/协助”是合法 5e 行动，通常给予下一次相关检定或攻击优势；不要因为出现“优势”而拒绝。
- 只有玩家宣告结果本身越权时才拒绝，例如自动命中、自动暴击、跳过豁免、凭空加满 HP/金币/神器。
- 若合法性依赖资源但上下文不足，优先给出需要确认或需要检定的裁定，不要直接判作 rule_violation。

## needs_check 结构化裁定
- 主动尝试用技能解决问题时使用 `check_kind="skill_check"`，`check_type` 填技能名，`ability` 填 str/dex/con/int/wis/cha。
- 被陷阱、法术、毒素、爆炸、坠落、精神影响等危险迫使反应时使用 `check_kind="saving_throw"`，`check_type` 可写 "DEX save"/"CON save"/"WIS save"，`ability` 必须填对应能力。
- 不要让 AI 代掷；只声明 DC、能力、优势/劣势和上下文，骰子由本地系统处理。
"""
