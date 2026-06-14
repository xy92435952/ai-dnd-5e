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
    get_optional_user_id, assert_can_act, assert_character_can_act,
    assert_character_in_session, assert_optional_session_access,
    broadcast_to_session, current_turn_user_id,
)
from services.combat_service import CombatService
from services.spell_service import spell_service
from services.combat_legendary_resistance_service import maybe_use_legendary_resistance
from services.dnd_rules import roll_dice, _normalize_class
from services.combat_narrator import narrate_action, narrate_batch
from services.combat_reaction_service import (
    apply_absorb_elements_state,
    calculate_absorb_elements_prevention,
    calculate_counterspell_result,
    calculate_cutting_words_prevention,
    calculate_hellish_rebuke_damage,
    calculate_reaction_save,
    calculate_shield_prevention,
    calculate_uncanny_dodge_prevention,
    character_knows_absorb_elements,
    character_knows_counterspell,
    choose_absorb_elements_slot,
    choose_counterspell_slot,
    CuttingWordsError,
    resolve_counterspell_eligibility,
    restore_prevented_damage,
    spend_cutting_words_resource,
)
from services.combat_temporary_hp_service import build_character_target_state
from services.combat_ai_spell_service import consume_ai_spell_slot, consume_named_spell_slot
from services.combat_action_rules_service import CombatActionRuleError, validate_can_take_reaction
from services.character_roster import CharacterRoster

from api.combat._shared import (
    _DEFAULT_TS, svc,
    _get_ts, _save_ts, _reset_ts,
    _broadcast_combat, _calc_entity_turn_limits,
    _project_ai_control_prompts_for_user,
    _chebyshev_dist, _check_attack_range, _ai_move_toward,
    _has_adjacent_enemy, _has_ally_adjacent_to,
    _do_concentration_check, _tick_conditions_char, _tick_conditions_enemy,
    _chebyshev, _resolve_opportunity_attacks,
)
from api.combat.ai_turn_utils import advance_ai_turn, build_deferred_lair_action_prompt
from api.combat.schemas import (
    MoveRequest, ConditionRequest, CombatActionRequest, DeathSaveRequest,
    SmiteRequest, ClassFeatureRequest, ReactionRequest, GrappleShoveRequest,
    AttackRollRequest, DamageRollRequest, SpellRequest, SpellRollRequest,
    SpellConfirmRequest, ManeuverRequest,
)
from schemas.combat_responses import CombatActionResult
from schemas.ws_events import CombatUpdate

router = APIRouter(prefix="/game", tags=["combat"])


def _actor_snapshot_for_attack_reaction(player, pending_reaction: dict):
    if not pending_reaction or pending_reaction.get("trigger") != "incoming_attack":
        return player
    hp_before = pending_reaction.get("target_hp_before_damage")
    if not isinstance(hp_before, int):
        hp_before = getattr(player, "hp_current", 0)
    return {
        "hp_current": hp_before,
        "death_saves": None,
        "conditions": pending_reaction.get(
            "target_conditions_before_damage",
            getattr(player, "conditions", None) or [],
        ),
    }


def _reaction_already_resolved(req: ReactionRequest, ts: dict) -> dict:
    return {
        "action": "reaction_already_resolved",
        "reaction_type": req.reaction_type,
        "narration": "",
        "turn_state": ts,
        "reaction_effect": {"already_resolved": True},
    }


def _has_pending_attack_reaction(ts: dict) -> bool:
    return (ts.get("pending_attack_reaction") or {}).get("trigger") == "incoming_attack"


def _has_pending_spell_reaction(ts: dict) -> bool:
    return (ts.get("pending_spell_reaction") or {}).get("trigger") == "spell_cast"


