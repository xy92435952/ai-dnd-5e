"""
api.combat.reactions — 反应类能力（盾击 / 迅闪 / 不意防御 / 地狱诅咒）

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
    resolve_controlled_player_character,
)
from services.combat_service import CombatService
from services.spell_service import spell_service
from services.dnd_rules import roll_dice, _normalize_class
from services.combat_narrator import narrate_action, narrate_batch
from services.character_roster import CharacterRoster

from api.combat._shared import (
    _DEFAULT_TS, svc,
    _get_ts, _save_ts, _reset_ts,
    _broadcast_combat, _calc_entity_turn_limits,
    _chebyshev_dist, _check_attack_range, _ai_move_toward,
    _has_adjacent_enemy, _has_ally_adjacent_to,
    _do_concentration_check, _tick_conditions_char, _tick_conditions_enemy,
    _chebyshev, _resolve_opportunity_attacks,
)
from api.combat.ai_turn_utils import advance_after_pending_ai_attack
from api.combat.schemas import (
    MoveRequest, ConditionRequest, CombatActionRequest, DeathSaveRequest,
    SmiteRequest, ClassFeatureRequest, ReactionRequest, GrappleShoveRequest,
    AttackRollRequest, DamageRollRequest, SpellRequest, SpellRollRequest,
    SpellConfirmRequest, ManeuverRequest,
)
from schemas.combat_responses import CombatActionResult
from schemas.ws_events import CombatUpdate

router = APIRouter(prefix="/game", tags=["combat"])


async def _resolve_pending_ai_attack(
    *,
    session_id: str,
    session: Session,
    combat: CombatState,
    player: Character,
    turn_state: dict,
    pending: dict | None,
    db: AsyncSession,
    negated_by_shield: bool = False,
    damage_multiplier: float = 1.0,
):
    if not pending:
        return None

    target_id = str(pending.get("target_id") or "")
    if target_id != str(player.id):
        return None

    attack_roll = dict(pending.get("attack_roll") or {})
    incoming_damage = int(pending.get("damage") or 0)
    final_damage = int(incoming_damage * damage_multiplier)
    target_new_hp = player.hp_current
    conc_log = None

    if negated_by_shield:
        attack_roll["hit"] = False
        final_damage = 0
        narration = (
            f"{player.name}'s Shield turns the attack aside "
            f"({attack_roll.get('attack_total')} vs AC {attack_roll.get('target_ac')} + 5)."
        )
    else:
        player.hp_current = svc.apply_damage(
            player.hp_current,
            final_damage,
            (player.derived or {}).get("hp_max", player.hp_current),
        )
        target_new_hp = player.hp_current
        narration = svc._build_narration(
            pending.get("actor_name", "Attacker"),
            pending.get("target_name") or player.name,
            attack_roll,
            final_damage,
        )
        if final_damage > 0:
            conc_log = await _do_concentration_check(player, final_damage, session_id)

    turn_state.pop("pending_ai_attack", None)
    _save_ts(combat, player.id, turn_state)
    await advance_after_pending_ai_attack(combat, session, db, pending)

    db.add(GameLog(
        session_id=session_id,
        role="enemy",
        content=narration,
        log_type="combat",
        dice_result={"attack": attack_roll, "damage": final_damage},
    ))
    if conc_log:
        db.add(conc_log)

    state = session.game_state or {}
    enemies = list(state.get("enemies", []))
    combat_over, outcome = svc.check_combat_over(enemies, player.hp_current)
    if combat_over:
        session.combat_active = False

    return {
        "narration": narration,
        "attack_result": attack_roll,
        "damage": final_damage,
        "target_id": player.id,
        "target_new_hp": target_new_hp,
        "next_turn_index": combat.current_turn_index,
        "round_number": combat.round_number,
        "combat_over": combat_over,
        "outcome": outcome,
        "concentration_check": conc_log.dice_result if conc_log else None,
    }


@router.post("/combat/{session_id}/reaction", response_model=CombatActionResult)
async def use_reaction(
    session_id: str,
    req: ReactionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """
    Player uses reaction during enemy turn.
    reaction_type: "shield" | "uncanny_dodge" | "hellish_rebuke" | "opportunity_attack"
    Called by frontend when enemy attacks player and player has reaction available.
    """
    session = await get_session_or_404(session_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    player = await resolve_controlled_player_character(session, user_id, db)
    player_id = player.id
    await assert_can_act(session, user_id, player_id, db, require_current_turn=False)
    ts = _get_ts(combat, player_id)
    if ts.get("reaction_used"):
        raise HTTPException(400, "本回合反应已用尽")

    p_class = _normalize_class(player.char_class)
    p_level = player.level
    derived = player.derived or {}
    state = session.game_state or {}
    enemies = list(state.get("enemies", []))
    narration = ""
    reaction_effect = {}
    reaction_target_name = ""
    pending_ai_attack = dict(ts.get("pending_ai_attack") or {})
    settled_attack = None

    if req.reaction_type == "skip":
        settled = await _resolve_pending_ai_attack(
            session_id=session_id,
            session=session,
            combat=combat,
            player=player,
            turn_state=ts,
            pending=pending_ai_attack,
            db=db,
        )
        if not settled:
            raise HTTPException(400, "No pending reaction to skip")
        await db.commit()
        await _broadcast_combat(session, combat, CombatUpdate())
        return {
            "action": "reaction",
            "reaction_type": "skip",
            "narration": settled["narration"],
            "turn_state": _get_ts(combat, player_id),
            "reaction_effect": {"skipped": True},
            **settled,
        }

    if req.reaction_type == "shield":
        # Shield spell: AC+5 until next turn, costs 1st level slot
        known = set(player.known_spells or []) | set(player.prepared_spells or [])
        if "Shield" not in known and "shield" not in known:
            raise HTTPException(400, "你没有学会「护盾术」")
        slots = dict(player.spell_slots or {})
        if slots.get("1st", 0) <= 0:
            raise HTTPException(400, "没有可用的1环法术位")
        slots["1st"] -= 1
        player.spell_slots = slots

        ts["reaction_used"] = True
        _save_ts(combat, player_id, ts)

        # Temporarily boost AC (tracked in conditions until next turn)
        conditions = list(player.conditions or [])
        if "shield_spell" not in conditions:
            conditions.append("shield_spell")
        player.conditions = conditions
        durations = dict(player.condition_durations or {})
        durations["shield_spell"] = 1  # Expires at start of next turn
        player.condition_durations = durations

        old_ac = derived.get("ac", 10)
        new_ac = old_ac + 5
        narration = f"🛡️ {player.name} 用反应施放「护盾术」！AC {old_ac} → {new_ac}（持续至下回合）"
        reaction_effect = {"ac_bonus": 5, "new_ac": new_ac, "slot_used": "1st"}
        if pending_ai_attack:
            attack_roll = dict(pending_ai_attack.get("attack_roll") or {})
            shield_ac = old_ac + 5
            negated = (
                not attack_roll.get("is_crit")
                and int(attack_roll.get("attack_total") or 0) < shield_ac
            )
            settled_attack = await _resolve_pending_ai_attack(
                session_id=session_id,
                session=session,
                combat=combat,
                player=player,
                turn_state=ts,
                pending=pending_ai_attack,
                db=db,
                negated_by_shield=negated,
            )
            reaction_effect["attack_negated"] = bool(negated)
            if settled_attack:
                reaction_effect["settled_attack"] = {
                    "damage": settled_attack["damage"],
                    "target_new_hp": settled_attack["target_new_hp"],
                }

    elif req.reaction_type == "uncanny_dodge":
        # Rogue 5+: halve incoming damage
        if p_class != "Rogue":
            raise HTTPException(400, "只有游荡者可以使用灵巧闪避")
        if p_level < 5:
            raise HTTPException(400, "需要游荡者5级以上才能使用灵巧闪避")

        ts["reaction_used"] = True
        _save_ts(combat, player_id, ts)

        # Mark for damage halving (frontend applies before confirming damage)
        narration = f"⚡ {player.name} 使用「灵巧闪避」！本次受到的伤害减半！"
        reaction_effect = {"damage_halved": True}
        settled_attack = await _resolve_pending_ai_attack(
            session_id=session_id,
            session=session,
            combat=combat,
            player=player,
            turn_state=ts,
            pending=pending_ai_attack,
            db=db,
            damage_multiplier=0.5,
        )
        if settled_attack:
            reaction_effect["settled_attack"] = {
                "damage": settled_attack["damage"],
                "target_new_hp": settled_attack["target_new_hp"],
            }

    elif req.reaction_type == "hellish_rebuke":
        # Tiefling racial / Warlock: deal 2d10 fire damage to attacker
        slots = dict(player.spell_slots or {})
        if slots.get("1st", 0) <= 0:
            raise HTTPException(400, "没有可用的1环法术位")
        slots["1st"] -= 1
        player.spell_slots = slots

        ts["reaction_used"] = True
        _save_ts(combat, player_id, ts)

        rebuke_roll = roll_dice("2d10")
        rebuke_damage = rebuke_roll["total"]

        # Apply damage to the attacking enemy
        target_name = "攻击者"
        if req.target_id:
            for e in enemies:
                if e["id"] == req.target_id and e.get("hp_current", 0) > 0:
                    e["hp_current"] = svc.apply_damage(
                        e["hp_current"], rebuke_damage,
                        e.get("derived", {}).get("hp_max", 10),
                    )
                    target_name = e["name"]
            state["enemies"] = enemies
            session.game_state = dict(state); flag_modified(session, "game_state")

        reaction_target_name = target_name
        narration = f"🔥 {player.name} 使用「地狱斥责」！2d10={rebuke_damage} 火焰伤害反击 {target_name}！"
        reaction_effect = {"damage_dealt": rebuke_damage, "target": target_name}

    else:
        raise HTTPException(400, f"未知反应类型：{req.reaction_type}")

    # LLM vivid narration for reactions
    vivid = await narrate_action(
        actor_name=player.name, actor_class=p_class,
        target_name=reaction_target_name,
        action_type="reaction",
        extra_details=narration,
    )
    if vivid:
        narration = vivid

    db.add(GameLog(
        session_id=session_id, role="player",
        content=narration, log_type="combat",
        dice_result={"type": "reaction", "reaction_type": req.reaction_type, **reaction_effect},
    ))
    await db.commit()
    await _broadcast_combat(session, combat, CombatUpdate())

    # 反应骰子动画
    reaction_dice = None
    if req.reaction_type == "hellish_rebuke":
        reaction_dice = {"faces": 10, "result": reaction_effect.get("damage_dealt", 0), "label": "地狱斥责 2d10", "count": 2}

    return {
        "action": "reaction",
        "reaction_type": req.reaction_type,
        "narration": narration,
        "turn_state": _get_ts(combat, player_id),
        "reaction_effect": reaction_effect,
        "dice_roll": reaction_dice,
        **(settled_attack or {}),
    }


# ── 擒抱/推撞 (Grapple/Shove, P1-4) ────────────────────────

