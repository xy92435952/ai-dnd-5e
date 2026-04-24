"""
api.combat.schemas — 战斗端点的 Pydantic 请求体 schemas。

所有 /game/combat/* 的 POST 请求体都定义在这里，避免散落。
"""
from typing import Optional
from pydantic import BaseModel


class MoveRequest(BaseModel):
    entity_id: str
    to_x: int
    to_y: int


class ConditionRequest(BaseModel):
    entity_id:   str              # character_id 或 enemy["id"]
    condition:   str              # e.g. "poisoned"
    is_enemy:    bool = False     # True → 在 game_state.enemies 中查找
    rounds:      Optional[int] = None  # 持续回合数；None = 永久（需手动移除）


class CombatActionRequest(BaseModel):
    action_text: str = "普通攻击"
    target_id:   Optional[str] = None
    is_ranged:   bool = False
    is_offhand:  bool = False   # 副手攻击（附赠行动，需先完成主手攻击）


class DeathSaveRequest(BaseModel):
    character_id: str
    d20_value: Optional[int] = None  # Frontend 3D dice result


class SmiteRequest(BaseModel):
    slot_level:       int = 1           # 使用的法术位等级
    target_is_undead: bool = False      # 目标是否为亡灵/邪魔
    damage_values:    Optional[list[int]] = None  # 前端骰子物理结果
    target_id:        Optional[str] = None        # 斩击目标（前端传入）


class ClassFeatureRequest(BaseModel):
    feature_name: str                   # "second_wind" | "action_surge" | "rage" | "cunning_action_dash" | ...
    target_id:    Optional[str] = None  # 部分能力需要目标


class ReactionRequest(BaseModel):
    reaction_type: str      # "shield" | "uncanny_dodge" | "hellish_rebuke" | "opportunity_attack"
    target_id: Optional[str] = None  # For hellish_rebuke / opportunity_attack


class GrappleShoveRequest(BaseModel):
    action_type: str        # "grapple" | "shove"
    target_id: str
    shove_type: str = "prone"  # "prone" | "push" (only for shove)


class AttackRollRequest(BaseModel):
    entity_id:   str
    target_id:   str
    action_type: str = "melee"       # "melee" | "ranged"
    is_offhand:  bool = False
    d20_value:   Optional[int] = None  # Frontend 3D dice result


class DamageRollRequest(BaseModel):
    pending_attack_id: str
    damage_values: Optional[list[int]] = None  # Frontend 3D dice results [3, 5, 2]


class SpellRequest(BaseModel):
    caster_id:   str
    spell_name:  str
    spell_level: int = 1
    target_id:   Optional[str]       = None   # 单目标（向后兼容）
    target_ids:  Optional[list[str]] = None   # AoE 多目标列表


class SpellRollRequest(BaseModel):
    caster_id:   str
    spell_name:  str
    spell_level: int = 1
    target_id:   Optional[str]       = None
    target_ids:  Optional[list[str]] = None


class SpellConfirmRequest(BaseModel):
    pending_spell_id: str
    damage_values: Optional[list[int]] = None  # Frontend 3D spell dice results


class ManeuverRequest(BaseModel):
    maneuver_name: str
    target_id: str

