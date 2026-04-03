"""
内部数据结构 Pydantic 模型
为 JSON 字段提供类型约束，消除运行时 KeyError 和拼写错误

使用方式：
    from schemas.game_schemas import EnemyState, GameState, CombatEntities

    # 解析 session.game_state
    gs = GameState.model_validate(session.game_state or {})

    # 序列化回 JSON 存储
    session.game_state = gs.model_dump()
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# ── 角色衍生属性 ──────────────────────────────────────────

class AbilityModifiers(BaseModel):
    # str/int 是 Python 内置名，用 alias 避免 Pydantic v2 字段名冲突
    model_config = ConfigDict(populate_by_name=True)

    str_: int = Field(default=0, alias="str")
    dex:  int = 0
    con:  int = 0
    int_: int = Field(default=0, alias="int")
    wis:  int = 0
    cha:  int = 0


class SavingThrows(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    str_: int = Field(default=0, alias="str")
    dex:  int = 0
    con:  int = 0
    int_: int = Field(default=0, alias="int")
    wis:  int = 0
    cha:  int = 0


class DerivedStats(BaseModel):
    hp_max:              int   = 1
    ac:                  int   = 10
    initiative:          int   = 0
    proficiency_bonus:   int   = 2
    attack_bonus:        int   = 2
    ranged_attack_bonus: int   = 2
    spell_save_dc:       int   = 0
    spell_attack_bonus:  int   = 0
    spell_ability:       Optional[str] = None
    caster_type:         Optional[str] = None   # "full"|"half"|"pact"|None
    cantrips_count:      int   = 0
    hit_die:             int   = 8
    ability_modifiers:   AbilityModifiers = Field(default_factory=AbilityModifiers)
    saving_throws:       SavingThrows     = Field(default_factory=SavingThrows)
    spell_slots_max:     dict[str, int]   = Field(default_factory=dict)

    class Config:
        extra = "allow"   # 允许未来添加字段而不报错


# ── 战斗中的敌人状态 ─────────────────────────────────────

class EnemyDerived(BaseModel):
    hp_max:            int = 10
    ac:                int = 10
    attack_bonus:      int = 2
    proficiency_bonus: int = 2
    ability_modifiers: AbilityModifiers = Field(default_factory=AbilityModifiers)
    hit_die:           int = 8

    class Config:
        extra = "allow"


class EnemyState(BaseModel):
    id:          str
    name:        str
    hp_current:  int = 10
    derived:     EnemyDerived = Field(default_factory=EnemyDerived)
    conditions:  list[str]    = Field(default_factory=list)
    position:    Optional[dict[str, int]] = None   # {"x":3,"y":5}

    class Config:
        extra = "allow"


# ── Session.game_state ───────────────────────────────────

class GameState(BaseModel):
    companion_ids: list[str]     = Field(default_factory=list)
    scene_index:   int           = 0
    flags:         dict          = Field(default_factory=dict)
    enemies:       list[EnemyState] = Field(default_factory=list)

    class Config:
        extra = "allow"


# ── CombatState 字段 ──────────────────────────────────────

class EntityPosition(BaseModel):
    x: int
    y: int


class TurnEntry(BaseModel):
    character_id: str
    name:         str
    initiative:   int
    is_player:    bool  = False
    is_enemy:     bool  = False

    class Config:
        extra = "allow"


class GridCell(BaseModel):
    """地形格子类型（future: 障碍/困难地形）"""
    type: str = "normal"   # "normal"|"wall"|"difficult"|"cover"


# ── 战斗实体快照（返回给前端）────────────────────────────

class CombatEntitySnapshot(BaseModel):
    """发送给前端的实体信息快照"""
    id:         str
    name:       str
    hp_current: int
    hp_max:     int
    ac:         int
    is_player:  bool = False
    is_enemy:   bool = False
    conditions: list[str] = Field(default_factory=list)

    class Config:
        extra = "allow"
