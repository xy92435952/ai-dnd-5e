"""
api.combat._shared — 战斗模块的共享常量 / 单例 / 辅助函数。

这里定义的每样东西被多个端点模块调用。改动前请用 grep 确认影响范围。
"""
import asyncio

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Character, Session, CombatState, SessionMember
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
from services.combat_ai_control_service import (
    ai_combat_driver_user_id,
    user_can_drive_ai_combat,
)

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
        "turn_states": _project_turn_states_for_viewer(
            combat.turn_states or {},
            viewer_character_id=viewer_character_id,
        ),
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
        if payload.get("combat") is None and db is None:
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

    await _send_combat_payload(session, combat, payload, db)


async def _send_combat_payload(
    session: Session,
    combat: CombatState | None,
    payload: dict,
    db: AsyncSession | None,
) -> None:
    payload = _inject_current_entity_id(payload, combat)
    if combat is not None and db is not None:
        from services.ws_manager import ws_manager

        viewer_character_ids = await _viewer_character_ids_by_user(db, session)
        driver_user_id = (
            await _ai_combat_driver_user_id(db, session)
            if _payload_has_ai_control_prompt(payload)
            else None
        )
        viewer_user_ids = await ws_manager.online_users(session.id)
        if not viewer_user_ids:
            if payload.get("combat") is None:
                payload = {
                    **payload,
                    "combat": await _build_combat_snapshot(db, session, combat),
                }
            await broadcast_to_session(session, payload)
            return
        for viewer_user_id in viewer_user_ids:
            viewer_character_id = viewer_character_ids.get(str(viewer_user_id))
            viewer_payload = {
                **payload,
                "combat": await _build_combat_snapshot(
                    db,
                    session,
                    combat,
                    viewer_character_id=viewer_character_id,
                ),
            }
            viewer_payload = _project_combat_event_for_viewer(
                viewer_payload,
                viewer_character_id=viewer_character_id,
                viewer_can_drive_ai_combat=(
                    driver_user_id is not None
                    and str(driver_user_id) == str(viewer_user_id)
                ),
            )
            await ws_manager.send_to_user(session.id, viewer_user_id, viewer_payload)
        return
    await broadcast_to_session(session, payload)


def _project_turn_states_for_viewer(
    turn_states: dict,
    *,
    viewer_character_id: str | None,
) -> dict:
    private_keys = {
        "pending_attack",
        "pending_spell",
        "pending_smite",
        "pending_attack_reaction",
        "pending_spell_reaction",
        "resume_spell_reaction",
    }
    projected: dict = {}
    for entity_id, state in dict(turn_states or {}).items():
        if not isinstance(state, dict):
            projected[entity_id] = state
            continue
        if viewer_character_id is not None and str(entity_id) == str(viewer_character_id):
            projected[entity_id] = state
            continue
        public_state = {
            key: value
            for key, value in state.items()
            if key not in private_keys
        }
        for key in ("ready_action", "ready_action_expired", "ready_action_failed"):
            if key in public_state:
                public_state[key] = _redacted_ready_action_payload(public_state.get(key), key)
        if "ready_action_resolved" in public_state:
            public_state["ready_action_resolved"] = _redact_ready_action_result_payload(
                public_state.get("ready_action_resolved")
            )
        projected[entity_id] = public_state
    return projected


def _redacted_ready_action_payload(value, kind: str) -> dict:
    if not isinstance(value, dict):
        return {
            "type": kind,
            "redacted": True,
            "visibility": "other_character",
        }
    return {
        "type": value.get("type") or kind,
        "redacted": True,
        "visibility": "other_character",
        "actor_id": value.get("actor_id"),
        "actor_name": value.get("actor_name"),
    }


def _redact_ready_action_result_payload(value):
    private_keys = {
        "condition_text",
        "trigger",
        "trigger_match",
        "slot_already_consumed",
        "slot_key",
        "slots_remaining",
        "concentration_spell_name",
    }
    if isinstance(value, dict):
        clean = {}
        for key, child in value.items():
            if key in private_keys:
                continue
            if key in {"ready_action", "ready_action_expired", "ready_action_failed"} and isinstance(child, dict):
                clean[key] = _redacted_ready_action_payload(child, key)
                continue
            clean[key] = _redact_ready_action_result_payload(child)
        return clean
    if isinstance(value, list):
        return [_redact_ready_action_result_payload(item) for item in value]
    return value


def _inject_current_entity_id(payload: dict, combat: CombatState | None) -> dict:
    if combat is None or payload.get("current_entity_id") is not None or not combat.turn_order:
        return payload
    try:
        cur = combat.turn_order[combat.current_turn_index or 0]
        if isinstance(cur, dict):
            payload["current_entity_id"] = cur.get("character_id")
    except (IndexError, AttributeError):
        pass
    return payload


