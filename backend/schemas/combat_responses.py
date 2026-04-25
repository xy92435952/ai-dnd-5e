"""
战斗端点响应 schema —— 用 5 个通用类型覆盖 17+ 个端点。

为什么不每个端点单独建 schema：
  - 战斗端点返回的 dict 形状变化频繁（每加一个新规则就可能加字段）
  - 每个建一个 schema 维护成本高且 OpenAPI 文档臃肿
  - 用通用 schema + ConfigDict(extra='allow') 既能给前端"主字段"类型提示，
    又允许端点自由扩展不破坏前端

主字段建模 + extra=allow 是这里的设计哲学。
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class CombatActionResult(BaseModel):
    """
    11 个动作类端点共用：/action / /attack-roll / /damage-roll / /spell /
    /spell-roll / /spell-confirm / /smite / /grapple-shove / /class-feature /
    /maneuver / /reaction
    """
    model_config = ConfigDict(extra="allow")

    # 大部分动作端点都返回的核心字段
    success: bool = True
    action: Optional[str] = None              # 动作类型（attack/spell/maneuver/...）
    log_msg: Optional[str] = None             # 战斗日志展示文本
    dice_result: Optional[dict[str, Any]] = None
    # 攻击 / 法术常见
    hit: Optional[bool] = None
    damage: Optional[int] = None
    is_crit: Optional[bool] = None
    # 状态变化
    target_hp_current: Optional[int] = None
    attacker_hp_current: Optional[int] = None
    # 战斗结束信号
    combat_over: Optional[bool] = None
    outcome: Optional[str] = None             # "victory" | "defeat" | None


class EndTurnResult(BaseModel):
    """/end-turn / /ai-turn / /end 等回合推进类端点。"""
    model_config = ConfigDict(extra="allow")

    success: bool = True
    next_turn_index: Optional[int] = None
    round_number: Optional[int] = None
    current_entity_id: Optional[str] = None
    combat_over: Optional[bool] = None
    outcome: Optional[str] = None


class MoveResult(BaseModel):
    """/move —— 含借机攻击触发结果。"""
    model_config = ConfigDict(extra="allow")

    entity_id: str
    x: int
    y: int
    movement_used: Optional[int] = None
    movement_remaining: Optional[int] = None
    opportunity_attacks: list[dict[str, Any]] = []   # [{attacker, target, log, result}]


class ConditionUpdateResult(BaseModel):
    """
    /condition/add / /condition/remove —— 端点返回更新后**完整**的条件列表。
    前端据 `conditions` 整体覆盖 UI 状态，不做 diff。
    """
    model_config = ConfigDict(extra="allow")

    entity_id: str
    conditions: list[str] = []
    log_msg: Optional[str] = None


class DeathSaveResult(BaseModel):
    """/death-save。"""
    model_config = ConfigDict(extra="allow")

    success: bool = True                # HTTP 层成功（不是检定成功）
    d20: Optional[int] = None
    save_succeeded: Optional[bool] = None  # 这次检定是否 ≥ DC10
    successes: Optional[int] = None
    failures: Optional[int] = None
    stable: Optional[bool] = None
    revived: Optional[bool] = None      # 自然 20 直接复活
    dead: Optional[bool] = None         # 3 失败死亡
    hp_current: Optional[int] = None
    log_msg: Optional[str] = None


__all__ = [
    "CombatActionResult", "EndTurnResult", "MoveResult",
    "ConditionUpdateResult", "DeathSaveResult",
]
