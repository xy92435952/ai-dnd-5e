"""
api.combat._shared — 战斗模块的共享常量 / 单例 / 辅助函数。

这里定义的每样东西被多个端点模块调用。改动前请用 grep 确认影响范围。
"""
import asyncio

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models import Character, Session, CombatState
from api.deps import entity_snapshot, serialize_combat, broadcast_to_session
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
from services.enemy_inspect_service import build_enemy_inspect_snapshot
from services.character_roster import CharacterRoster

svc = CombatService()
_TURN_ADVANCE_LOCKS: dict[str, asyncio.Lock] = {}


def _combat_turn_token(combat: CombatState, current: dict | None = None) -> str:
    turn_index = combat.current_turn_index or 0
    if current is None:
        turn_order = combat.turn_order or []
        current = turn_order[turn_index] if 0 <= turn_index < len(turn_order) else {}
    actor_id = current.get("character_id") or current.get("id") or ""
    return f"{combat.round_number or 1}:{turn_index}:{actor_id}"


def _assert_expected_turn_token(
    combat: CombatState,
    expected_token: str | None,
    *,
    detail_prefix: str = "Combat action",
) -> None:
    if not expected_token:
        return
    current_token = _combat_turn_token(combat)
    if expected_token != current_token:
        raise HTTPException(409, f"{detail_prefix} token is stale; refresh combat state")


def _get_turn_advance_lock(session_id: str) -> asyncio.Lock:
    lock = _TURN_ADVANCE_LOCKS.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _TURN_ADVANCE_LOCKS[session_id] = lock
    return lock


def _release_turn_advance_lock(session_id: str) -> bool:
    lock = _TURN_ADVANCE_LOCKS.get(session_id)
    if lock is None or lock.locked():
        return False
    _TURN_ADVANCE_LOCKS.pop(session_id, None)
    return True


async def _build_combat_snapshot(
    db: AsyncSession,
    session: Session,
    combat: CombatState,
    *,
    viewer_character_id: str | None = None,
) -> dict:
    """Return the full combat payload consumed by HTTP and realtime clients."""
    state = session.game_state or {}
    enemies = state.get("enemies", []) or []
    entities: dict = {}
    seen_character_ids: set[str] = set()

    async def add_character(character_id: str | None = None, character: Character | None = None) -> None:
        if character is None and character_id:
            character = await db.get(Character, character_id)
        if not character:
            return
        cid = str(character.id)
        entities[cid] = entity_snapshot(character, is_enemy=False)
        seen_character_ids.add(cid)

    roster = CharacterRoster(db, session)
    for character in await roster.party():
        await add_character(character=character)

    for turn in combat.turn_order or []:
        if not isinstance(turn, dict) or turn.get("is_enemy"):
            continue
        character_id = turn.get("character_id") or turn.get("id")
        if character_id and str(character_id) not in seen_character_ids:
            await add_character(character_id=str(character_id))

    for enemy in enemies:
        enemy_id = enemy.get("id")
        if not enemy_id:
            continue
        derived = enemy.get("derived") or {}
        hp_max = derived.get("hp_max", enemy.get("hp_max", 10))
        ac = derived.get("ac", enemy.get("ac", 10))
        enemy_snapshot = {
            "id": str(enemy_id),
            "name": enemy.get("name", "Enemy"),
            "is_player": False,
            "is_enemy": True,
            "hp_current": enemy.get("hp_current", 0),
            "hp_max": hp_max,
            "ac": ac,
            "conditions": enemy.get("conditions", []),
            "condition_durations": enemy.get("condition_durations", {}),
            "derived": {**derived, "hp_max": hp_max, "ac": ac},
        }
        enemy_snapshot.update(build_enemy_inspect_snapshot(
            enemy,
            viewer_character_id=viewer_character_id,
        ))
        entities[str(enemy_id)] = enemy_snapshot

    return {
        **serialize_combat(combat),
        "entities": entities,
        "turn_states": combat.turn_states or {},
    }


# ── 多人联机：战斗状态广播辅助 ──────────────────────────
# 在 commit 后调用，向房间所有 WS 连接广播一次最新战斗状态。
# 单人模式静默跳过。

from pydantic import BaseModel as _PydBase   # 局部 import 避免顶部污染


async def _broadcast_combat(
    session: Session,
    combat: CombatState | None,
    event: _PydBase,
    db: AsyncSession | None = None,
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
            payload["combat"] = (
                await _build_combat_snapshot(db, session, combat)
                if db is not None
                else serialize_combat(combat)
            )
        if payload.get("current_entity_id") is None and combat.turn_order:
            try:
                cur = combat.turn_order[combat.current_turn_index or 0]
                payload["current_entity_id"] = cur.get("character_id") if isinstance(cur, dict) else None
            except (IndexError, AttributeError):
                pass

    await broadcast_to_session(session, payload)