def _project_combat_event_for_viewer(
    payload: dict,
    *,
    viewer_character_id: str | None,
    viewer_can_drive_ai_combat: bool = True,
) -> dict:
    projected = payload
    prompt = payload.get("reaction_prompt")
    if prompt:
        reactor_character_id = prompt.get("reactor_character_id") if isinstance(prompt, dict) else None
        if reactor_character_id and not _viewer_matches_character(viewer_character_id, reactor_character_id):
            projected = dict(projected)
            projected["reaction_prompt"] = None
            projected["player_can_react"] = False

    actor_id = projected.get("actor_id")
    if projected.get("action") == "ready_action" and not _viewer_matches_character(viewer_character_id, actor_id):
        projected = dict(projected)
        actor_name = projected.get("actor_name") or "A combatant"
        projected["narration"] = f"{actor_name} readies an action."
        projected["ready_action"] = _redacted_ready_action_payload(
            projected.get("ready_action"),
            "ready_action",
        )
        ready_dice = projected.get("dice_result")
        if isinstance(ready_dice, dict) and ready_dice.get("type") == "ready_action_declared":
            projected["dice_result"] = {
                "type": "ready_action_declared",
                "ready_action": _redacted_ready_action_payload(
                    ready_dice.get("ready_action"),
                    "ready_action",
                ),
            }
            projected["special_action"] = projected["dice_result"]
        elif projected.get("special_action"):
            projected["special_action"] = None
        projected["remaining_slots"] = None
        projected["actor_state"] = None
        projected["caster_state"] = None
        projected["concentration_started"] = False
        projected["concentration_spell_name"] = None
        projected["concentration_effect_updates"] = []

    expired_ready_action = projected.get("expired_ready_action")
    if isinstance(expired_ready_action, dict):
        expired_actor_id = expired_ready_action.get("actor_id")
        if not _viewer_matches_character(viewer_character_id, expired_actor_id):
            projected = dict(projected)
            projected["expired_ready_action"] = _redacted_ready_action_payload(
                expired_ready_action,
                "ready_action_expired",
            )
            actor_name = expired_ready_action.get("actor_name") or "A combatant"
            if projected.get("ready_action_expired_log"):
                projected["ready_action_expired_log"] = f"{actor_name}'s readied action expires."

    ready_action_failed = projected.get("ready_action_failed")
    if isinstance(ready_action_failed, dict):
        failed_actor_id = ready_action_failed.get("actor_id") or projected.get("actor_id")
        if not _viewer_matches_character(viewer_character_id, failed_actor_id):
            projected = dict(projected)
            actor_name = ready_action_failed.get("actor_name") or projected.get("actor_name") or "A combatant"
            projected["narration"] = f"{actor_name} ends concentration."
            projected["ready_action_failed"] = _redacted_ready_action_payload(
                ready_action_failed,
                "ready_action_failed",
            )
            projected["concentration_spell_name"] = None
            projected["actor_state"] = _redact_ready_action_failed_from_state(projected.get("actor_state"))
            projected["caster_state"] = _redact_ready_action_failed_from_state(projected.get("caster_state"))
            ready_dice = projected.get("dice_result")
            if isinstance(ready_dice, dict):
                projected["dice_result"] = _redact_ready_action_failed_from_dice(ready_dice)
                projected["special_action"] = projected["dice_result"]
            elif projected.get("special_action"):
                projected["special_action"] = None

    target_state = projected.get("target_state")
    target_ready_action_failed = (
        target_state.get("ready_action_failed")
        if isinstance(target_state, dict)
        else None
    )
    if isinstance(target_ready_action_failed, dict):
        failed_actor_id = (
            target_ready_action_failed.get("actor_id")
            or projected.get("target_id")
            or projected.get("actor_id")
        )
        if not _viewer_matches_character(viewer_character_id, failed_actor_id):
            projected = dict(projected)
            projected["target_state"] = _redact_ready_action_failed_from_state(target_state)
            ready_dice = projected.get("dice_result")
            if isinstance(ready_dice, dict):
                projected["dice_result"] = _redact_ready_action_failed_from_dice(ready_dice)
                projected["special_action"] = projected["dice_result"]
            elif projected.get("special_action"):
                projected["special_action"] = None

    ready_action_results = projected.get("ready_action_results")
    if isinstance(ready_action_results, list):
        clean_results = []
        changed = False
        for result in ready_action_results:
            if not isinstance(result, dict):
                clean_results.append(result)
                continue
            result_actor_id = result.get("actor_id")
            if result_actor_id and not _viewer_matches_character(viewer_character_id, result_actor_id):
                clean_results.append(_redact_ready_action_result_payload(result))
                changed = True
            else:
                clean_results.append(result)
        if changed:
            projected = dict(projected)
            projected["ready_action_results"] = clean_results

    inspect_payload = projected.get("inspect_result")
    if (
        projected.get("action") == "enemy_inspect"
        and isinstance(inspect_payload, dict)
        and not _viewer_matches_character(viewer_character_id, inspect_payload.get("actor_id"))
    ):
        projected = dict(projected)
        redacted_inspect = _redact_enemy_inspect_payload(inspect_payload)
        projected["inspect_result"] = redacted_inspect
        dice = projected.get("dice_result")
        if isinstance(dice, dict) and dice.get("type") == "enemy_inspect":
            projected["dice_result"] = _redact_enemy_inspect_payload(dice)
        if isinstance(projected.get("special_action"), dict):
            projected["special_action"] = redacted_inspect

    if not viewer_can_drive_ai_combat and _payload_has_ai_control_prompt(projected):
        projected = dict(projected)
        projected["legendary_action_prompt"] = None
        projected["lair_action_prompt"] = None
    return projected


