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
    expected_turn_token: Optional[str] = None


class ConditionRequest(BaseModel):
    entity_id:   str              # character_id 或 enemy["id"]
    condition:   str              # e.g. "poisoned"
    is_enemy:    bool = False     # True → 在 game_state.enemies 中查找
    rounds:      Optional[int] = None  # 持续回合数；None = 永久（需手动移除）


class CombatActionRequest(BaseModel):
    action_text: str = "普通攻击"
    target_id:   Optional[str] = None
    is_ranged:   bool = False
    expected_turn_token: Optional[str] = None
    is_offhand:  bool = False   # 副手攻击（附赠行动，需先完成主手攻击）


class DeathSaveRequest(BaseModel):
    character_id: str
    d20_value: Optional[int] = None  # Frontend 3D dice result


class RecoverThrownWeaponsRequest(BaseModel):
    character_id: str


class SmiteRequest(BaseModel):
    slot_level:       int = 1           # 使用的法术位等级
    target_is_undead: bool = False      # 目标是否为亡灵/邪魔
    damage_values:    Optional[list[int]] = None  # 前端骰子物理结果
    target_id:        Optional[str] = None        # 斩击目标（前端传入）
    is_crit: Optional[bool] = None  # Bound hit crit context


class ClassFeatureRequest(BaseModel):
    feature_name: str                   # "second_wind" | "action_surge" | "rage" | "cunning_action_dash" | ...
    target_id:    Optional[str] = None  # 部分能力需要目标


class ReactionRequest(BaseModel):
    reaction_type: str      # "shield" | "counterspell" | "decline" | "uncanny_dodge" | "hellish_rebuke" | "absorb_elements"
    target_id: Optional[str] = None  # For counterspell / hellish_rebuke
    character_id: Optional[str] = None  # Reacting character; important in multiplayer rooms


class ReadyActionRequest(BaseModel):
    entity_id: str
    action_type: str = "attack"
    trigger: str = "target_moves"
    target_id: Optional[str] = None
    is_ranged: bool = False
    spell_name: Optional[str] = None
    spell_level: int = 0
    move_to_x: Optional[int] = None
    move_to_y: Optional[int] = None
    condition_text: Optional[str] = None
    trigger_match: Optional[str] = None
    expected_turn_token: Optional[str] = None


class GrappleShoveRequest(BaseModel):
    action_type: str        # "grapple" | "shove"
    target_id: str
    shove_type: str = "prone"  # "prone" | "push" (only for shove)


class GrappleEscapeRequest(BaseModel):
    source_id: Optional[str] = None
    skill: Optional[str] = None  # "athletics" | "acrobatics" | None for best available


class AttackRollRequest(BaseModel):
    entity_id:   str
    target_id:   str
    action_type: str = "melee"       # "melee" | "ranged"
    is_offhand:  bool = False
    weapon_name: Optional[str] = None
    d20_value:   Optional[int] = None  # Frontend 3D dice result
    second_d20_value: Optional[int] = None  # Advantage/disadvantage second d20
    use_lucky: bool = False
    lucky_d20_value: Optional[int] = None
    use_bardic_inspiration: bool = False
    bardic_inspiration_roll: Optional[int] = None
    expected_turn_token: Optional[str] = None


class DamageRollRequest(BaseModel):
    pending_attack_id: str
    damage_values: Optional[list[int]] = None  # Frontend 3D dice results [3, 5, 2]


class SpellRequest(BaseModel):
    caster_id: str
    spell_name: str
    spell_level: int = 1
    target_id: Optional[str] = None
    target_ids: Optional[list[str]] = None
    aoe_center: Optional[str] = None
    expected_turn_token: Optional[str] = None


class SpellRollRequest(BaseModel):
    caster_id:   str
    spell_name:  str
    spell_level: int = 1
    target_id:   Optional[str]       = None
    target_ids:  Optional[list[str]] = None
    aoe_center:  Optional[str]       = None
    d20_value: Optional[int] = None  # Frontend 3D dice result for spell attacks
    second_d20_value: Optional[int] = None  # Advantage/disadvantage second d20 for spell attacks
    expected_turn_token: Optional[str] = None


class SpellConfirmRequest(BaseModel):
    pending_spell_id: str
    damage_values: Optional[list[int]] = None  # Frontend 3D spell dice results


class ManeuverRequest(BaseModel):
    maneuver_name: str
    target_id: str


class CombatInspectRequest(BaseModel):
    character_id: str
    target_id: str
    skill: str = "investigation"
    dc: Optional[int] = None
    d20_value: Optional[int] = None
    second_d20_value: Optional[int] = None
    expected_turn_token: Optional[str] = None
