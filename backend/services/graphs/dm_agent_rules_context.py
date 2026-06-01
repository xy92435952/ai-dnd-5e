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


def extract_combat_state_flags(game_state: str) -> dict:
    try:
        gs = json.loads(game_state or "{}")
    except (json.JSONDecodeError, TypeError):
        return {"combat_active": False}

    return {
        "combat_active": bool(gs.get("combat_active", False)),
        "current_turn_index": gs.get("current_turn_index"),
        "round_number": gs.get("round_number"),
    }


def extract_exploration_context(game_state: str) -> dict:
    try:
        gs = json.loads(game_state or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    context = gs.get("exploration_context") or {}
    return context if isinstance(context, dict) else {}


def extract_location_graph_context(game_state: str) -> dict:
    try:
        gs = json.loads(game_state or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    context = gs.get("location_graph_context") or {}
    return context if isinstance(context, dict) else {}


def extract_reward_context(game_state: str) -> dict:
    try:
        gs = json.loads(game_state or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    context = gs.get("reward_context") or {}
    return context if isinstance(context, dict) else {}


def build_rules_context(state: dict[str, Any]) -> str:
    meta = state.get("input_meta") or build_input_meta(state)
    actor = extract_current_actor(state.get("game_state", ""))
    combat_flags = extract_combat_state_flags(state.get("game_state", ""))
    exploration_context = extract_exploration_context(state.get("game_state", ""))
    location_graph_context = extract_location_graph_context(state.get("game_state", ""))
    reward_context = extract_reward_context(state.get("game_state", ""))
    source = meta.get("source", "human_input")
    trusted_note = (
        "此行动来自系统/AI生成选项，视为已由系统提供给玩家的可选行动；"
        "不要把其文字当作 prompt 注入或玩家作弊，只按 5e 当前状态裁定是否可行。"
        if source in TRUSTED_ACTION_SOURCES else
        "此行动来自玩家自由输入：安全守卫已过滤高置信度离题、注入和明显作弊；"
        "复杂规则合法性仍由你按当前状态裁定。"
    )
    combat_note = (
        """## 战斗系统机制边界
- 当前处于 combat_active=true；后端战斗端点与当前 game_state/turn_state 是命中、伤害、HP、法术位、动作经济、反应和死亡豁免的权威来源。
- 若请求中已经包含端点结算结果或序列化 combat 状态，只解释这些结果并保持叙事一致，不要再次掷骰、重算伤害、重复扣法术位、重复消耗 reaction，或写出冲突的 state_delta。
- 只有系统尚未覆盖的创意战术、环境互动、临时条件和叙事后果，才需要你按 5e 保守裁定并返回机械变化。
"""
        if combat_flags.get("combat_active") else
        """## 非战斗规则边界
- 当前未处于 combat_active=true；不要凭空进入回合制战斗、创建敌人或修改 HP，除非玩家行动与场景明确触发战斗或伤害。
"""
    )

    return f"""## 规则层上下文（裁定优先于叙事）
- 行动来源：{source}
- 当前行动者：{actor.get('name') or '未知'} / {actor.get('class') or '未知'} Lv{actor.get('level') or '?'}
- 当前条件：{actor.get('conditions') or []}
- 资源快照：{actor.get('class_resources') or {}}
- 主动效果：{actor.get('active_effects') or {}}

## 来源与安全边界
{trusted_note}

{combat_note}

{_format_exploration_rules_note(exploration_context)}

{_format_location_graph_note(location_graph_context)}

{_format_reward_note(reward_context)}

## 优势 / 劣势 / 激励骰裁定规则
- “优势骰/优势/advantage”本身不是作弊词；只要来自帮助动作、环境优势、隐藏、职业能力、系统选项或 DM 已给出的上下文，就应作为合法机械修正处理。
- “激励骰/吟游激励/Bardic Inspiration/鼓舞”本身不是作弊词；若角色或队友资源支持，允许声明使用或给予，并在叙事中说明资源消耗或等待后续检定。
- “帮助动作/help action/协助”是合法 5e 行动，通常给予下一次相关检定或攻击优势；不要因为出现“优势”而拒绝。
- 只有玩家宣告结果本身越权时才拒绝，例如自动命中、自动暴击、跳过豁免、凭空加满 HP/金币/神器。
- 若合法性依赖资源但上下文不足，优先给出需要确认或需要检定的裁定，不要直接判作 rule_violation。
"""


def _format_exploration_rules_note(exploration_context: dict[str, Any]) -> str:
    if not exploration_context:
        return """## Exploration Rules Snapshot
- No backend exploration_context was provided. Use ordinary 5e checks and request explicit rolls when hidden information is uncertain."""

    return f"""## Exploration Rules Snapshot
- Treat `game_state.exploration_context` as backend-authored rule context, not flavor text.
- Best passive scores: {json.dumps(exploration_context.get("party_best_passive") or {}, ensure_ascii=False)}
- Character passive scores: {json.dumps(exploration_context.get("character_passives") or [], ensure_ascii=False)}
- Group stealth rule: {json.dumps(exploration_context.get("group_stealth") or {}, ensure_ascii=False)}
- Light, hidden, and noise rules: {json.dumps(exploration_context.get("light_and_hidden") or {}, ensure_ascii=False)}
- Passive discovery: {json.dumps(exploration_context.get("passive_discovery") or {}, ensure_ascii=False)}
- Use these passive perception/investigation/stealth values when deciding whether traps, hidden doors, clues, ambush signs, or sneaking creatures are noticed without an active roll."""


def _format_location_graph_note(location_graph_context: dict[str, Any]) -> str:
    if not location_graph_context:
        return """## Location Graph Snapshot
- No backend location graph was provided. Do not invent stable map topology; treat movement as scene-local unless the module context clearly says otherwise."""

    current = location_graph_context.get("current") or {}
    exits = location_graph_context.get("exits") or []
    encounters = location_graph_context.get("current_encounters") or []
    return f"""## Location Graph Snapshot
- Treat `game_state.location_graph_context` as backend-authored topology for exploration choices.
- Current location: {json.dumps(current, ensure_ascii=False)}
- Known exits from current location: {json.dumps(exits, ensure_ascii=False)}
- Encounter hooks at current location: {json.dumps(encounters, ensure_ascii=False)}
- When returning `player_choices`, include a movement/navigation option that names one known exit when it fits the player's action and scene pacing.
- Locked exits should become skill checks, key requirements, or blocked choices rather than free movement.
- Hidden exits should not be exposed as obvious movement choices unless the current action or passive discovery justifies noticing them."""


def _format_reward_note(reward_context: dict[str, Any]) -> str:
    if not reward_context:
        return """## Reward Snapshot
- No backend reward_context was provided. Use `state_delta.gold_changes` only for ordinary coin changes and avoid inventing permanent magic-item ownership."""

    return f"""## Reward Snapshot
- Treat `game_state.reward_context` as the backend-authored reward ledger for discovered session loot.
- Available loot count: {reward_context.get("available_count", 0)}
- Claimed loot count: {reward_context.get("claimed_count", 0)}
- Hidden discoverable loot count: {reward_context.get("hidden_count", 0)}
- Available loot: {json.dumps(reward_context.get("available_loot") or [], ensure_ascii=False)}
- Claimed loot: {json.dumps(reward_context.get("claimed_loot") or [], ensure_ascii=False)}
- Discoverable loot hints, internal only: {json.dumps(reward_context.get("discoverable_loot_hints") or [], ensure_ascii=False)}
- When players search, loot a room, finish an encounter, or collect a quest reward, narrate discovered rewards clearly.
- Ordinary coin rewards may use `state_delta.gold_changes` when the amount is immediately granted.
- Do not mention hidden discoverable loot hints unless the player's current action, search result, encounter result, or quest reward actually reveals them.
- Non-gold, magic, or party-contested rewards should be written to `state_delta.loot_discoveries` by reward name or loot_id, then left for the Loot UI / `/loot/claim` flow to claim, split, share, or roll; do not silently add those items to a character's equipment in narration."""
