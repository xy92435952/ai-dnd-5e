"""
api.combat.ai_turn_utils — shared helpers for AI combat turns.
"""
from sqlalchemy.orm.attributes import flag_modified

from api.combat._shared import (
    _calc_entity_turn_limits,
    _reset_ts,
    _set_active_ai_control_prompt,
    _tick_conditions_char,
    _tick_conditions_enemy,
)
from api.deps import entity_snapshot
from models import Character, GameLog
from services.character_roster import CharacterRoster
from services.combat_legendary_action_service import (
    build_lair_action_prompt,
    build_legendary_action_prompt,
    should_prompt_lair_action_for_turn_advance,
)
from services.combat_reaction_service import (
    calculate_absorb_elements_prevention,
    get_cutting_words_die,
    build_pending_spell_reaction,
    character_knows_absorb_elements,
    character_knows_counterspell,
    choose_absorb_elements_slot,
    choose_counterspell_slot,
    resolve_counterspell_eligibility,
    calculate_shield_prevention,
    calculate_uncanny_dodge_prevention,
)
from services.combat_action_rules_service import can_take_reaction
from services.dnd_rules import _normalize_class
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
from services.combat_ready_action_service import (
    apply_ready_action_expiry_to_turn_state,
    build_ready_action_expiry,
    build_ready_action_expiry_log,
    clear_expired_ready_spell_concentration_hold,
)


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


async def _build_lair_action_prompt_for_turn_advance(
    combat,
    session,
    db,
    turn_order,
    *,
    current_index: int,
    next_index: int,
    round_started: bool,
    target_candidates: list[dict] | None = None,
):
    state = session.game_state or {}
    enemies = list(state.get("enemies", []))
    lair_timing_reached = should_prompt_lair_action_for_turn_advance(
        turn_order,
        current_index=current_index,
        next_index=next_index,
        round_started=round_started,
    )
    if not lair_timing_reached:
        return None
    if (
        int(state.get("lair_action_prompted_round", 0) or 0) == int(combat.round_number or 0)
        or int(state.get("lair_action_used_round", 0) or 0) == int(combat.round_number or 0)
    ):
        return None

    if target_candidates is None:
        roster = CharacterRoster(db, session)
        target_candidates = [
            entity_snapshot(character, is_enemy=False)
            for character in await roster.party()
            if character and int(character.hp_current or 0) > 0
        ]
    current = turn_order[current_index % len(turn_order)] if turn_order else {}
    lair_action_prompt = build_lair_action_prompt(
        state,
        enemies,
        round_number=int(combat.round_number or 1),
        timing="initiative_count_20",
        trigger_entity_id=current.get("character_id") if isinstance(current, dict) else None,
        trigger_entity_name=current.get("name") if isinstance(current, dict) else None,
        positions=dict(combat.entity_positions or {}),
        target_candidates=target_candidates,
    )
    if lair_action_prompt:
        state["lair_action_prompted_round"] = int(combat.round_number or 1)
        state["enemies"] = enemies
        session.game_state = dict(state)
        flag_modified(session, "game_state")
        _set_active_ai_control_prompt(session, lair_action_prompt=lair_action_prompt)
    return lair_action_prompt


async def build_deferred_lair_action_prompt(combat, session, db, turn_order, context: dict | None):
    if not context:
        return None
    try:
        current_index = int(context.get("current_index"))
        next_index = int(context.get("next_index"))
    except (TypeError, ValueError):
        return None
    return await _build_lair_action_prompt_for_turn_advance(
        combat,
        session,
        db,
        turn_order,
        current_index=current_index,
        next_index=next_index,
        round_started=bool(context.get("round_started")),
    )


