"""
WebSocket 事件 schema — 所有 /ws/sessions/{id} 广播的事件在这里**唯一定义**。

设计原则：
  - 每个事件一个 Pydantic 类，type 字段用 Literal 固定
  - 通过 WSEvent Union + discriminator='type' 做 tagged union
  - 广播发送侧：构造 Pydantic 实例 → model_dump(mode='json') → ws.send_json
  - 接收侧（前端）：有对应的 ts 类型守卫
  - extra = "allow"：向前兼容，老客户端遇到未知字段不会崩

新增事件流程：
  1. 在下面某个分组（房间管理 / 在线打字 / DM 流程 / 战斗）加一个类
  2. 加到底部 WSEvent Union
  3. 在相应的广播调用点（rooms.py / game.py / ws.py / combat/*）构造该类
  4. 前端 types/ws.d.ts 也同步加一个 interface

为什么不放在 api/combat/schemas.py：那里专注于请求体；WS 事件是独立主题，
且会被多个模块共享（rooms / game / combat 都要广播），放 schemas/ 根目录更合理。
"""
from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class _BaseEvent(BaseModel):
    """所有 WS 事件的公共父类。"""
    model_config = ConfigDict(extra="allow")


# ─── 房间管理 ────────────────────────────────────────────────

class MemberJoined(_BaseEvent):
    type: Literal["member_joined"] = "member_joined"
    user_id: str
    members: list[dict]     # [{user_id, username, display_name, role, character_id, ...}]


class MemberLeft(_BaseEvent):
    type: Literal["member_left"] = "member_left"
    user_id: str
    host_transferred_to: Optional[str] = None
    members: list[dict]


class RoomDissolved(_BaseEvent):
    type: Literal["room_dissolved"] = "room_dissolved"
    by_user_id: str


class GameStarted(_BaseEvent):
    type: Literal["game_started"] = "game_started"
    current_speaker_user_id: Optional[str] = None


class AiCompanionsFilled(_BaseEvent):
    type: Literal["ai_companions_filled"] = "ai_companions_filled"
    generated: int
    ai_companions: list[dict]


class MemberKicked(_BaseEvent):
    type: Literal["member_kicked"] = "member_kicked"
    user_id: str
    by_user_id: str
    members: list[dict]


class HostTransferred(_BaseEvent):
    type: Literal["host_transferred"] = "host_transferred"
    new_host_user_id: str


class CharacterClaimed(_BaseEvent):
    type: Literal["character_claimed"] = "character_claimed"
    user_id: str
    character_id: str
    members: list[dict]


# ─── 在线 / 打字 ─────────────────────────────────────────────

class MemberOnline(_BaseEvent):
    type: Literal["member_online"] = "member_online"
    user_id: str
    members: list[dict] = []


class MemberOffline(_BaseEvent):
    type: Literal["member_offline"] = "member_offline"
    user_id: str
    members: list[dict] = []


class Typing(_BaseEvent):
    type: Literal["typing"] = "typing"
    user_id: str
    is_typing: bool


class WSError(_BaseEvent):
    type: Literal["error"] = "error"
    code: str
    message: str


# ─── DM 流程 ─────────────────────────────────────────────────

class DMThinkingStart(_BaseEvent):
    """其他玩家提交行动，调 LLM 前广播一次，让所有人看到"DM 思考中"动画。"""
    type: Literal["dm_thinking_start"] = "dm_thinking_start"
    by_user_id: str
    redacted: bool = False
    visibility: Optional[str] = None
    group_id: Optional[str] = None
    started_at: Optional[str] = None
    action_text: str        # 简短预览（<= 80 字符）


class DMResponded(_BaseEvent):
    """DM 出结果广播给房间所有人；非 actor 用来触发本地剧场模式。"""
    type: Literal["dm_responded"] = "dm_responded"
    by_user_id: str
    action_type: str
    narrative: str
    companion_reactions: str = ""
    dice_display: list = []
    combat_triggered: bool = False
    combat_ended: bool = False
    visibility: dict = Field(default_factory=dict)
    table_reason: str = ""
    table_decision: dict = Field(default_factory=dict)


