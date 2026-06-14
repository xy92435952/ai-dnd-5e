"""
api.combat.turns — 明确结束回合

从原 combat.py (单体 5368 行) 按功能域拆出，逻辑未改动。
"""
import uuid
import random
from typing import Optional
from fastapi import APIRouter, Body, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from sqlalchemy.orm.attributes import flag_modified

from database import get_db
from models import Character, Session, GameLog, CombatState, Module
from api.deps import (
    get_session_or_404, entity_snapshot, serialize_combat,
    get_user_id, assert_can_act, assert_session_access, broadcast_to_session, current_turn_user_id,
)
from services.combat_service import CombatService
from services.spell_service import spell_service
from services.dnd_rules import roll_dice, _normalize_class, get_incapacitating_reasons
from services.combat_narrator import narrate_action, narrate_batch
from services.combat_outcome_service import check_and_cleanup_combat_outcome
from services.character_roster import CharacterRoster
from services.combat_hazard_service import (
    apply_turn_start_hazard,
    hazard_result_to_log_text,
)
from services.combat_confusion_service import (
    apply_confusion_turn_start,
    build_confusion_end_save_log,
    build_confusion_attack_log,
    build_confusion_turn_log,
    resolve_confusion_end_of_turn_save,
    resolve_confusion_random_melee_attack,
)
from services.combat_repeat_save_service import (
    build_condition_end_save_log,
    resolve_repeat_save_end_of_turn_saves,
)
from services.bardic_inspiration_service import BardicInspirationError
from services.combat_legendary_action_service import (
    build_lair_action_prompt,
    build_legendary_action_prompt,
    should_prompt_lair_action_for_turn_advance,
)
from services.combat_ready_action_service import (
    apply_ready_action_expiry_to_turn_state,
    build_ready_action_expiry,
    build_ready_action_expiry_log,
    clear_expired_ready_spell_concentration_hold,
)

from api.combat._shared import (
    _DEFAULT_TS, svc,
    _get_ts, _save_ts, _reset_ts,
    _broadcast_combat, _calc_entity_turn_limits,
    _assert_ai_combat_driver,
    _combat_turn_token, _get_turn_advance_lock,
    _project_ai_control_prompts_for_user,
    _chebyshev_dist, _check_attack_range, _ai_move_toward,
    _has_adjacent_enemy, _has_ally_adjacent_to,
    _do_concentration_check, _tick_conditions_char, _tick_conditions_enemy,
    _chebyshev, _resolve_opportunity_attacks,
)
from api.combat.schemas import (
    MoveRequest, ConditionRequest, CombatActionRequest, DeathSaveRequest,
    SmiteRequest, ClassFeatureRequest, ReactionRequest, GrappleShoveRequest,
    AttackRollRequest, DamageRollRequest, SpellRequest, SpellRollRequest,
    SpellConfirmRequest, ManeuverRequest,
)
from schemas.combat_responses import EndTurnResult

router = APIRouter(prefix="/game", tags=["combat"])


class EndTurnRequest(BaseModel):
    expected_turn_token: str | None = None
    use_bardic_inspiration: bool = False
    bardic_inspiration_roll: int | None = None


class DelayTurnRequest(BaseModel):
    expected_turn_token: str | None = None
    after_entity_id: str | None = None