async def advance_ai_turn(combat, session, db, turn_order, next_index: int, *, include_lair_prompt: bool = True):
    """Advance combat state to the next turn and reset the next actor's turn state."""
    current_index = combat.current_turn_index or 0
    round_started = next_index == 0
    combat.current_turn_index = next_index
    if round_started:
        combat.round_number += 1
    turn_start_hazard = None
    turn_start_hazard_log = ""
    expired_ready_action = None
    ready_action_expired_log = ""
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
        if confusion_turn_result:
            actor_name = next_turn.get("name") if isinstance(next_turn, dict) else str(next_entity_id)
            db.add(GameLog(
                session_id=session.id,
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
                db.add(GameLog(
                    session_id=session.id,
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
        )
        hazard_log = hazard_result_to_log_text(turn_start_hazard)
        if hazard_log:
            turn_start_hazard_log = hazard_log
            db.add(GameLog(
                session_id=session.id,
                role="system",
                content=hazard_log,
                log_type="combat",
                dice_result={"hazard": turn_start_hazard},
            ))
        if expired_ready_action:
            await clear_expired_ready_spell_concentration_hold(db, str(next_entity_id), expired_ready_action)
            apply_ready_action_expiry_to_turn_state(combat, str(next_entity_id), expired_ready_action)
            ready_log = build_ready_action_expiry_log(str(session.id), expired_ready_action)
            ready_action_expired_log = ready_log.content
            db.add(ready_log)

    ai_control_target_candidates = None
    current = turn_order[current_index % len(turn_order)] if turn_order else {}

    async def get_ai_control_target_candidates():
        nonlocal ai_control_target_candidates
        if ai_control_target_candidates is None:
            roster = CharacterRoster(db, session)
            ai_control_target_candidates = [
                entity_snapshot(character, is_enemy=False)
                for character in await roster.party()
                if character and int(character.hp_current or 0) > 0
            ]
        return ai_control_target_candidates

    lair_action_prompt = None
    legendary_action_prompt = None
    if include_lair_prompt:
        target_candidates = await get_ai_control_target_candidates()
        lair_action_prompt = await _build_lair_action_prompt_for_turn_advance(
            combat,
            session,
            db,
            turn_order,
            current_index=current_index,
            next_index=next_index,
            round_started=round_started,
            target_candidates=target_candidates,
        )

        if not lair_action_prompt:
            state = session.game_state or {}
            enemies = list(state.get("enemies", []) or [])
            legendary_action_prompt = build_legendary_action_prompt(
                enemies,
                trigger_entity_id=current.get("character_id") if isinstance(current, dict) else None,
                trigger_entity_name=current.get("name") if isinstance(current, dict) else None,
                positions=dict(combat.entity_positions or {}),
                target_candidates=target_candidates,
            )
            if legendary_action_prompt:
                state["enemies"] = enemies
                session.game_state = dict(state)
                flag_modified(session, "game_state")
    _set_active_ai_control_prompt(
        session,
        lair_action_prompt=lair_action_prompt,
        legendary_action_prompt=legendary_action_prompt,
    )

    return {
        "turn_start_hazard": turn_start_hazard,
        "turn_start_hazard_log": turn_start_hazard_log,
        "expired_ready_action": expired_ready_action,
        "ready_action_expired_log": ready_action_expired_log,
        "confusion_turn": confusion_turn_result,
        "lair_action_prompt": lair_action_prompt,
        "legendary_action_prompt": legendary_action_prompt,
    }


async def _confusion_actor_for_turn(db, session, turn: dict | None, entity_id: str):
    if isinstance(turn, dict) and turn.get("is_enemy"):
        state = session.game_state or {}
        return next(
            (enemy for enemy in state.get("enemies", []) or [] if str(enemy.get("id")) == str(entity_id)),
            None,
        )
    return await db.get(Character, entity_id)


def tick_ai_actor_conditions(
    *,
    session_id: str,
    session,
    combat=None,
    actor_name: str,
    is_enemy: bool,
    enemy,
    character,
    enemies: list[dict] | None = None,
) -> list[GameLog]:
    """Tick the AI actor's own conditions at the end of its turn."""
    tick_logs: list[GameLog] = []
    if is_enemy and enemy:
        confusion_end_save = resolve_confusion_end_of_turn_save(
            enemy,
            entity_id=str(enemy.get("id") or ""),
            actor_name=actor_name,
        )
        if confusion_end_save:
            tick_logs.append(GameLog(
                session_id=session_id,
                role="system",
                content=build_confusion_end_save_log(actor_name, confusion_end_save),
                log_type="combat",
                dice_result=confusion_end_save,
            ))
        condition_end_saves = resolve_repeat_save_end_of_turn_saves(
            enemy,
            entity_id=str(enemy.get("id") or ""),
            actor_name=actor_name,
            combat=combat,
        )
        for condition_end_save in condition_end_saves:
            tick_logs.append(GameLog(
                session_id=session_id,
                role="system",
                content=build_condition_end_save_log(actor_name, condition_end_save),
                log_type="combat",
                dice_result=condition_end_save,
            ))
        removed = _tick_conditions_enemy(enemy)
        for condition in removed:
            tick_logs.append(GameLog(
                session_id=session_id,
                role="system",
                content=f"🟢 {actor_name} 的【{condition}】状态到期解除",
                log_type="system",
            ))
        if enemies is not None:
            state = session.game_state or {}
            state["enemies"] = enemies
            session.game_state = dict(state)
            flag_modified(session, "game_state")
    elif not is_enemy and character:
        confusion_end_save = resolve_confusion_end_of_turn_save(
            character,
            entity_id=str(getattr(character, "id", "")),
            actor_name=actor_name,
        )
        if confusion_end_save:
            tick_logs.append(GameLog(
                session_id=session_id,
                role="system",
                content=build_confusion_end_save_log(actor_name, confusion_end_save),
                log_type="combat",
                dice_result=confusion_end_save,
            ))
        condition_end_saves = resolve_repeat_save_end_of_turn_saves(
            character,
            entity_id=str(getattr(character, "id", "")),
            actor_name=actor_name,
            combat=combat,
        )
        for condition_end_save in condition_end_saves:
            tick_logs.append(GameLog(
                session_id=session_id,
                role="system",
                content=build_condition_end_save_log(actor_name, condition_end_save),
                log_type="combat",
                dice_result=condition_end_save,
            ))
        removed = _tick_conditions_char(character)
        for condition in removed:
            tick_logs.append(GameLog(
                session_id=session_id,
                role="system",
                content=f"🟢 {actor_name} 的【{condition}】状态到期解除",
                log_type="system",
            ))
    return tick_logs


def build_reaction_prompt(
    player_check,
    player_ts: dict,
    target_id,
    actor_name: str,
    actor_id: str,
    total_damage: int,
    result_obj,
):
    """Build the reaction prompt shown when the player is targeted."""
    if not player_check:
        return False, False, None

    if str(target_id) != str(player_check.id):
        return False, False, None

    if player_ts.get("reaction_used"):
        return True, False, None
    pending_reaction = player_ts.get("pending_attack_reaction") or {}
    if not can_take_reaction(_actor_snapshot_for_attack_reaction(player_check, pending_reaction)):
        return True, False, None

    p_derived_r = player_check.derived or {}
    p_cls = _normalize_class(player_check.char_class)
    p_level = player_check.level or 1
    known_spells = set(player_check.known_spells or []) | set(player_check.prepared_spells or [])
    p_slots = dict(player_check.spell_slots or {})
    available_reactions = []

    if ("Shield" in known_spells or "shield" in known_spells) and p_slots.get("1st", 0) > 0:
        shield_preview = calculate_shield_prevention(pending_reaction)
        available_reactions.append({
            "id": "shield",
            "name": "Shield",
            "type": "shield",
            "cost": "1st-level spell slot",
            "slot_level": "1st",
            "slots_remaining": p_slots.get("1st", 0),
            "effect": "+5 AC（持续到你的下个回合开始）",
            "resulting_ac": p_derived_r.get("ac", 10) + 5,
            "damage_prevented": shield_preview["damage_prevented"],
            "blocked_attacks": shield_preview["blocked_attacks"],
        })

    absorb_slot = choose_absorb_elements_slot(p_slots)
    absorb_preview = calculate_absorb_elements_prevention(pending_reaction)
    if (
        character_knows_absorb_elements(player_check)
        and absorb_slot
        and absorb_preview["damage_prevented"] > 0
    ):
        slot_key, slot_level = absorb_slot
        available_reactions.append({
            "id": "absorb_elements",
            "name": "Absorb Elements",
            "type": "absorb_elements",
            "cost": f"{slot_key} spell slot",
            "slot_level": slot_key,
            "slot_level_number": slot_level,
            "slots_remaining": p_slots.get(slot_key, 0),
            "effect": (
                f"Gain resistance to {absorb_preview['damage_type']} and reduce this hit "
                f"from {absorb_preview['original_damage']} to {absorb_preview['reduced_damage']}; "
                f"next melee hit deals +{slot_level}d6 {absorb_preview['damage_type']}."
            ),
            "damage_type": absorb_preview["damage_type"],
            "damage_prevented": absorb_preview["damage_prevented"],
            "reduced_damage": absorb_preview["reduced_damage"],
            "extra_damage_dice": f"{slot_level}d6",
        })

    if p_cls == "Rogue" and p_level >= 5:
        dodge_preview = calculate_uncanny_dodge_prevention(pending_reaction)
        available_reactions.append({
            "id": "uncanny_dodge",
            "name": "Uncanny Dodge",
            "type": "uncanny_dodge",
            "cost": "reaction",
            "effect": f"将此次攻击的伤害减半（{dodge_preview['original_damage']} → {dodge_preview['reduced_damage']}）",
            "reduced_damage": dodge_preview["reduced_damage"],
            "damage_prevented": dodge_preview["damage_prevented"],
        })

    cutting_die = get_cutting_words_die(player_check)
    if cutting_die:
        attack_total = result_obj.attack_roll.get("attack_total", 0) if result_obj else 0
        incoming_damage = int((pending_reaction or {}).get("incoming_damage") or total_damage or 0)
        available_reactions.append({
            "id": "cutting_words",
            "name": "Cutting Words",
            "type": "cutting_words",
            "cost": f"reaction + Bardic Inspiration {cutting_die}",
            "die": cutting_die,
            "effect": (
                f"Roll {cutting_die} and subtract it from the attack "
                f"({attack_total} vs AC{p_derived_r.get('ac', 10)})."
            ),
        })
        if incoming_damage > 0:
            available_reactions.append({
                "id": "cutting_words_damage",
                "name": "Cutting Words: Damage",
                "type": "cutting_words_damage",
                "cost": f"reaction + Bardic Inspiration {cutting_die}",
                "die": cutting_die,
                "damage_roll_before": incoming_damage,
                "effect": (
                    f"Roll {cutting_die} and subtract it from the damage "
                    f"roll ({incoming_damage} damage)."
                ),
            })

    if ("Hellish Rebuke" in known_spells or "hellish_rebuke" in known_spells) and p_slots.get("1st", 0) > 0:
        available_reactions.append({
            "id": "hellish_rebuke",
            "name": "Hellish Rebuke",
            "type": "hellish_rebuke",
            "cost": "1st-level spell slot",
            "slot_level": "1st",
            "slots_remaining": p_slots.get("1st", 0),
            "effect": "对攻击者造成 2d10 火焰伤害（DEX豁免成功减半）",
            "damage_dice": "2d10",
        })

    if not available_reactions:
        return True, False, None

    return True, True, {
        "can_react": True,
        "reaction_used": player_ts.get("reaction_used", False),
        "attack_roll": result_obj.attack_roll.get("attack_total", 0) if result_obj else 0,
        "player_ac": p_derived_r.get("ac", 10),
        "incoming_damage": total_damage,
        "target_hp_before_damage": pending_reaction.get("target_hp_before_damage"),
        "target_temporary_hp_before_damage": pending_reaction.get("target_temporary_hp_before_damage"),
        "target_wild_shape_hp_before_damage": pending_reaction.get("target_wild_shape_hp_before_damage"),
        "attacker_name": actor_name,
        "attacker_id": actor_id,
        "reactor_character_id": str(player_check.id),
        "target_id": actor_id,
        "spell_slots": p_slots,
        "available_reactions": available_reactions,
        "options": [
            {
                "type": reaction["type"],
                "target_id": actor_id,
                "character_id": str(player_check.id),
                "label": f"{reaction['name']} - {reaction.get('effect', '')}".strip(" -"),
            }
            for reaction in available_reactions
        ],
    }


def build_counterspell_prompt(
    *,
    player_check,
    player_ts: dict,
    actor_id: str,
    actor_name: str,
    spell_name: str,
    spell_level: int,
    spell_target_id: str | None,
    decision: dict,
    decided_reason: str,
    combat=None,
    caster_conditions: list[str] | None = None,
):
    if not player_check:
        return False, False, None
    if player_ts.get("reaction_used"):
        return True, False, None
    if not can_take_reaction(player_check):
        return True, False, None
    if not character_knows_counterspell(player_check):
        return True, False, None

    slot_choice = choose_counterspell_slot(player_check.spell_slots or {}, spell_level)
    if not slot_choice:
        return True, False, None

    eligibility = resolve_counterspell_eligibility(
        reactor=player_check,
        caster_id=actor_id,
        combat=combat,
        caster_conditions=caster_conditions,
    )
    if not eligibility["can_counterspell"]:
        return True, False, None

    slot_key, slot_level = slot_choice
    declined = player_ts.get("resume_spell_reaction") or {}
    spell_target_key = str(spell_target_id) if spell_target_id is not None else None
    if (
        declined.get("trigger") == "spell_cast"
        and str(declined.get("caster_id")) == str(actor_id)
        and declined.get("spell_name") == spell_name
        and int(declined.get("spell_level") or 0) == int(spell_level or 0)
        and declined.get("spell_target_id") == spell_target_key
    ):
        return True, False, None

    pending_reaction = build_pending_spell_reaction(
        caster_id=actor_id,
        caster_name=actor_name,
        reactor_id=str(player_check.id),
        spell_name=spell_name,
        spell_level=spell_level,
        spell_target_id=spell_target_id,
        decision=decision,
        decided_reason=decided_reason,
    )
    player_ts["pending_spell_reaction"] = pending_reaction

    reaction = {
        "id": "counterspell",
        "name": "Counterspell",
        "type": "counterspell",
        "cost": f"{slot_key} spell slot",
        "slot_level": slot_key,
        "slot_level_number": slot_level,
        "slots_remaining": (player_check.spell_slots or {}).get(slot_key, 0),
        "effect": (
            f"Cancel {actor_name}'s {spell_name}"
            if spell_level <= slot_level
            else f"Attempt to cancel {actor_name}'s {spell_name} (DC {10 + int(spell_level or 0)})"
        ),
        "countered_spell": spell_name,
        "countered_spell_level": int(spell_level or 0),
    }
    return True, True, {
        "can_react": True,
        "reaction_used": player_ts.get("reaction_used", False),
        "trigger": "spell_cast",
        "context": f"{actor_name} is casting {spell_name}.",
        "attacker_name": actor_name,
        "attacker_id": actor_id,
        "caster_name": actor_name,
        "caster_id": actor_id,
        "spell_name": spell_name,
        "spell_level": int(spell_level or 0),
        "reactor_character_id": str(player_check.id),
        "target_id": actor_id,
        "spell_target_id": str(spell_target_id) if spell_target_id is not None else None,
        "range": eligibility,
        "spell_slots": player_check.spell_slots or {},
        "available_reactions": [reaction],
        "options": [{
            "type": "counterspell",
            "target_id": actor_id,
            "character_id": str(player_check.id),
            "label": f"{reaction['name']} - {reaction.get('effect', '')}".strip(" -"),
        }],
    }
