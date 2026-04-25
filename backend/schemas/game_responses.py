"""
HTTP 响应体 Pydantic schemas — 游戏主循环相关端点的 response_model。

FastAPI 会把这些 schema 注入到 OpenAPI 文档，前端 `npm run types:api`
自动生成对应的 TypeScript 接口。

目标是**渐进式**覆盖：先给前端最常用的几个端点（存档列表 / 存档详情 /
player_action）定义 response_model，让这些端点的响应在 api.d.ts 里
从 `unknown` 升级为真实结构。剩余端点可以后续逐个补齐。

设计约定：
  - 所有响应 schema 放本文件（不要散到端点文件里）
  - 嵌套结构（character / log）单独定义，方便复用
  - `extra="allow"`：保持向前兼容——后端增加字段，旧前端不崩
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


# ─── 通用嵌套结构 ────────────────────────────────────────────

class CharacterBrief(BaseModel):
    """对应 api.deps.char_brief(Character) 的返回。"""
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    race: str
    char_class: str
    level: int
    hp_current: int
    hp_max: int
    ac: int
    is_player: bool
    spell_slots:      dict[str, Any] = {}
    proficient_skills: list[str]     = []
    proficient_saves:  list[str]     = []
    conditions:        list[str]     = []
    derived:           dict[str, Any] = {}
    concentration:     Optional[str] = None
    known_spells:      list[str]     = []
    cantrips:          list[str]     = []
    equipment:         dict[str, Any] = {}
    fighting_style:    Optional[str] = None


class GameLogEntry(BaseModel):
    """对应 api.deps.serialize_log(GameLog) 的返回。"""
    model_config = ConfigDict(extra="allow")

    id: str
    role: str
    content: str
    log_type: str
    dice_result: Optional[dict[str, Any]] = None
    created_at: Optional[str] = None


# ─── /game/sessions 存档列表 ─────────────────────────────────

class SessionListItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    save_name: Optional[str] = None
    module_name: str
    combat_active: bool
    updated_at: Optional[str] = None
    player_name:  Optional[str] = None
    player_class: Optional[str] = None
    player_level: Optional[int] = None
    player_race:  Optional[str] = None


# ─── /game/sessions/{id} 存档详情 ────────────────────────────

class SessionDetail(BaseModel):
    """Adventure.jsx loadSession 消费的主接口。"""
    model_config = ConfigDict(extra="allow")

    session_id: str
    save_name: Optional[str] = None
    module_id: Optional[str] = None
    module_name: Optional[str] = None
    current_scene: Optional[str] = None
    combat_active: bool = False
    game_state: dict[str, Any] = {}
    player: Optional[CharacterBrief] = None
    companions: list[CharacterBrief] = []
    logs: list[GameLogEntry] = []
    campaign_state: dict[str, Any] = {}
    # 多人联机字段（单人模式下可能不存在，故全部可选）
    is_multiplayer: bool = False
    room_code: Optional[str] = None


# ─── /game/action 玩家行动响应 ───────────────────────────────

class PlayerActionResponse(BaseModel):
    """
    对应 api.game.player_action 返回。字段来自 StateApplicator.apply
    产生的 ApplyResult，加上后端注入的 combat_update。
    """
    model_config = ConfigDict(extra="allow")

    # ApplyResult 映射的字段
    type: str                                # action_type
    narrative: str
    companion_reactions: str = ""
    dice_display: list[Any] = []
    player_choices: list[Any] = []
    needs_check: Optional[dict[str, Any]] = None
    combat_triggered: bool = False
    combat_ended: bool = False
    combat_end_result: Optional[dict[str, Any]] = None
    combat_update: Optional[dict[str, Any]] = None
    errors: list[Any] = []


__all__ = [
    "CharacterBrief", "GameLogEntry",
    "SessionListItem", "SessionDetail", "PlayerActionResponse",
]
