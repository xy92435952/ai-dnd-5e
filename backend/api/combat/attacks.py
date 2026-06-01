"""
api.combat.attacks — 玩家主动攻击类行动（近战/远程/smite/擒抱/职业特性）

从原 combat.py (单体 5368 行) 按功能域拆出，逻辑未改动。
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from database import get_db
from models import Character, GameLog, CombatState
from api.deps import (
    assert_can_act,
    assert_character_can_act,
    assert_optional_session_access,
    get_session_or_404,
    get_optional_user_id,
)
from services.combat_narrator import narrate_action
from services.combat_outcome_service import check_and_cleanup_combat_outcome
from services.combat_attack_damage_service import apply_attack_damage_to_target
from services.combat_attack_roll_service import CombatAttackRollError
from services.combat_direct_attack_service import (
    apply_dark_ones_blessing_note,
    consume_direct_attack_turn,
    prepare_direct_attack,
)

from api.combat._shared import (
    _assert_expected_turn_token,
    _broadcast_combat,
    svc,
    _save_ts,
    _has_ally_adjacent_to,
)
from api.combat.attack_actions import maybe_handle_pre_attack_action
from api.combat.schemas import (
    CombatActionRequest,
)
from schemas.combat_responses import CombatActionResult
from schemas.ws_events import CombatUpdate

router = APIRouter(prefix="/game", tags=["combat"])


@router.post("/combat/{session_id}/action", response_model=CombatActionResult)
async def combat_action(
    session_id: str,
    req:        CombatActionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    """
    玩家战斗行动（攻击 / 闪避 / 冲刺 / 脱离接战 / 协助）。
    本端点不再自动推进回合——玩家需明确调用 /end-turn 结束回合。
    """
    action_text = req.action_text
    target_id   = req.target_id
    session = await get_session_or_404(session_id, db)
    await assert_optional_session_access(session, user_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    await db.refresh(session)  # 确保读取最新 game_state
    _assert_expected_turn_token(combat, req.expected_turn_token, detail_prefix="Combat action")

    player_id = session.player_character_id
    if session.is_multiplayer and combat.turn_order:
        try:
            current = combat.turn_order[combat.current_turn_index or 0]
            current_id = current.get("character_id") if isinstance(current, dict) else None
            if current_id:
                player_id = current_id
        except (IndexError, AttributeError):
            pass
    if user_id:
        await assert_can_act(session, user_id, player_id, db)
    else:
        await assert_character_can_act(player_id, db)
    player      = await db.get(Character, player_id)
    player_name = player.name if player else "你"
    state       = session.game_state or {}
    enemies     = list(state.get("enemies", []))

    pre_action = await maybe_handle_pre_attack_action(
        session_id=session_id,
        action_text=action_text,
        target_id=target_id,
        db=db,
        session=session,
        combat=combat,
        player=player,
        player_id=player_id,
        player_name=player_name,
        state=state,
        enemies=enemies,
    )
    if pre_action is not None:
        await _broadcast_combat(
            session,
            combat,
            CombatUpdate(
                actor_id=str(player_id),
                actor_name=player_name,
                narration=pre_action.get("narration"),
                action=pre_action.get("action"),
                target_id=pre_action.get("target_id"),
                target_new_hp=pre_action.get("target_new_hp"),
                combat_over=pre_action.get("combat_over", False),
                outcome=pre_action.get("outcome"),
            ),
            db=db,
        )
        return pre_action

    try:
        prepared = await prepare_direct_attack(
            db,
            combat=combat,
            player=player,
            player_id=player_id,
            target_id=target_id,
            enemies=enemies,
            is_ranged=req.is_ranged,
            session=session,
            combat_service=svc,
            has_ally_adjacent_to=_has_ally_adjacent_to,
        )
    except CombatAttackRollError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    attack_result_dict = prepared.attack_result
    damage = prepared.damage
    extra_damage_notes = prepared.extra_damage_notes

    mechanical_narration = svc._build_narration(
        player_name,
        prepared.target_name,
        attack_result_dict,
        damage,
    )
    if prepared.ranged_penalty:
        mechanical_narration = f"（相邻敌人，远程劣势）{mechanical_narration}"
    if extra_damage_notes:
        mechanical_narration += f"（{', '.join(extra_damage_notes)}）"

    # LLM vivid narration for old-path attack
    vivid = await narrate_action(
        actor_name=player_name, actor_class=prepared.player_class,
        target_name=prepared.target_name, action_type="attack",
        hit=attack_result_dict["hit"], is_crit=attack_result_dict["is_crit"],
        is_fumble=attack_result_dict["is_fumble"], damage=damage,
        damage_type=prepared.player_derived.get("damage_type", ""),
        extra_details=", ".join(extra_damage_notes) if extra_damage_notes else "",
    )
    narration = vivid if vivid else mechanical_narration

    # 更新 HP
    conc_log      = None
    target_new_hp = None
    target_state  = None
    if attack_result_dict["hit"]:
        target_new_hp, conc_log, target_state = await apply_attack_damage_to_target(
            db,
            session_id=session_id,
            enemies=enemies,
            target_id=prepared.target_id,
            target_is_enemy=prepared.target_is_enemy,
            damage=damage,
            session=session,
            is_critical=attack_result_dict.get("is_crit", False),
            attacker_id=str(player_id),
            attacker_is_enemy=False,
            is_melee=not req.is_ranged,
        )
        if prepared.target_is_enemy:
            state["enemies"]   = enemies
            session.game_state = dict(state); flag_modified(session, "game_state")

    # ── Dark One's Blessing: Warlock gains temp HP on kill ──
    extra_damage_notes = apply_dark_ones_blessing_note(
        player=player,
        target_new_hp=target_new_hp,
        target_is_enemy=prepared.target_is_enemy,
        subclass_effects=prepared.subclass_effects,
        player_derived=prepared.player_derived,
        player_level=prepared.player_level,
        extra_damage_notes=extra_damage_notes,
    )

    # 更新攻击计数
    ts = consume_direct_attack_turn(prepared.turn_state, attacks_max=prepared.attacks_max)
    if attack_result_dict["hit"]:
        ts["last_attack_target"] = prepared.target_id
        ts["last_attack_is_crit"] = bool(attack_result_dict.get("is_crit"))
    _save_ts(combat, player_id, ts)

    # Extra Attack 提示
    attacks_remaining = prepared.attacks_max - ts["attacks_made"]

    db.add(GameLog(
        session_id  = session_id,
        role        = "player",
        content     = narration,
        log_type    = "combat",
        dice_result = {
            "attack": attack_result_dict, "damage": prepared.damage_roll,
            "sneak_attack": prepared.sneak_attack_damage if prepared.sneak_attack_applied else None,
            "extra_damage": extra_damage_notes if extra_damage_notes else None,
        },
    ))
    if conc_log:
        db.add(conc_log)

    # 检查战斗是否结束（不推进回合）
    combat_over, outcome = await check_and_cleanup_combat_outcome(
        db,
        session=session,
        session_id=session_id,
        enemies=enemies,
        check_combat_over=svc.check_combat_over,
    )

    await db.commit()
    await _broadcast_combat(
        session,
        combat,
        CombatUpdate(
            actor_id=str(player_id),
            actor_name=player_name,
            narration=narration,
            action="attack",
            target_id=prepared.target_id,
            target_new_hp=target_new_hp,
            combat_over=combat_over,
            outcome=outcome,
        ),
        db=db,
    )
    return {
        "action":               "attack",
        "narration":            narration,
        "attack_result":        attack_result_dict,
        "damage":               damage,
        "target_id":            prepared.target_id,
        "target_new_hp":        target_new_hp,
        "target_state":         target_state,
        "ranged_penalty":       prepared.ranged_penalty,
        "cover_bonus":          prepared.cover_bonus,
        "feat_power_attack":    prepared.feat_power_attack,
        "weapon_resource":      prepared.weapon_resource,
        "sneak_attack":         prepared.sneak_attack_applied,
        "sneak_attack_damage":  prepared.sneak_attack_damage,
        "extra_damage_notes":   extra_damage_notes,
        "defender_interception": prepared.defender_interception,
        "attacks_made":         ts["attacks_made"],
        "attacks_max":          prepared.attacks_max,
        "attacks_remaining":    attacks_remaining,
        "concentration_check":  conc_log.dice_result if conc_log else None,
        "turn_state":           ts,
        "next_turn_index":      combat.current_turn_index,
        "round_number":         combat.round_number,
        "combat_over":          combat_over,
        "outcome":              outcome,
    }