def _redact_enemy_inspect_payload(value: dict) -> dict:
    clean = {
        "type": "enemy_inspect",
        "redacted": True,
        "visibility": "other_character",
    }
    for key in (
        "actor_id",
        "actor_name",
        "target_id",
        "target_name",
        "skill",
        "dc",
        "success",
    ):
        if key in value:
            clean[key] = value.get(key)
    check = value.get("check")
    if isinstance(check, dict):
        clean["check"] = dict(check)
    return clean


def _redact_ready_action_failed_from_state(value):
    if not isinstance(value, dict):
        return value
    state = dict(value)
    if isinstance(state.get("ready_action_failed"), dict):
        state["ready_action_failed"] = _redacted_ready_action_payload(
            state["ready_action_failed"],
            "ready_action_failed",
        )
    return state


def _redact_ready_action_failed_from_dice(value):
    dice = dict(value)
    dice["concentration_spell_name"] = None
    if isinstance(dice.get("ready_action_failed"), dict):
        dice["ready_action_failed"] = _redacted_ready_action_payload(
            dice["ready_action_failed"],
            "ready_action_failed",
        )
    if isinstance(dice.get("actor_state"), dict):
        dice["actor_state"] = _redact_ready_action_failed_from_state(dice["actor_state"])
    if isinstance(dice.get("caster_state"), dict):
        dice["caster_state"] = _redact_ready_action_failed_from_state(dice["caster_state"])
    if isinstance(dice.get("target_state"), dict):
        dice["target_state"] = _redact_ready_action_failed_from_state(dice["target_state"])
    return dice


async def _project_ai_control_prompts_for_user(
    db: AsyncSession,
    session: Session,
    user_id: str | None,
    payload: dict,
) -> dict:
    """Hide monster/lair control prompts from non-driver HTTP responses."""
    if not _payload_has_ai_control_prompt(payload):
        return payload
    can_drive = await _user_can_drive_ai_combat(db, session, user_id)
    if can_drive:
        return payload
    projected = dict(payload)
    projected["legendary_action_prompt"] = None
    projected["lair_action_prompt"] = None
    return projected


async def _assert_ai_combat_driver(
    db: AsyncSession,
    session: Session,
    user_id: str,
) -> None:
    """Require the caller to be the multiplayer AI combat driver."""
    if await _user_can_drive_ai_combat(db, session, user_id):
        return
    raise HTTPException(403, "Only the AI combat driver can control monster or lair actions")


async def _user_can_drive_ai_combat(
    db: AsyncSession,
    session: Session,
    user_id: str | None,
) -> bool:
    return await user_can_drive_ai_combat(db, session, user_id)


async def _ai_combat_driver_user_id(
    db: AsyncSession,
    session: Session,
) -> str | None:
    """Mirror frontend getAiCombatTurnDriverUserId: online host, then first online/member."""
    return await ai_combat_driver_user_id(db, session)


def _payload_has_ai_control_prompt(payload: dict) -> bool:
    return (
        payload.get("legendary_action_prompt") is not None
        or payload.get("lair_action_prompt") is not None
    )


def _viewer_matches_character(viewer_character_id: str | None, character_id: str | None) -> bool:
    return (
        viewer_character_id is not None
        and character_id is not None
        and str(viewer_character_id) == str(character_id)
    )


async def _viewer_character_ids_by_user(
    db: AsyncSession,
    session: Session,
) -> dict[str, str | None]:
    if session.is_multiplayer:
        result = await db.execute(
            select(SessionMember.user_id, SessionMember.character_id)
            .where(SessionMember.session_id == session.id)
        )
        return {
            str(user_id): str(character_id) if character_id else None
            for user_id, character_id in result.all()
        }
    if session.user_id and session.player_character_id:
        return {str(session.user_id): str(session.player_character_id)}
    return {}

