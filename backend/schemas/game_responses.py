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


# ─── /game/skill-check ─────────────────────────────────────

class SkillCheckResult(BaseModel):
    """对应 services.dnd_rules.roll_skill_check 的返回。"""
    model_config = ConfigDict(extra="allow")

    d20: int
    modifier: int
    total: int
    success: bool
    proficient: bool = False
    advantage:    bool = False
    disadvantage: bool = False


# ─── /game/sessions/{id}/rest ──────────────────────────────

class CharacterRestResult(BaseModel):
    """单个角色的休息结果。长休 / 短休字段是并集。"""
    model_config = ConfigDict(extra="allow")

    name: str
    hp_recovered: int
    hp_current: int
    slots_restored: dict[str, Any] = {}
    hit_dice_remaining: Optional[int] = None
    # 短休专属（长休不带）
    hit_die_roll:    Optional[int] = None
    con_mod:         Optional[int] = None
    no_hit_dice:     Optional[bool] = None
    class_resources: Optional[dict[str, Any]] = None


class RestResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    rest_type: str
    characters: list[CharacterRestResult] = []


# ─── /game/combat/{id} ─────────────────────────────────────

class EntitySnapshot(BaseModel):
    """战斗地图上的实体（玩家 / 队友 / 敌人共用）。"""
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    is_player: bool = False
    is_enemy:  bool = False
    hp_current: int
    hp_max: int
    ac: int
    conditions: list[str] = []
    derived: dict[str, Any] = {}


class CombatStateResponse(BaseModel):
    """对应 api.combat.info.get_combat_state 的返回。"""
    model_config = ConfigDict(extra="allow")

    session_id: str
    turn_order: list[Any] = []
    current_turn_index: int = 0
    round_number: int = 1
    entity_positions: dict[str, Any] = {}
    grid_data: dict[str, Any] = {}
    entities: dict[str, EntitySnapshot] = {}
    turn_states: dict[str, Any] = {}


# ─── /game/combat/{id}/skill-bar ───────────────────────────

class SkillBarItem(BaseModel):
    """技能栏单项。形状由 _build_skill_bar 决定，字段较多用 extra='allow'。"""
    model_config = ConfigDict(extra="allow")

    k: str             # atk / spell / shove / ...
    glyph: str = ""    # 显示符号
    cost: str  = ""    # "动作" / "附赠" / "反应" / "免费"
    available: bool = True


class SkillBarResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    entity_id: str
    char_class: str = ""
    level: int = 1
    bar: list[SkillBarItem] = []


# ─── /game/sessions POST ───────────────────────────────────

class CreateSessionResponse(BaseModel):
    """对应 api.game.create_session 返回。"""
    model_config = ConfigDict(extra="allow")

    session_id: str
    opening_scene: str


# ─── /characters/options ───────────────────────────────────

class CharacterOptionsResponse(BaseModel):
    """
    GET /characters/options 返回 —— 角色创建向导依赖的元数据。
    字段非常多（种族/职业/法术/装备/专长全表），用 extra=allow 兼容；
    这里只列前端必读的主键。
    """
    model_config = ConfigDict(extra="allow")

    races:       list[Any] = []
    classes:     list[Any] = []
    backgrounds: list[Any] = []
    alignments:  list[Any] = []
    all_skills:  list[Any] = []
    spellcaster_classes: list[Any] = []


# ─── 完整角色详情（GET /characters/{id} + POST /characters/create） ─

class CharacterDetail(BaseModel):
    """
    对应 api.characters._serialize_character 返回。和 CharacterBrief 的区别：
    Brief 只给 DM 上下文用（精简），Detail 给前端创角 / 角色面板（完整）。
    """
    model_config = ConfigDict(extra="allow")

    id: str
    is_player: bool
    name: str
    race: str
    char_class: str
    subclass: Optional[str] = None
    level: int
    background: Optional[str] = None
    alignment: Optional[str] = None
    ability_scores: dict[str, Any] = {}
    derived: dict[str, Any] = {}
    hp_current: int
    hp_max: int
    ac: int
    spell_slots: dict[str, Any] = {}
    spell_slots_max: dict[str, Any] = {}
    known_spells: list[str] = []
    prepared_spells: list[str] = []
    cantrips: list[str] = []
    concentration: Optional[str] = None
    caster_type: Optional[str] = None
    cantrips_count: int = 0
    proficient_skills: list[str] = []
    proficient_saves: list[str] = []
    equipment: dict[str, Any] = {}
    fighting_style: Optional[str] = None
    languages: list[str] = []
    tool_proficiencies: list[str] = []
    feats: list[Any] = []
    conditions: list[str] = []
    death_saves: Optional[dict[str, Any]] = None
    # AI 队友专属
    personality:        Optional[str] = None
    speech_style:       Optional[str] = None
    combat_preference:  Optional[str] = None
    backstory:          Optional[str] = None
    catchphrase:        Optional[str] = None
    multiclass_info:    Optional[dict[str, Any]] = None
    subclass_effects:   dict[str, Any] = {}
    condition_durations: dict[str, Any] = {}


class GeneratePartyResponse(BaseModel):
    """POST /characters/generate-party 返回。"""
    model_config = ConfigDict(extra="allow")

    companions: list[CharacterDetail] = []


# ─── 角色 PATCH / POST 端点（结构稳定的部分） ──────────────

class PreparedSpellsResult(BaseModel):
    """PATCH /characters/{id}/prepared-spells"""
    model_config = ConfigDict(extra="allow")
    prepared_spells: list[str]
    max_prepared: int


class GoldUpdateResult(BaseModel):
    """PATCH /characters/{id}/gold"""
    model_config = ConfigDict(extra="allow")
    gold: int
    change: int
    reason: Optional[str] = None


class ExhaustionUpdateResult(BaseModel):
    """PATCH /characters/{id}/exhaustion"""
    model_config = ConfigDict(extra="allow")
    exhaustion_level: int
    effects: list[str] = []
    is_dead: bool = False


class AmmoUpdateResult(BaseModel):
    """PATCH /characters/{id}/ammo"""
    model_config = ConfigDict(extra="allow")
    weapon: str
    ammo: int
    change: int


class LevelUpResult(BaseModel):
    """POST /characters/{id}/level-up"""
    model_config = ConfigDict(extra="allow")
    character: CharacterDetail
    level_up_details: dict[str, Any] = {}


__all__ = [
    "CharacterBrief", "GameLogEntry",
    "SessionListItem", "SessionDetail", "PlayerActionResponse",
    "SkillCheckResult", "CharacterRestResult", "RestResponse",
    "EntitySnapshot", "CombatStateResponse",
    "SkillBarItem", "SkillBarResponse",
    "CreateSessionResponse",
    "CharacterOptionsResponse", "CharacterDetail", "GeneratePartyResponse",
    "PreparedSpellsResult", "GoldUpdateResult", "ExhaustionUpdateResult",
    "AmmoUpdateResult", "LevelUpResult",
]
