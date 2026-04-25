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

from pydantic import BaseModel, ConfigDict


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


class MemberOffline(_BaseEvent):
    type: Literal["member_offline"] = "member_offline"
    user_id: str


class Typing(_BaseEvent):
    type: Literal["typing"] = "typing"
    user_id: str
    is_typing: bool


# ─── DM 流程 ─────────────────────────────────────────────────

class DMThinkingStart(_BaseEvent):
    """其他玩家提交行动，调 LLM 前广播一次，让所有人看到"DM 思考中"动画。"""
    type: Literal["dm_thinking_start"] = "dm_thinking_start"
    by_user_id: str
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


class DMSpeakTurn(_BaseEvent):
    """
    探索阶段发言权转移通知。
    auto=True 表示 DM 回复后自动推进；False 表示玩家主动点"我说完了"触发。
    """
    type: Literal["dm_speak_turn"] = "dm_speak_turn"
    user_id: str
    auto: bool = False


# ─── 战斗 ────────────────────────────────────────────────────

class CombatUpdate(_BaseEvent):
    """_broadcast_combat 的默认事件，战斗状态有任何变化时广播。"""
    type: Literal["combat_update"] = "combat_update"
    combat: Optional[dict] = None              # serialize_combat() 的完整快照
    current_entity_id: Optional[str] = None    # 当前回合归属（前端判 owner 用）


class TurnChanged(_BaseEvent):
    """end-turn 端点触发，轮到下一个实体。"""
    type: Literal["turn_changed"] = "turn_changed"
    combat: Optional[dict] = None
    current_entity_id: Optional[str] = None
    round_number: int
    next_turn_index: int


class EntityMoved(_BaseEvent):
    """move 端点触发，某个实体位置变化。"""
    type: Literal["entity_moved"] = "entity_moved"
    combat: Optional[dict] = None
    current_entity_id: Optional[str] = None
    entity_id: str
    position: dict             # {"x": int, "y": int}


# ─── 判别联合类型（discriminator = "type"） ─────────────────────

WSEvent = Union[
    MemberJoined, MemberLeft, RoomDissolved, GameStarted,
    AiCompanionsFilled, MemberKicked, HostTransferred, CharacterClaimed,
    MemberOnline, MemberOffline, Typing,
    DMThinkingStart, DMResponded, DMSpeakTurn,
    CombatUpdate, TurnChanged, EntityMoved,
]

# 方便调用方：`WS_EVENT_TYPES` 是全部事件 type 字面量的集合
WS_EVENT_TYPES = frozenset({
    "member_joined", "member_left", "room_dissolved", "game_started",
    "ai_companions_filled", "member_kicked", "host_transferred", "character_claimed",
    "member_online", "member_offline", "typing",
    "dm_thinking_start", "dm_responded", "dm_speak_turn",
    "combat_update", "turn_changed", "entity_moved",
})


__all__ = [
    "WSEvent", "WS_EVENT_TYPES",
    # 房间
    "MemberJoined", "MemberLeft", "RoomDissolved", "GameStarted",
    "AiCompanionsFilled", "MemberKicked", "HostTransferred", "CharacterClaimed",
    # 在线
    "MemberOnline", "MemberOffline", "Typing",
    # DM
    "DMThinkingStart", "DMResponded", "DMSpeakTurn",
    # 战斗
    "CombatUpdate", "TurnChanged", "EntityMoved",
]