class DMSpeakTurn(_BaseEvent):
    """
    探索阶段发言权转移通知。
    auto=True 表示 DM 回复后自动推进；False 表示玩家主动点"我说完了"触发。
    """
    type: Literal["dm_speak_turn"] = "dm_speak_turn"
    user_id: str
    auto: bool = False


class RoomStateUpdated(_BaseEvent):
    """房间协作状态快照更新。前端收到后可直接替换 room realtime state。"""
    type: Literal["room_state_updated"] = "room_state_updated"
    room: dict


# ─── 战斗 ────────────────────────────────────────────────────

class CombatUpdate(_BaseEvent):
    """_broadcast_combat 的默认事件，战斗状态有任何变化时广播。"""
    type: Literal["combat_update"] = "combat_update"
    combat: Optional[dict] = None              # serialize_combat() 的完整快照
    current_entity_id: Optional[str] = None    # 当前回合归属（前端判 owner 用）
    combat_over: Optional[bool] = None
    outcome: Optional[str] = None
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    narration: Optional[str] = None
    action: Optional[str] = None
    reaction_type: Optional[str] = None
    reaction_effect: Optional[dict[str, Any]] = None
    next_turn_index: Optional[int] = None
    round_number: Optional[int] = None
    target_id: Optional[str] = None
    target_name: Optional[str] = None
    target_new_hp: Optional[int] = None
    target_state: Optional[dict[str, Any]] = None
    condition: Optional[str] = None
    condition_action: Optional[str] = None
    condition_result: Optional[dict[str, Any]] = None
    inspect_result: Optional[dict[str, Any]] = None
    actor_state: Optional[dict[str, Any]] = None
    caster_state: Optional[dict[str, Any]] = None
    entity_positions: Optional[dict[str, Any]] = None
    player_targeted: bool = False
    attack_result: Optional[dict[str, Any]] = None
    damage: Optional[int] = None
    heal: Optional[int] = None
    total_damage: Optional[int] = None
    damage_roll: Optional[dict[str, Any]] = None
    damage_type: Optional[str] = None
    damage_before_resistance: Optional[int] = None
    damage_after_resistance: Optional[int] = None
    resistance_applied: Optional[bool] = None
    resistance_sources: list[str] = Field(default_factory=list)
    crit_extra: Optional[int] = None
    sneak_attack: Optional[bool] = None
    sneak_attack_damage: Optional[int] = None
    extra_damage_notes: list[str] = Field(default_factory=list)
    defender_interception: Optional[dict[str, Any]] = None
    weapon_resource: Optional[dict[str, Any]] = None
    weapon_resources: list[dict[str, Any]] = Field(default_factory=list)
    enemy_action: Optional[dict[str, Any]] = None
    enemy_actions: list[dict[str, Any]] = Field(default_factory=list)
    tactical_decision: Optional[dict[str, Any]] = None
    dice_result: Optional[dict[str, Any]] = None
    spell_result: Optional[dict[str, Any]] = None
    special_action: Optional[dict[str, Any]] = None
    ready_action: Optional[dict[str, Any]] = None
    save: Optional[dict[str, Any]] = None
    target_results: list[dict[str, Any]] = Field(default_factory=list)
    aoe_results: list[dict[str, Any]] = Field(default_factory=list)
    resurrection_results: list[dict[str, Any]] = Field(default_factory=list)
    concentration_effect_updates: list[dict[str, Any]] = Field(default_factory=list)
    concentration_started: Optional[bool] = None
    concentration_ended: Optional[bool] = None
    ready_action_failed: Optional[dict[str, Any]] = None
    remaining_slots: Optional[dict[str, Any]] = None
    dc_source: Optional[dict[str, Any]] = None
    concentration_check: Optional[dict[str, Any]] = None
    concentration_checks: list[dict[str, Any]] = Field(default_factory=list)
    wild_magic_surge: Optional[dict[str, Any]] = None
    wild_magic_check: Optional[dict[str, Any]] = None
    skirmisher_reposition: Optional[dict[str, Any]] = None
    confusion_turn: Optional[dict[str, Any]] = None
    player_can_react: bool = False
    reaction_prompt: Optional[dict[str, Any]] = None
    lair_action_prompt: Optional[dict[str, Any]] = None
    legendary_action_prompt: Optional[dict[str, Any]] = None
    lair_action: Optional[dict[str, Any]] = None
    legendary_action: Optional[dict[str, Any]] = None
    ready_action_results: list[dict[str, Any]] = Field(default_factory=list)
    opportunity_attacks: list[dict[str, Any]] = Field(default_factory=list)
    expired_ready_action: Optional[dict[str, Any]] = None
    ready_action_expired_log: Optional[str] = None
    confusion_end_save: Optional[dict[str, Any]] = None
    condition_end_saves: list[dict[str, Any]] = Field(default_factory=list)
    turn_start_hazard: Optional[dict[str, Any]] = None
    turn_start_hazard_log: Optional[str] = None


