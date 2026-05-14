"""
api.combat._shared — 战斗模块的共享常量 / 单例 / 辅助函数。

这里定义的每样东西被多个端点模块调用。改动前请用 grep 确认影响范围。
"""
from models import Session, CombatState
from api.deps import serialize_combat, broadcast_to_session
from services.combat_service import CombatService
from services.combat_concentration_service import do_concentration_check as _do_concentration_check
from services.combat_condition_duration_service import (
    tick_character_conditions as _tick_conditions_char,
    tick_enemy_conditions as _tick_conditions_enemy,
)
from services.combat_grid_service import (
    ai_move_toward as _ai_move_toward,
    check_attack_range as _check_attack_range,
    chebyshev_distance as _chebyshev,
    chebyshev_distance as _chebyshev_dist,
    has_adjacent_enemy as _has_adjacent_enemy,
    has_ally_adjacent_to as _has_ally_adjacent_to,
)
from services.combat_opportunity_attack_service import (
    resolve_opportunity_attacks as _resolve_opportunity_attacks,
)
from services.combat_turn_state_service import (
    DEFAULT_TURN_STATE as _DEFAULT_TS,
    get_turn_state as _get_ts,
    reset_turn_state as _reset_ts,
    save_turn_state as _save_ts,
)
from services.combat_turn_limits_service import (
    calculate_entity_turn_limits as _calc_entity_turn_limits,
)

svc = CombatService()


# ── 多人联机：战斗状态广播辅助 ──────────────────────────
# 在 commit 后调用，向房间所有 WS 连接广播一次最新战斗状态。
# 单人模式静默跳过。

from pydantic import BaseModel as _PydBase   # 局部 import 避免顶部污染


async def _broadcast_combat(
    session: Session,
    combat: CombatState | None,
    event: _PydBase,
) -> None:
    """
    广播一个战斗相关 WS 事件。调用方构造 Pydantic 实例
    （`schemas.ws_events.CombatUpdate / TurnChanged / EntityMoved` 等），
    `combat` 和 `current_entity_id` 字段如果未填，由本函数自动注入。

    单人模式静默跳过。
    """
    if not session.is_multiplayer:
        return

    payload = event.model_dump(mode="json")

    # 自动注入通用字段
    if combat is not None:
        if payload.get("combat") is None:
            payload["combat"] = serialize_combat(combat)
        if payload.get("current_entity_id") is None and combat.turn_order:
            try:
                cur = combat.turn_order[combat.current_turn_index or 0]
                payload["current_entity_id"] = cur.get("character_id") if isinstance(cur, dict) else None
            except (IndexError, AttributeError):
                pass

    await broadcast_to_session(session, payload)

