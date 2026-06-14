"""
api.combat.movement — 网格移动 + 借机攻击触发

从原 combat.py (单体 5368 行) 按功能域拆出，逻辑未改动。
"""
import uuid
import random
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from sqlalchemy.orm.attributes import flag_modified

from database import get_db
from models import Character, Session, GameLog, CombatState, Module
from api.deps import (
    get_session_or_404, entity_snapshot, serialize_combat,
    get_user_id, assert_can_act, broadcast_to_session, current_turn_user_id,
)
from services.combat_service import CombatService
from services.spell_service import spell_service
from services.dnd_rules import roll_dice, _normalize_class
from services.combat_narrator import narrate_action, narrate_batch
from services.character_roster import CharacterRoster
from services.combat_hazard_service import (
    apply_movement_hazard,
    hazard_result_to_log_text,
)
from services.combat_movement_rules_service import (
    MovementRuleError,
    apply_stand_up_from_prone,
    validate_displacement_allowed,
    validate_frightened_movement,
)
from services.combat_movement_cost_service import build_movement_cost_breakdown
from services.combat_grapple_drag_service import (
    apply_grapple_drag_positions,
    build_grapple_drag_result,
)
from services.combat_ready_action_service import (
    matching_ready_action_actor_ids_for_movement,
    resolve_ready_actions_for_movement,
)