class TurnChanged(_BaseEvent):
    """end-turn 端点触发，轮到下一个实体。"""
    type: Literal["turn_changed"] = "turn_changed"
    combat: Optional[dict] = None
    current_entity_id: Optional[str] = None
    round_number: int
    next_turn_index: int
    lair_action_prompt: Optional[dict[str, Any]] = None
    legendary_action_prompt: Optional[dict[str, Any]] = None
    turn_order_delayed: bool = False
    delayed_turn: Optional[dict[str, Any]] = None


class EntityMoved(_BaseEvent):
    """move 端点触发，某个实体位置变化。"""
    type: Literal["entity_moved"] = "entity_moved"
    combat: Optional[dict] = None
    current_entity_id: Optional[str] = None
    entity_id: str
    position: dict             # {"x": int, "y": int}
    narration: Optional[str] = None
    movement: Optional[dict[str, Any]] = None
    dice_result: Optional[dict[str, Any]] = None
    special_action: Optional[dict[str, Any]] = None
    combat_over: Optional[bool] = None
    outcome: Optional[str] = None
    ready_action_results: list[dict[str, Any]] = Field(default_factory=list)
    opportunity_attacks: list[dict[str, Any]] = Field(default_factory=list)
    hazard_result: Optional[dict[str, Any]] = None


# ─── 判别联合类型（discriminator = "type"） ─────────────────────

WSEvent = Union[
    MemberJoined, MemberLeft, RoomDissolved, GameStarted,
    AiCompanionsFilled, MemberKicked, HostTransferred, CharacterClaimed,
    MemberOnline, MemberOffline, Typing, WSError,
    DMThinkingStart, DMResponded, DMSpeakTurn, RoomStateUpdated,
    CombatUpdate, TurnChanged, EntityMoved,
]

# 方便调用方：`WS_EVENT_TYPES` 是全部事件 type 字面量的集合
WS_EVENT_TYPES = frozenset({
    "member_joined", "member_left", "room_dissolved", "game_started",
    "ai_companions_filled", "member_kicked", "host_transferred", "character_claimed",
    "member_online", "member_offline", "typing", "error",
    "dm_thinking_start", "dm_responded", "dm_speak_turn", "room_state_updated",
    "combat_update", "turn_changed", "entity_moved",
})


__all__ = [
    "WSEvent", "WS_EVENT_TYPES",
    # 房间
    "MemberJoined", "MemberLeft", "RoomDissolved", "GameStarted",
    "AiCompanionsFilled", "MemberKicked", "HostTransferred", "CharacterClaimed",
    # 在线
    "MemberOnline", "MemberOffline", "Typing", "WSError",
    # DM
    "DMThinkingStart", "DMResponded", "DMSpeakTurn", "RoomStateUpdated",
    # 战斗
    "CombatUpdate", "TurnChanged", "EntityMoved",
]
