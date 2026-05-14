from dataclasses import dataclass, field
from typing import Any, Callable

from sqlalchemy.orm.attributes import flag_modified

from models import GameLog
from services.combat_pending_spell_service import complete_pending_spell
from services.combat_service import CombatService
from services.combat_spell_application_service import apply_confirmed_spell_effects
from services.combat_spell_resolution_service import (
    build_spell_mechanical_narration,
    build_spell_resolution_context,
    choose_spell_narration_target,
    consume_spell_slot_for_confirmation,
)
from services.combat_wild_magic_service import (
    apply_wild_magic_mechanical_effect,
    resolve_wild_magic_for_spell,
)
from services.dnd_rules import _normalize_class, roll_dice, roll_wild_magic_surge
from services.spell_service import spell_service

svc = CombatService()


@dataclass
class ConfirmedSpellResult:
    narration: str
    mechanical_narration: str
    wild_magic_narration_append: str | None
    spell_target: str
    damage: int
    heal: int
    target_id: str | None
    target_new_hp: int | None
    aoe_results: list[dict[str, Any]]
    remaining_slots: dict[str, Any]
    dice_detail: dict[str, Any]
    turn_state: dict[str, Any]
    is_concentration: bool
    is_aoe: bool
    combat_over: bool
    outcome: str | None
    wild_magic_surge: dict[str, Any] | None
    wild_magic_check: dict[str, Any] | None
    log_dice_result: dict[str, Any]
    concentration_logs: list[Any] = field(default_factory=list)
    wild_magic_logs: list[GameLog] = field(default_factory=list)


async def confirm_pending_spell(
    db,
    *,
    session_id: str,
    combat_obj,
    caster,
    caster_entity_id: str,
    pending: dict[str, Any],
    spell: dict[str, Any],
    state: dict[str, Any],
    enemies: list[dict[str, Any]],
    damage_values: list[int] | None,
    session=None,
    spell_service_obj=spell_service,
    flag_modified_func: Callable[[Any, str], None] = flag_modified,
    roll_dice_func: Callable[[str], dict[str, Any]] = roll_dice,
    roll_wild_magic_surge_func: Callable[[], dict[str, Any]] = roll_wild_magic_surge,
    check_combat_outcome_func: Callable[..., Any] | None = None,
    complete_pending_spell_func: Callable[..., dict[str, Any]] = complete_pending_spell,
) -> ConfirmedSpellResult:
    spell_name = pending["spell_name"]
    spell_level = pending["spell_level"]
    target_ids = pending["target_ids"]
    is_cantrip = pending["is_cantrip"]
    is_aoe = pending["is_aoe"]
    spell_type = pending["spell_type"]

    new_slots = consume_spell_slot_for_confirmation(
        current_slots=caster.spell_slots,
        spell_level=spell_level,
        is_cantrip=is_cantrip,
        consume_slot=spell_service_obj.consume_slot,
    )
    caster.spell_slots = new_slots

    spell_context = build_spell_resolution_context(caster.derived)
    spell_application = await apply_confirmed_spell_effects(
        db,
        session_id=session_id,
        enemies=enemies,
        target_ids=target_ids,
        is_aoe=is_aoe,
        spell_type=spell_type,
        spell_name=spell_name,
        spell_level=spell_level,
        spell_mod=spell_context["spell_mod"],
        bonus_healing=spell_context["bonus_healing"],
        spell=spell,
        damage_values=damage_values,
        spell_save_dc=spell_context["spell_save_dc"],
        resolve_damage=spell_service_obj.resolve_damage,
        resolve_heal=spell_service_obj.resolve_heal,
    )
    if spell_application.enemies_changed:
        state["enemies"] = enemies
        if session is not None:
            session.game_state = dict(state)
            flag_modified_func(session, "game_state")

    if spell.get("concentration"):
        caster.concentration = spell_name

    mechanical_narration = build_spell_mechanical_narration(
        caster_name=caster.name,
        spell_name=spell_name,
        spell_level=spell_level,
        is_cantrip=is_cantrip,
        is_aoe=is_aoe,
        aoe_results=spell_application.aoe_results,
        result_damage=spell_application.result_damage,
        result_heal=spell_application.result_heal,
        spell_type=spell_type,
        save_detail=spell_application.save_detail,
        condition_name=spell_application.condition_name,
    )
    spell_target = choose_spell_narration_target(
        is_aoe=is_aoe,
        aoe_results=spell_application.aoe_results,
        target_ids=target_ids,
    )

    turn_state = complete_pending_spell_func(combat_obj, caster_entity_id, is_cantrip=is_cantrip)

    wild_magic = resolve_wild_magic_for_spell(
        caster_name=caster.name,
        is_cantrip=is_cantrip,
        derived=caster.derived,
        class_resources=caster.class_resources,
        roll_dice=roll_dice_func,
        roll_wild_magic_surge=roll_wild_magic_surge_func,
    )
    if wild_magic.updated_class_resources is not None:
        caster.class_resources = wild_magic.updated_class_resources

    wild_magic_logs: list[GameLog] = []
    if wild_magic.log_content:
        log_kwargs = {
            "session_id": session_id,
            "role": "system",
            "content": wild_magic.log_content,
            "log_type": "system",
        }
        if wild_magic.log_dice_result:
            log_kwargs["dice_result"] = wild_magic.log_dice_result
        wild_magic_logs.append(GameLog(**log_kwargs))
    apply_wild_magic_mechanical_effect(
        caster=caster,
        surge=wild_magic.surge,
        roll_dice=roll_dice_func,
    )

    combat_over = False
    outcome = None
    if check_combat_outcome_func is not None and session is not None:
        combat_over, outcome = await check_combat_outcome_func(
            db,
            session=session,
            session_id=session_id,
            enemies=enemies,
            check_combat_over=svc.check_combat_over,
        )
    elif check_combat_outcome_func is not None:
        maybe_result = check_combat_outcome_func()
        combat_over, outcome = await maybe_result if hasattr(maybe_result, "__await__") else maybe_result

    return ConfirmedSpellResult(
        narration=mechanical_narration,
        mechanical_narration=mechanical_narration,
        wild_magic_narration_append=wild_magic.narration_append,
        spell_target=spell_target if isinstance(spell_target, str) else str(spell_target),
        damage=spell_application.result_damage,
        heal=spell_application.result_heal,
        target_id=target_ids[0] if target_ids else None,
        target_new_hp=spell_application.target_new_hp,
        aoe_results=spell_application.aoe_results,
        remaining_slots=new_slots,
        dice_detail=spell_application.dice_detail,
        turn_state=turn_state,
        is_concentration=spell.get("concentration", False),
        is_aoe=is_aoe,
        combat_over=combat_over,
        outcome=outcome,
        wild_magic_surge=wild_magic.surge,
        wild_magic_check=wild_magic.check,
        log_dice_result={
            "dice": spell_application.dice_detail,
            "damage": spell_application.result_damage,
            "heal": spell_application.result_heal,
            "aoe": spell_application.aoe_results,
        },
        concentration_logs=spell_application.concentration_logs,
        wild_magic_logs=wild_magic_logs,
    )


def spell_actor_class(caster) -> str:
    return _normalize_class(caster.char_class)