@router.post("/combat/{session_id}/end-turn", response_model=EndTurnResult)
async def end_player_turn(
    session_id: str,
    req: EndTurnRequest = Body(default_factory=EndTurnRequest),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    玩家明确结束回合。
    - 对当前实体执行条件倒计时
    - 推进 current_turn_index
    - 重置下一实体的回合状态
    """
    session = await get_session_or_404(session_id, db)
    async with _get_turn_advance_lock(session_id):
        return await _end_player_turn_locked(session_id, req, db, user_id, session)


@router.post("/combat/{session_id}/delay-turn", response_model=EndTurnResult)
async def delay_player_turn(
    session_id: str,
    req: DelayTurnRequest = Body(default_factory=DelayTurnRequest),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    session = await get_session_or_404(session_id, db)
    async with _get_turn_advance_lock(session_id):
        return await _end_player_turn_locked(
            session_id,
            req,
            db,
            user_id,
            session,
            delay_current_turn=True,
        )


async def _end_player_turn_locked(
    session_id: str,
    req: EndTurnRequest | DelayTurnRequest,
    db: AsyncSession,
    user_id: str,
    session,
    *,
    delay_current_turn: bool = False,
):
    await db.refresh(session)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    combat_result = await db.execute(
        select(CombatState)
        .where(CombatState.session_id == session_id)
        .order_by(CombatState.created_at.desc())
    )
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    turn_order = combat.turn_order or []
    if not turn_order:
        raise HTTPException(400, "先攻顺序为空")

    turn_index = combat.current_turn_index or 0
    current    = turn_order[turn_index]
    expected_token = req.expected_turn_token
    current_token = _combat_turn_token(combat, current)
    if expected_token and expected_token != current_token:
        raise HTTPException(409, "End turn token is stale; refresh combat state")
    current_cid = current.get("character_id") if isinstance(current, dict) else None
    delay_after_entity_id = getattr(req, "after_entity_id", None) if delay_current_turn else None
    delay_after_target_index = None
    if delay_current_turn:
        delay_after_target_index = _validate_delay_after_target(
            turn_order,
            turn_index,
            delay_after_entity_id,
        )
        _assert_delay_turn_unspent(combat, current_cid)

    # 多人联机：必须由当前回合归属玩家本人结束（AI 托管角色由 ai-turn 推进）
    if current_cid:
        if current.get("is_player") is not True:
            await assert_session_access(session, user_id, db)
            await _assert_ai_combat_driver(db, session, user_id)
        else:
            await assert_can_act(
                session,
                user_id,
                current_cid,
                db,
                allow_incapacitated=True,
            )
        if delay_current_turn:
            await _assert_delay_actor_can_choose_delay(db, session, current)

    # ── 当前实体条件倒计时 ────────────────────────────────
    tick_logs = []
    confusion_end_save = None
    condition_end_saves = []
    if current.get("is_player"):
        player = await db.get(Character, current_cid)
        if player:
            confusion_end_save = resolve_confusion_end_of_turn_save(
                player,
                entity_id=str(current_cid),
                actor_name=player.name,
            )
            if confusion_end_save:
                tick_logs.append(GameLog(
                    session_id=session_id,
                    role="system",
                    content=build_confusion_end_save_log(player.name, confusion_end_save),
                    log_type="combat",
                    dice_result=confusion_end_save,
                ))
            use_bardic_end_save = bool(getattr(req, "use_bardic_inspiration", False))
            bardic_end_save_roll = getattr(req, "bardic_inspiration_roll", None)
            try:
                condition_end_saves = resolve_repeat_save_end_of_turn_saves(
                    player,
                    entity_id=str(current_cid),
                    actor_name=player.name,
                    combat=combat,
                    use_bardic_inspiration=use_bardic_end_save,
                    bardic_inspiration_roll=bardic_end_save_roll,
                )
            except BardicInspirationError as exc:
                raise HTTPException(exc.status_code, exc.detail) from exc
            if use_bardic_end_save and not _condition_end_save_spent_bardic(condition_end_saves):
                raise HTTPException(400, "No end-of-turn saving throw available for Bardic Inspiration.")
            for condition_end_save in condition_end_saves:
                tick_logs.append(GameLog(
                    session_id=session_id,
                    role="system",
                    content=build_condition_end_save_log(player.name, condition_end_save),
                    log_type="combat",
                    dice_result=condition_end_save,
                ))
            removed = _tick_conditions_char(player)
            for c in removed:
                tick_logs.append(GameLog(
                    session_id=session_id, role="system",
                    content=f"[{player.name}] 的【{c}】状态到期解除",
                    log_type="system",
                ))

    # ── 推进回合 ──────────────────────────────────────────
    delayed_turn = None
    lair_turn_order = list(turn_order)
    lair_current_index = turn_index
    lair_next_index = None
    if delay_current_turn:
        delayed_turn = _delay_current_turn_to_round_end(
            combat,
            turn_order,
            turn_index,
            after_entity_id=delay_after_entity_id,
            after_target_index=delay_after_target_index,
        )
        turn_order = combat.turn_order or turn_order

    if delayed_turn and delayed_turn.get("moved"):
        next_index = int(delayed_turn["next_turn_index"])
        round_started = False
        next_lair_entity_id = _entry_entity_id(turn_order[next_index]) if turn_order else None
        if next_lair_entity_id:
            lair_next_index = _find_turn_entry_index(lair_turn_order, next_lair_entity_id)
    else:
        next_index = (combat.current_turn_index + 1) % max(len(turn_order), 1)
        round_started = next_index == 0
    if lair_next_index is None:
        lair_next_index = next_index
    combat.current_turn_index = next_index
    if round_started:
        combat.round_number += 1

    # ── 重置下一实体的回合状态（根据角色实际数据）────────
    next_entity_id = None
    expired_ready_action = None
    confusion_turn_result = None
    if turn_order:
        next_turn = turn_order[next_index]
        next_entity_id = next_turn["character_id"]
        expired_ready_action = build_ready_action_expiry(combat, str(next_entity_id))
        next_atk_max, next_move_max = await _calc_entity_turn_limits(db, session, next_entity_id)
        _reset_ts(combat, next_entity_id, attacks_max=next_atk_max, movement_max=next_move_max)
        confusion_actor = await _confusion_actor_for_turn(db, session, next_turn, str(next_entity_id))
        confusion_turn_result = apply_confusion_turn_start(
            combat,
            str(next_entity_id),
            confusion_actor,
        )

    turn_start_logs = []
    turn_start_hazard = None
    turn_start_hazard_log = ""
    ready_action_expired_log = ""
    if next_entity_id:
        if confusion_turn_result:
            actor_name = turn_order[next_index].get("name") if isinstance(turn_order[next_index], dict) else str(next_entity_id)
            turn_start_logs.append(GameLog(
                session_id=session_id,
                role="system",
                content=build_confusion_turn_log(actor_name or str(next_entity_id), confusion_turn_result),
                log_type="combat",
                dice_result={"confusion": confusion_turn_result},
            ))
            state_for_confusion = session.game_state or {}
            enemies_for_confusion = list(state_for_confusion.get("enemies", []) or [])
            confusion_attack = await resolve_confusion_random_melee_attack(
                db,
                session=session,
                combat=combat,
                entity_id=str(next_entity_id),
                actor=confusion_actor,
                enemies=enemies_for_confusion,
                confusion_turn=confusion_turn_result,
            )
            if confusion_attack:
                turn_start_logs.append(GameLog(
                    session_id=session_id,
                    role="system",
                    content=build_confusion_attack_log(actor_name or str(next_entity_id), confusion_attack),
                    log_type="combat",
                    dice_result={"confusion_attack": confusion_attack},
                ))
        turn_start_hazard = await apply_turn_start_hazard(
            db=db,
            session=session,
            combat_state=combat,
            entity_id=str(next_entity_id),
            combat_service=svc,
        )
        turn_start_hazard_log = hazard_result_to_log_text(turn_start_hazard)
        if turn_start_hazard_log:
            turn_start_logs.append(GameLog(
                session_id=session_id,
                role="system",
                content=turn_start_hazard_log,
                log_type="combat",
                dice_result={"hazard": turn_start_hazard},
            ))
        if expired_ready_action:
            await clear_expired_ready_spell_concentration_hold(db, str(next_entity_id), expired_ready_action)
            apply_ready_action_expiry_to_turn_state(combat, str(next_entity_id), expired_ready_action)
            ready_log = build_ready_action_expiry_log(session_id, expired_ready_action)
            ready_action_expired_log = ready_log.content
            turn_start_logs.append(ready_log)

    # ── 检查战斗结束 ──────────────────────────────────────
    state   = session.game_state or {}
    enemies = list(state.get("enemies", []))
    combat_over, outcome = await check_and_cleanup_combat_outcome(
        db,
        session=session,
        session_id=session_id,
        enemies=enemies,
        check_combat_over=svc.check_combat_over,
    )

    lair_action_prompt = None
    legendary_action_prompt = None
    if not combat_over:
        roster = CharacterRoster(db, session)
        legendary_target_candidates = [
            entity_snapshot(character, is_enemy=False)
            for character in await roster.party()
            if character and int(character.hp_current or 0) > 0
        ]
        lair_timing_reached = should_prompt_lair_action_for_turn_advance(
            lair_turn_order,
            current_index=lair_current_index,
            next_index=lair_next_index,
            round_started=round_started,
        )
        if (
            lair_timing_reached
            and int(state.get("lair_action_prompted_round", 0) or 0) != int(combat.round_number or 0)
            and int(state.get("lair_action_used_round", 0) or 0) != int(combat.round_number or 0)
        ):
            lair_action_prompt = build_lair_action_prompt(
                state,
                enemies,
                round_number=int(combat.round_number or 1),
                timing="initiative_count_20",
                trigger_entity_id=current_cid,
                trigger_entity_name=current.get("name"),
                positions=dict(combat.entity_positions or {}),
                target_candidates=legendary_target_candidates,
            )
            if lair_action_prompt:
                state["lair_action_prompted_round"] = int(combat.round_number or 1)

        if not lair_action_prompt:
            legendary_action_prompt = build_legendary_action_prompt(
                enemies,
                trigger_entity_id=current_cid,
                trigger_entity_name=current.get("name"),
                positions=dict(combat.entity_positions or {}),
                target_candidates=legendary_target_candidates,
            )

        if lair_action_prompt or legendary_action_prompt:
            state["enemies"] = enemies
            session.game_state = dict(state)
            flag_modified(session, "game_state")

    for tl in [*tick_logs, *turn_start_logs]:
        db.add(tl)
    await db.commit()
    # 多人联机：广播回合切换 + 最新战斗状态
    from schemas.ws_events import TurnChanged
    turn_changed_payload = {
        "round_number": combat.round_number,
        "next_turn_index": next_index,
        "lair_action_prompt": lair_action_prompt,
        "legendary_action_prompt": legendary_action_prompt,
    }
    if delayed_turn:
        turn_changed_payload["turn_order_delayed"] = bool(delayed_turn.get("moved"))
        turn_changed_payload["delayed_turn"] = delayed_turn
    await _broadcast_combat(session, combat, TurnChanged(**turn_changed_payload), db=db)

    response_payload = {
        "next_turn_index":    next_index,
        "round_number":       combat.round_number,
        "expired_conditions": [tl.content for tl in tick_logs if getattr(tl, "log_type", "") == "system"],
        "turn_start_hazard":  turn_start_hazard,
        "turn_start_hazard_log": turn_start_hazard_log,
        "expired_ready_action": expired_ready_action,
        "ready_action_expired_log": ready_action_expired_log,
        "confusion_end_save": confusion_end_save,
        "condition_end_saves": condition_end_saves,
        "confusion_turn":      confusion_turn_result,
        "lair_action_prompt": lair_action_prompt,
        "legendary_action_prompt": legendary_action_prompt,
        "combat_over":        combat_over,
        "outcome":            outcome,
    }
    if delayed_turn:
        response_payload["turn_order_delayed"] = bool(delayed_turn.get("moved"))
        response_payload["delayed_turn"] = delayed_turn
    return await _project_ai_control_prompts_for_user(db, session, user_id, response_payload)


def _condition_end_save_spent_bardic(condition_end_saves: list[dict]) -> bool:
    return any(
        bool(((result.get("save") or {}).get("bardic_inspiration") or {}).get("spent"))
        for result in condition_end_saves
    )


def _entry_entity_id(entry: dict | None) -> str | None:
    if not isinstance(entry, dict):
        return None
    entity_id = entry.get("character_id") or entry.get("id")
    return str(entity_id) if entity_id is not None else None


def _normalized_delay_after_entity_id(after_entity_id: str | None) -> str | None:
    if after_entity_id is None:
        return None
    normalized = str(after_entity_id).strip()
    return normalized or None


def _find_turn_entry_index(turn_order: list, entity_id: str) -> int | None:
    for index, entry in enumerate(turn_order):
        if _entry_entity_id(entry) == entity_id:
            return index
    return None


def _turn_state_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _assert_delay_turn_unspent(combat: CombatState, actor_id: str | None) -> None:
    if not actor_id:
        return
    turn_state = _get_ts(combat, str(actor_id))
    spent = []
    action_used = bool(turn_state.get("action_used"))
    if action_used:
        spent.append("action")
    if turn_state.get("bonus_action_used"):
        spent.append("bonus action")
    if _turn_state_int(turn_state.get("movement_used")) > 0:
        spent.append("movement")
    if not action_used and _turn_state_int(turn_state.get("attacks_made")) > 0:
        spent.append("attack")
    if spent:
        raise HTTPException(
            400,
            "Cannot delay after spending this turn's action economy: " + ", ".join(spent),
        )


async def _assert_delay_actor_can_choose_delay(db: AsyncSession, session: Session, turn_entry: dict | None) -> None:
    if not isinstance(turn_entry, dict):
        return
    actor_id = _entry_entity_id(turn_entry)
    if not actor_id:
        return
    if turn_entry.get("is_enemy"):
        state = session.game_state or {}
        actor_state = next(
            (enemy for enemy in state.get("enemies", []) or [] if str(enemy.get("id")) == str(actor_id)),
            None,
        )
    else:
        actor_state = await db.get(Character, actor_id)
    reasons = get_incapacitating_reasons(actor_state)
    if reasons:
        raise HTTPException(
            400,
            "Cannot delay while incapacitated: " + ", ".join(reasons),
        )


def _validate_delay_after_target(
    turn_order: list,
    current_index: int,
    after_entity_id: str | None,
) -> int | None:
    normalized = _normalized_delay_after_entity_id(after_entity_id)
    if not normalized:
        return None
    if len(turn_order) <= 1:
        raise HTTPException(400, "Cannot delay after another combatant in a one-actor turn order")
    target_index = _find_turn_entry_index(turn_order, normalized)
    if target_index is None:
        raise HTTPException(400, "Delay target is not in current turn order")
    if target_index == current_index:
        raise HTTPException(400, "Cannot delay after the current actor")
    if target_index < current_index:
        raise HTTPException(400, "Delay target has already acted this round")
    return target_index


def _delay_current_turn_to_round_end(
    combat: CombatState,
    turn_order: list,
    current_index: int,
    *,
    after_entity_id: str | None = None,
    after_target_index: int | None = None,
) -> dict:
    current_turn = turn_order[current_index]
    actor_id = _entry_entity_id(current_turn)
    normalized_after_entity_id = _normalized_delay_after_entity_id(after_entity_id)
    if normalized_after_entity_id and after_target_index is None:
        after_target_index = _validate_delay_after_target(
            turn_order,
            current_index,
            normalized_after_entity_id,
        )
    after_target = turn_order[after_target_index] if after_target_index is not None else None
    payload = {
        "actor_id": actor_id,
        "actor_name": current_turn.get("name"),
        "after_entity_id": normalized_after_entity_id,
        "after_entity_name": after_target.get("name") if isinstance(after_target, dict) else None,
        "from_index": current_index,
        "to_index": current_index,
        "next_turn_index": (current_index + 1) % max(len(turn_order), 1),
        "moved": False,
        "placement": "after_target" if normalized_after_entity_id else "round_end",
        "reason": (
            "already_at_round_end"
            if len(turn_order) <= 1 or current_index >= len(turn_order) - 1
            else "delayed_to_round_end"
        ),
    }
    if len(turn_order) <= 1 or current_index >= len(turn_order) - 1:
        return payload

    reordered = list(turn_order)
    delayed = reordered.pop(current_index)
    if after_target_index is not None:
        insert_index = after_target_index
        reordered.insert(insert_index, delayed)
        payload["reason"] = "delayed_after_target"
    else:
        reordered.append(delayed)
        insert_index = len(reordered) - 1
    combat.turn_order = reordered
    flag_modified(combat, "turn_order")

    payload["to_index"] = insert_index
    payload["next_turn_index"] = current_index
    payload["moved"] = True
    return payload


async def _confusion_actor_for_turn(db, session, turn: dict | None, entity_id: str):
    if isinstance(turn, dict) and turn.get("is_enemy"):
        state = session.game_state or {}
        return next(
            (enemy for enemy in state.get("enemies", []) or [] if str(enemy.get("id")) == str(entity_id)),
            None,
        )
    return await db.get(Character, entity_id)


# ── 反应 (Reaction System, P0-6) ─────────────────────────