@router.post("/combat/{session_id}/reaction", response_model=CombatActionResult)
async def use_reaction(
    session_id: str,
    req: ReactionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    """
    Player uses reaction during enemy turn.
    reaction_type: "shield" | "counterspell" | "decline" | "uncanny_dodge" | "hellish_rebuke" | "absorb_elements"
    Called by frontend when an enemy attack or spell cast offers a reaction prompt.
    """
    session = await get_session_or_404(session_id, db)
    await assert_optional_session_access(session, user_id, db)
    if not session.combat_active:
        raise HTTPException(400, "当前不在战斗中")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise HTTPException(404, "战斗状态不存在")

    player_id = req.character_id or session.player_character_id
    if session.is_multiplayer and not req.character_id:
        if not user_id:
            raise HTTPException(401, "Login required for multiplayer combat")
        from models import SessionMember
        member_result = await db.execute(
            select(SessionMember).where(
                SessionMember.session_id == session_id,
                SessionMember.user_id == user_id,
            )
        )
        member = member_result.scalar_one_or_none()
        if member and member.character_id:
            player_id = member.character_id

    if user_id:
        await assert_can_act(
            session,
            user_id,
            player_id,
            db,
            require_current_turn=False,
            allow_incapacitated=True,
        )
    else:
        await assert_character_can_act(player_id, db, allow_incapacitated=True)

    player = await db.get(Character, player_id)
    if not player:
        raise HTTPException(404, "玩家角色不存在")

    await assert_character_in_session(player, session, db)
    ts = _get_ts(combat, player_id)
    pending_reaction = ts.get("pending_attack_reaction") or {}
    pending_spell_reaction = ts.get("pending_spell_reaction") or {}
    try:
        validate_can_take_reaction(_actor_snapshot_for_attack_reaction(player, pending_reaction))
    except CombatActionRuleError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    if ts.get("reaction_used"):
        return _reaction_already_resolved(req, ts)

    p_class = _normalize_class(player.char_class)
    p_level = player.level
    derived = player.derived or {}
    attack_reaction_types = {"shield", "uncanny_dodge", "hellish_rebuke", "absorb_elements", "cutting_words"}
    if req.reaction_type in attack_reaction_types and not _has_pending_attack_reaction(ts):
        return _reaction_already_resolved(req, ts)
    if req.reaction_type == "counterspell" and not _has_pending_spell_reaction(ts):
        return _reaction_already_resolved(req, ts)

    state = session.game_state or {}
    enemies = list(state.get("enemies", []))
    narration = ""
    reaction_effect = {}
    reaction_target_name = ""
    lair_action_prompt = None
    legendary_action_prompt = None

    if req.reaction_type == "decline":
        if pending_reaction:
            lair_action_prompt = await build_deferred_lair_action_prompt(
                combat,
                session,
                db,
                combat.turn_order or [],
                pending_reaction.get("deferred_lair_action"),
            )
            if lair_action_prompt:
                legendary_action_prompt = None
        if pending_spell_reaction:
            ts["resume_spell_reaction"] = pending_spell_reaction
            ts.pop("pending_spell_reaction", None)
        ts.pop("pending_attack_reaction", None)
        _save_ts(combat, player_id, ts)
        await db.commit()
        if lair_action_prompt:
            await _broadcast_combat(
                session,
                combat,
                CombatUpdate(
                    actor_id=str(player_id),
                    actor_name=player.name,
                    reaction_type=req.reaction_type,
                    target_id=req.target_id,
                    lair_action_prompt=lair_action_prompt,
                    legendary_action_prompt=legendary_action_prompt,
                ),
                db=db,
            )
        return await _project_ai_control_prompts_for_user(db, session, user_id, {
            "action": "reaction_declined",
            "reaction_type": req.reaction_type,
            "narration": "",
            "turn_state": ts,
            "lair_action_prompt": lair_action_prompt,
            "legendary_action_prompt": legendary_action_prompt,
        })

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
        shield_result = calculate_shield_prevention(pending_reaction)
        hp_result = restore_prevented_damage(
            player,
            pending_reaction,
            shield_result["damage_prevented"],
        )
        ts.pop("pending_attack_reaction", None)
        _save_ts(combat, player_id, ts)

        narration = f"🛡️ {player.name} 用反应施放「护盾术」！AC {old_ac} → {new_ac}（持续至下回合）"
        if hp_result["hp_restored"] > 0:
            narration += f" 护盾让 {shield_result['blocked_attacks']} 次攻击落空，恢复 {hp_result['hp_restored']} 点已结算伤害。"
        reaction_effect = {
            "ac_bonus": 5,
            "new_ac": new_ac,
            "slot_used": "1st",
            **shield_result,
            **hp_result,
        }

    elif req.reaction_type == "uncanny_dodge":
        # Rogue 5+: halve incoming damage
        if p_class != "Rogue":
            raise HTTPException(400, "只有游荡者可以使用灵巧闪避")
        if p_level < 5:
            raise HTTPException(400, "需要游荡者5级以上才能使用灵巧闪避")

        dodge_result = calculate_uncanny_dodge_prevention(pending_reaction)
        hp_result = restore_prevented_damage(
            player,
            pending_reaction,
            dodge_result["damage_prevented"],
        )
        ts["reaction_used"] = True
        ts.pop("pending_attack_reaction", None)
        _save_ts(combat, player_id, ts)

        narration = f"⚡ {player.name} 使用「灵巧闪避」！本次受到的伤害减半！"
        if hp_result["hp_restored"] > 0:
            narration += f" 恢复 {hp_result['hp_restored']} 点已结算伤害。"
        reaction_effect = {"damage_halved": True, **dodge_result, **hp_result}

    elif req.reaction_type == "absorb_elements":
        if not character_knows_absorb_elements(player):
            raise HTTPException(400, "You have not learned Absorb Elements")

        slot_choice = choose_absorb_elements_slot(player.spell_slots or {})
        if not slot_choice:
            raise HTTPException(400, "No available 1st-level or higher spell slot")

        absorb_result = calculate_absorb_elements_prevention(pending_reaction)
        if absorb_result["damage_prevented"] <= 0 or not absorb_result["damage_type"]:
            raise HTTPException(
                400,
                "Absorb Elements requires incoming acid, cold, fire, lightning, or thunder damage",
            )

        slot_key, slot_level = slot_choice
        consume_named_spell_slot(player, slot_key)
        hp_result = restore_prevented_damage(
            player,
            pending_reaction,
            absorb_result["damage_prevented"],
        )
        absorb_state = apply_absorb_elements_state(
            player,
            absorb_result["damage_type"],
            slot_level,
        )

        ts["reaction_used"] = True
        ts.pop("pending_attack_reaction", None)
        _save_ts(combat, player_id, ts)

        reaction_target_name = pending_reaction.get("attacker_name") or "attacker"
        narration = (
            f"{player.name} uses Absorb Elements, bracing against "
            f"{absorb_result['damage_type']} damage."
        )
        if hp_result["hp_restored"] > 0:
            narration += f" Restored {hp_result['hp_restored']} already-applied damage."
        reaction_effect = {
            "slot_used": slot_key,
            **absorb_result,
            **absorb_state,
            **hp_result,
        }

    elif req.reaction_type == "cutting_words":
        try:
            cutting_words = spend_cutting_words_resource(
                player,
                cutting_words_roll=req.cutting_words_roll,
            )
        except CuttingWordsError as exc:
            raise HTTPException(400, str(exc)) from exc

        cutting_result = calculate_cutting_words_prevention(
            pending_reaction,
            cutting_words_roll=cutting_words["roll"],
        )
        hp_result = restore_prevented_damage(
            player,
            pending_reaction,
            cutting_result["damage_prevented"],
        )
        ts["reaction_used"] = True
        ts.pop("pending_attack_reaction", None)
        _save_ts(combat, player_id, ts)

        reaction_target_name = pending_reaction.get("attacker_name") or "attacker"
        if cutting_result["blocked_attack"]:
            narration = (
                f"{player.name} uses Cutting Words ({cutting_words['die']}={cutting_words['roll']}), "
                f"turning {reaction_target_name}'s attack from "
                f"{cutting_result['attack_total_before']} to {cutting_result['attack_total_after']} "
                f"against AC{cutting_result['target_ac']}."
            )
        else:
            narration = (
                f"{player.name} uses Cutting Words ({cutting_words['die']}={cutting_words['roll']}), "
                f"but {reaction_target_name}'s attack still lands at "
                f"{cutting_result['attack_total_after']} against AC{cutting_result['target_ac']}."
            )
        if hp_result["hp_restored"] > 0:
            narration += f" Restored {hp_result['hp_restored']} already-applied damage."
        reaction_effect = {
            "cutting_words": cutting_words,
            **cutting_result,
            **hp_result,
            "class_resources": player.class_resources or {},
        }

    elif req.reaction_type == "hellish_rebuke":
        # Tiefling racial / Warlock: deal 2d10 fire damage to attacker
        known = set(player.known_spells or []) | set(player.prepared_spells or [])
        if "Hellish Rebuke" not in known and "hellish_rebuke" not in known:
            raise HTTPException(400, "You have not learned Hellish Rebuke")
        slots = dict(player.spell_slots or {})
        if slots.get("1st", 0) <= 0:
            raise HTTPException(400, "没有可用的1环法术位")
        slots["1st"] -= 1
        player.spell_slots = slots

        ts["reaction_used"] = True
        ts.pop("pending_attack_reaction", None)
        _save_ts(combat, player_id, ts)

        rebuke_roll = roll_dice("2d10")
        rebuke_damage = rebuke_roll["total"]
        spell_save_dc = int(derived.get("spell_save_dc") or 13)
        save_detail = None
        damage_result = calculate_hellish_rebuke_damage(rebuke_damage, save_detail)

        # Apply damage to the attacking enemy
        target_name = "攻击者"
        if req.target_id:
            for e in enemies:
                if e["id"] == req.target_id and e.get("hp_current", 0) > 0:
                    save_roll = roll_dice("1d20")["rolls"][0]
                    save_detail = calculate_reaction_save(
                        e.get("derived", {}),
                        ability="dex",
                        dc=spell_save_dc,
                        d20=save_roll,
                        conditions=e.get("conditions", []),
                        condition_durations=e.get("condition_durations", {}),
                    )
                    save_detail = maybe_use_legendary_resistance(
                        e,
                        save_detail,
                        reason="reaction_save",
                    )
                    damage_result = calculate_hellish_rebuke_damage(rebuke_damage, save_detail)
                    e["hp_current"] = svc.apply_damage(
                        e["hp_current"], damage_result["damage_dealt"],
                        e.get("derived", {}).get("hp_max", 10),
                    )
                    target_name = e["name"]
            state["enemies"] = enemies
            session.game_state = dict(state); flag_modified(session, "game_state")

        reaction_target_name = target_name
        narration = f"🔥 {player.name} 使用「地狱斥责」！2d10={rebuke_damage} 火焰伤害反击 {target_name}！"
        if save_detail:
            save_outcome = "success, half damage" if save_detail["success"] else "failed, full damage"
            narration += (
                f" DEX save DC{save_detail['dc']}: "
                f"d20={save_detail['d20']}+{save_detail['modifier']}={save_detail['total']} "
                f"{save_outcome}; final damage {damage_result['damage_dealt']}."
            )
        reaction_effect = {
            "damage_dealt": damage_result["damage_dealt"],
            "rolled_damage": damage_result["rolled_damage"],
            "save_success": damage_result["save_success"],
            "save": save_detail,
            "target": target_name,
        }

    elif req.reaction_type == "counterspell":
        if pending_spell_reaction.get("trigger") != "spell_cast":
            raise HTTPException(400, "No spell is pending Counterspell")
        if not character_knows_counterspell(player):
            raise HTTPException(400, "You have not learned Counterspell")

        spell_level = int(pending_spell_reaction.get("spell_level") or 0)
        slot_choice = choose_counterspell_slot(player.spell_slots or {}, spell_level)
        if not slot_choice:
            raise HTTPException(400, "No available 3rd-level or higher spell slot")
        slot_key, slot_level = slot_choice

        caster_id = pending_spell_reaction.get("caster_id")
        caster_conditions = []
        for enemy in enemies:
            if str(enemy.get("id")) == str(caster_id):
                caster_conditions = enemy.get("conditions", [])
                break
        eligibility = resolve_counterspell_eligibility(
            reactor=player,
            caster_id=caster_id,
            combat=combat,
            caster_conditions=caster_conditions,
        )
        if not eligibility["can_counterspell"]:
            reason = eligibility.get("reason") or "not_eligible"
            if reason == "out_of_range":
                raise HTTPException(
                    400,
                    f"Counterspell target is out of range ({eligibility.get('distance_ft')}ft > {eligibility.get('range_ft')}ft)",
                )
            if reason in {"caster_not_visible", "reactor_blinded"}:
                raise HTTPException(400, "Counterspell requires seeing the spellcaster")
            raise HTTPException(400, "Counterspell cannot be used right now")

        counter_result = calculate_counterspell_result(
            countered_spell_level=spell_level,
            counterspell_slot_level=slot_level,
            caster_derived=derived,
            roll_dice_func=roll_dice,
        )
        consume_named_spell_slot(player, slot_key)

        ts["reaction_used"] = True
        ts.pop("pending_spell_reaction", None)
        if not counter_result["success"]:
            ts["resume_spell_reaction"] = pending_spell_reaction
        else:
            ts.pop("resume_spell_reaction", None)
        _save_ts(combat, player_id, ts)
        if counter_result["success"]:
            for enemy in enemies:
                if str(enemy.get("id")) == str(caster_id):
                    if spell_level > 0:
                        consume_ai_spell_slot(enemy, spell_level)
                    state["enemies"] = enemies
                    session.game_state = dict(state)
                    flag_modified(session, "game_state")
                    break
            turn_order = combat.turn_order or []
            if turn_order:
                next_index = ((combat.current_turn_index or 0) + 1) % max(len(turn_order), 1)
                advance_result = await advance_ai_turn(combat, session, db, turn_order, next_index)
                lair_action_prompt = advance_result.get("lair_action_prompt")
                legendary_action_prompt = advance_result.get("legendary_action_prompt")

        caster_name = pending_spell_reaction.get("caster_name") or "caster"
        spell_name = pending_spell_reaction.get("spell_name") or "spell"
        caster_id = pending_spell_reaction.get("caster_id")
        reaction_target_name = caster_name
        if counter_result["success"]:
            narration = (
                f"{player.name} uses Counterspell and cancels "
                f"{caster_name}'s {spell_name}."
            )
        else:
            narration = (
                f"{player.name} uses Counterspell against {caster_name}'s {spell_name}, "
                f"but the check fails."
            )
        reaction_effect = {
            "spell_cancelled": counter_result["success"],
            "countered_spell": spell_name,
            "countered_spell_level": spell_level,
            "caster_id": caster_id,
            "caster_name": caster_name,
            "slot_used": slot_key,
            "slot_level": slot_level,
            "check": counter_result,
        }

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

    if not lair_action_prompt and pending_reaction:
        lair_action_prompt = await build_deferred_lair_action_prompt(
            combat,
            session,
            db,
            combat.turn_order or [],
            pending_reaction.get("deferred_lair_action"),
        )
        if lair_action_prompt:
            legendary_action_prompt = None

    reaction_result = {
        "type": "reaction",
        "reaction_type": req.reaction_type,
        **reaction_effect,
    }

    db.add(GameLog(
        session_id=session_id, role="player",
        content=narration, log_type="combat",
        dice_result=reaction_result,
    ))
    target_state = build_character_target_state(player)
    target_state["target_name"] = player.name
    await db.commit()
    await _broadcast_combat(
        session,
        combat,
        CombatUpdate(
            actor_id=str(player_id),
            actor_name=player.name,
            narration=narration,
            action="reaction",
            reaction_type=req.reaction_type,
            reaction_effect=reaction_effect,
            target_id=req.target_id,
            target_name=reaction_target_name,
            target_state=target_state,
            actor_state=target_state,
            remaining_slots=player.spell_slots or {},
            dice_result=reaction_result,
            special_action=reaction_result,
            lair_action_prompt=lair_action_prompt,
            legendary_action_prompt=legendary_action_prompt,
        ),
        db=db,
    )

    # 反应骰子动画
    reaction_dice = None
    if req.reaction_type == "hellish_rebuke":
        reaction_dice = {"faces": 10, "result": reaction_effect.get("damage_dealt", 0), "label": "地狱斥责 2d10", "count": 2}

    if req.reaction_type == "cutting_words":
        cutting_words = reaction_effect.get("cutting_words") or {}
        try:
            faces = int(str(cutting_words.get("die") or "d6").lstrip("dD"))
        except (TypeError, ValueError):
            faces = 6
        reaction_dice = {
            "faces": faces,
            "result": cutting_words.get("roll"),
            "label": "Cutting Words",
            "count": 1,
        }

    return await _project_ai_control_prompts_for_user(db, session, user_id, {
        "action": "reaction",
        "reaction_type": req.reaction_type,
        "narration": narration,
        "turn_state": ts,
        "reaction_effect": reaction_effect,
        "target_state": target_state,
        "remaining_slots": player.spell_slots or {},
        "dice_result": reaction_result,
        "special_action": reaction_result,
        "dice_roll": reaction_dice,
        "lair_action_prompt": lair_action_prompt,
        "legendary_action_prompt": legendary_action_prompt,
    })


# ── 擒抱/推撞 (Grapple/Shove, P1-4) ────────────────────────