from api.combat._shared import (
    _assert_expected_turn_token,
    _DEFAULT_TS, svc,
    _get_ts, _save_ts, _reset_ts,
    _broadcast_combat, _calc_entity_turn_limits,
    _chebyshev_dist, _check_attack_range, _ai_move_toward,
    _has_adjacent_enemy, _has_ally_adjacent_to,
    _do_concentration_check, _tick_conditions_char, _tick_conditions_enemy,
    _chebyshev, _resolve_opportunity_attacks,
    _build_combat_snapshot,
)
from api.combat.schemas import (
    MoveRequest, ConditionRequest, CombatActionRequest, DeathSaveRequest,
    SmiteRequest, ClassFeatureRequest, ReactionRequest, GrappleShoveRequest,
    AttackRollRequest, DamageRollRequest, SpellRequest, SpellRollRequest,
    SpellConfirmRequest, ManeuverRequest,
)
from schemas.combat_responses import MoveResult

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/move", response_model=MoveResult)
async def combat_move(
    session_id: str, req: MoveRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """在战斗格子上移动实体（每回合最多 6 格 = 30ft）"""
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")
    await assert_can_act(session, user_id, req.entity_id, db)

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    _assert_expected_turn_token(combat, req.expected_turn_token, detail_prefix="Move")

    if not (0 <= req.to_x < 20 and 0 <= req.to_y < 12):
        raise HTTPException(400, "目标格子超出地图范围（20×12）")

    positions = dict(combat.entity_positions or {})
    for eid, pos in positions.items():
        if eid != req.entity_id and pos.get("x") == req.to_x and pos.get("y") == req.to_y:
            raise HTTPException(400, "目标格子已有其他实体")

    # ── 使用回合状态追踪移动力 ────────────────────────────
    ts  = _get_ts(combat, req.entity_id)
    stand_result = await _apply_stand_up_for_moving_entity(db, session, req.entity_id, ts)
    ts = stand_result.turn_state
    cur = positions.get(str(req.entity_id))
    opp_results = []
    movement_stop = None
    moved_distance = 0
    movement_cost = 0
    movement_cost_breakdown = None
    grapple_drag = None
    ready_action_results = []
    destination = {"x": req.to_x, "y": req.to_y}
    entity_name = await _get_entity_name(db, session, req.entity_id)
    condition_durations = await _get_moving_condition_durations(db, session, req.entity_id)
    if cur:
        # Chebyshev 距离（对角移动和直线移动同等消耗，符合 5e 标准规则）
        dist      = max(abs(cur["x"] - req.to_x), abs(cur["y"] - req.to_y))
        try:
            validate_displacement_allowed(stand_result.conditions, dist, condition_durations)
        except MovementRuleError as exc:
            raise HTTPException(400, "Cannot move while speed is 0") from exc
        try:
            validate_frightened_movement(
                stand_result.conditions,
                condition_durations,
                cur,
                destination,
                positions,
            )
        except MovementRuleError as exc:
            raise HTTPException(400, _movement_rule_error_detail(exc)) from exc
        grapple_drag = build_grapple_drag_result(
            actor_id=str(req.entity_id),
            actor_from=cur,
            actor_to=destination,
            positions=positions,
            targets=await _get_grapple_drag_candidates(db, session, req.entity_id),
            grid_data=dict(combat.grid_data or {}),
        )
        if grapple_drag and not grapple_drag.get("applied"):
            raise HTTPException(400, _grapple_drag_error_detail(grapple_drag))
        base_movement_cost = int(grapple_drag.get("movement_cost", dist) if grapple_drag else dist)
        movement_cost_breakdown = build_movement_cost_breakdown(
            dict(combat.grid_data or {}),
            cur,
            destination,
            base_cost=base_movement_cost,
            ignore_difficult_terrain=bool(ts.get("mobile_ignores_difficult_terrain")),
        )
        movement_cost = int(movement_cost_breakdown.get("movement_cost", base_movement_cost) or base_movement_cost)
        remaining = ts["movement_max"] - ts["movement_used"]
        if movement_cost > remaining:
            raise HTTPException(400, f"移动消耗 {movement_cost} 格超出剩余移动力（剩余 {remaining} 格）")

        # ── 借机攻击检查（移动前，使用旧位置计算相邻性）────
        # 脱离接战的实体不触发借机攻击
        ready_reaction_actor_ids = matching_ready_action_actor_ids_for_movement(
            combat,
            moving_id=str(req.entity_id),
            old_pos=cur,
            new_pos=destination,
        )
        if dist > 0 and not ts.get("disengaged"):
            opp_results = await _resolve_opportunity_attacks(
                db       = db,
                session  = session,
                combat   = combat,
                moving_id = str(req.entity_id),
                old_pos  = cur,
                new_pos  = {"x": req.to_x, "y": req.to_y},
                positions = apply_grapple_drag_positions(
                    {**positions, str(req.entity_id): destination},
                    grapple_drag,
                ) if grapple_drag else positions,
                excluded_actor_ids=ready_reaction_actor_ids,
            )
        for opp in opp_results:
            if opp.get("log"):
                db.add(opp["log"])

        movement_stop = next(
            (
                (opp.get("result") or {}).get("movement_stop")
                for opp in opp_results
                if (opp.get("result") or {}).get("movement_stop")
            ),
            None,
        )
        if movement_stop:
            destination = dict(movement_stop.get("to") or cur)
            grapple_drag = None
            ts["movement_used"] = max(
                int(ts.get("movement_used", 0) or 0),
                int(ts.get("movement_max", 0) or 0),
            )
            moved_distance = 0
        else:
            ts["movement_used"] += movement_cost
            moved_distance = dist
        _save_ts(combat, req.entity_id, ts)
    elif stand_result.stood_up:
        _save_ts(combat, req.entity_id, ts)

    positions = apply_grapple_drag_positions(positions, grapple_drag)
    positions[str(req.entity_id)] = destination
    combat.entity_positions        = positions

    if moved_distance > 0 and cur:
        ready_action_results = await resolve_ready_actions_for_movement(
            db=db,
            session=session,
            combat=combat,
            moving_id=str(req.entity_id),
            old_pos=cur,
            new_pos=destination,
            combat_service=svc,
            has_ally_adjacent_to=_has_ally_adjacent_to,
            resolve_opportunity_attacks=_resolve_opportunity_attacks,
        )
        if ready_action_results:
            positions = dict(combat.entity_positions or positions)

    hazard_result = None
    if moved_distance > 0:
        hazard_result = await apply_movement_hazard(
            db=db,
            session=session,
            combat_state=combat,
            entity_id=str(req.entity_id),
            position=positions[str(req.entity_id)],
            combat_service=svc,
        )
        hazard_log = hazard_result_to_log_text(hazard_result)
        if hazard_log:
            db.add(GameLog(
                session_id=session_id,
                role="system",
                content=hazard_log,
                log_type="combat",
                dice_result={"hazard": hazard_result},
            ))

    # 借机攻击后检查战斗是否结束
    opp_combat_over, opp_outcome = False, None
    if opp_results or hazard_result or ready_action_results:
        opp_state   = session.game_state or {}
        opp_enemies = list(opp_state.get("enemies", []))
        player_opp  = await db.get(Character, session.player_character_id)
        opp_combat_over, opp_outcome = svc.check_combat_over(
            opp_enemies, player_opp.hp_current if player_opp else 0
        )
        if opp_combat_over:
            session.combat_active = False

    movement_payload = _build_movement_payload(
        entity_id=str(req.entity_id),
        entity_name=entity_name,
        start=cur,
        destination=destination,
        moved_distance=moved_distance,
        movement_cost=movement_cost,
        movement_cost_breakdown=movement_cost_breakdown,
        movement_stop=movement_stop,
        stand_result=stand_result,
        turn_state=ts,
        grapple_drag=grapple_drag,
    )
    movement_narration = _format_movement_narration(movement_payload)
    if moved_distance > 0 or stand_result.stood_up or movement_stop or grapple_drag:
        db.add(GameLog(
            session_id=session_id,
            role="system",
            content=movement_narration,
            log_type="combat",
            dice_result=movement_payload,
        ))

    await db.commit()
    combat_snapshot = await _build_combat_snapshot(
        db,
        session,
        combat,
        viewer_character_id=str(req.entity_id),
    )
    # 多人联机：广播位置变更
    from schemas.ws_events import EntityMoved
    await _broadcast_combat(session, combat, EntityMoved(
        entity_id=req.entity_id,
        position=destination,
        narration=movement_narration,
        movement=movement_payload,
        dice_result=movement_payload,
        special_action=movement_payload,
        hazard_result=hazard_result,
        ready_action_results=ready_action_results,
        opportunity_attacks=[
            {"attacker": o["attacker"], "target": o["target"], **o["result"]}
            for o in opp_results
        ],
        combat_over=opp_combat_over,
        outcome=opp_outcome,
    ), db=db)
    for dragged in (grapple_drag or {}).get("targets") or []:
        if not dragged.get("applied"):
            continue
        await _broadcast_combat(session, combat, EntityMoved(
            entity_id=dragged["target_id"],
            position=dict(dragged["to"]),
            hazard_result=None,
        ), db=db)
    return {
        "entity_id":               req.entity_id,
        "x":                       destination["x"],
        "y":                       destination["y"],
        "positions":               positions,
        "entity_positions":        positions,
        "combat":                  combat_snapshot,
        "hazard_result":           hazard_result,
        "turn_state":              ts,
        "movement_used":           ts["movement_used"],
        "movement_max":            ts["movement_max"],
        "stood_up":                stand_result.stood_up,
        "stand_up_cost":           stand_result.movement_cost,
        "conditions":              stand_result.conditions,
        "narration":               movement_narration,
        "movement":                movement_payload,
        "dice_result":             movement_payload,
        "special_action":          movement_payload,
        "movement_stop":           movement_stop,
        "movement_cost":           movement_cost,
        "movement_steps":          (movement_cost_breakdown or {}).get("steps", moved_distance),
        "movement_path":           (movement_cost_breakdown or {}).get("path", []),
        "difficult_terrain_extra": (movement_cost_breakdown or {}).get("difficult_terrain_extra", 0),
        "difficult_terrain_cells": (movement_cost_breakdown or {}).get("difficult_terrain_cells", []),
        "ignores_difficult_terrain": (movement_cost_breakdown or {}).get("ignores_difficult_terrain", False),
        "grapple_drag":            grapple_drag,
        "ready_action_results":    ready_action_results,
        "opportunity_attacks":     [
            {"attacker": o["attacker"], "target": o["target"], **o["result"]}
            for o in opp_results
        ],
        "combat_over":             opp_combat_over,
        "outcome":                 opp_outcome,
    }


async def _apply_stand_up_for_moving_entity(db, session, entity_id: str, turn_state: dict):
    state = session.game_state or {}
    for enemy in state.get("enemies", []) or []:
        if str(enemy.get("id")) != str(entity_id):
            continue
        try:
            result = apply_stand_up_from_prone(
                turn_state,
                enemy.get("conditions", []),
                enemy.get("condition_durations") or {},
            )
        except MovementRuleError as exc:
            raise HTTPException(400, _movement_rule_error_detail(exc)) from exc
        if result.stood_up:
            enemy["conditions"] = result.conditions
            session.game_state = dict(state)
            flag_modified(session, "game_state")
        return result

    character = await db.get(Character, entity_id)
    if not character:
        return apply_stand_up_from_prone(turn_state, [])
    try:
        result = apply_stand_up_from_prone(
            turn_state,
            character.conditions or [],
            character.condition_durations or {},
        )
    except MovementRuleError as exc:
        raise HTTPException(400, _movement_rule_error_detail(exc)) from exc
    if result.stood_up:
        character.conditions = result.conditions
    return result


async def _get_moving_condition_durations(db, session, entity_id: str) -> dict:
    state = session.game_state or {}
    for enemy in state.get("enemies", []) or []:
        if str(enemy.get("id")) == str(entity_id):
            return dict(enemy.get("condition_durations") or {})
    character = await db.get(Character, entity_id)
    if not character:
        return {}
    return dict(character.condition_durations or {})


async def _get_grapple_drag_candidates(db, session, actor_id: str) -> list[dict]:
    state = session.game_state or {}
    candidates: list[dict] = []
    for enemy in state.get("enemies", []) or []:
        if str(enemy.get("id")) == str(actor_id):
            continue
        candidates.append({
            "id": str(enemy.get("id")),
            "name": enemy.get("name") or "Target",
            "conditions": list(enemy.get("conditions") or []),
            "condition_durations": dict(enemy.get("condition_durations") or {}),
            "is_enemy": True,
        })

    result = await db.execute(
        select(Character).where(Character.session_id == str(session.id))
    )
    for character in result.scalars().all():
        if str(character.id) == str(actor_id):
            continue
        candidates.append({
            "id": str(character.id),
            "name": character.name,
            "conditions": list(character.conditions or []),
            "condition_durations": dict(character.condition_durations or {}),
            "is_enemy": False,
        })
    return candidates


async def _get_entity_name(db, session, entity_id: str) -> str:
    state = session.game_state or {}
    for enemy in state.get("enemies", []) or []:
        if str(enemy.get("id")) == str(entity_id):
            return str(enemy.get("name") or entity_id)
    character = await db.get(Character, entity_id)
    if character:
        return character.name
    return str(entity_id)


def _build_movement_payload(
    *,
    entity_id: str,
    entity_name: str,
    start: dict | None,
    destination: dict,
    moved_distance: int,
    movement_cost: int,
    movement_cost_breakdown: dict | None,
    movement_stop: dict | None,
    stand_result,
    turn_state: dict,
    grapple_drag: dict | None,
) -> dict:
    movement_used = int(turn_state.get("movement_used", 0) or 0)
    movement_max = int(turn_state.get("movement_max", 0) or 0)
    movement_steps = int((movement_cost_breakdown or {}).get("steps", moved_distance) or 0)
    payload = {
        "type": "movement",
        "entity_id": str(entity_id),
        "entity_name": entity_name,
        "from": dict(start) if start else None,
        "to": dict(destination),
        "position": dict(destination),
        "steps": moved_distance,
        "distance_ft": moved_distance * 5,
        "movement_cost": int(movement_cost or 0),
        "movement_steps": movement_steps,
        "movement_path": list((movement_cost_breakdown or {}).get("path", [])),
        "difficult_terrain_extra": int((movement_cost_breakdown or {}).get("difficult_terrain_extra", 0) or 0),
        "difficult_terrain_cells": list((movement_cost_breakdown or {}).get("difficult_terrain_cells", [])),
        "ignores_difficult_terrain": bool((movement_cost_breakdown or {}).get("ignores_difficult_terrain", False)),
        "movement_stop": movement_stop,
        "stood_up": bool(getattr(stand_result, "stood_up", False)),
        "stand_up_cost": int(getattr(stand_result, "movement_cost", 0) or 0),
        "conditions": list(getattr(stand_result, "conditions", []) or []),
        "movement_used": movement_used,
        "movement_max": movement_max,
        "movement_remaining": max(0, movement_max - movement_used),
    }
    if grapple_drag:
        payload["grapple_drag"] = grapple_drag
    return payload


def _format_movement_narration(movement: dict) -> str:
    actor = movement.get("entity_name") or movement.get("entity_id") or "A combatant"
    start = movement.get("from") or {}
    destination = movement.get("to") or {}
    if movement.get("stood_up") and not movement.get("steps"):
        return f"{actor} stands up."
    route = ""
    if start.get("x") is not None and destination.get("x") is not None:
        route = f" from ({start.get('x')},{start.get('y')}) to ({destination.get('x')},{destination.get('y')})"
    distance = movement.get("distance_ft") or 0
    cost = movement.get("movement_cost")
    cost_text = f", costing {cost} movement" if cost else ""
    stop = movement.get("movement_stop")
    stop_text = " and is stopped" if isinstance(stop, dict) and stop.get("applied") else ""
    return f"{actor} moves {distance} ft{route}{cost_text}{stop_text}."


def _grapple_drag_error_detail(drag_result: dict | None) -> str:
    reason = (drag_result or {}).get("blocked_reason") or ""
    if reason == "occupied":
        return "Cannot drag grappled target into an occupied space"
    if reason == "blocked_terrain":
        return "Cannot drag grappled target through blocking terrain"
    if reason == "out_of_bounds":
        return "Cannot drag grappled target out of bounds"
    return "Cannot drag grappled target"


def _movement_rule_error_detail(exc: MovementRuleError) -> str:
    if str(exc).startswith("speed_zero_condition_blocks"):
        return "Cannot stand up or move while speed is 0"
    if str(exc).startswith("frightened_source_blocks"):
        return "Cannot move closer to the source of fear while frightened"
    return "Not enough movement to stand up from prone"


# ── 法术 ─────────────────────────────────────────────────

