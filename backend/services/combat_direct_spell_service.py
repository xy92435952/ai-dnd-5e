from dataclasses import dataclass, field
from typing import Any, Callable

from sqlalchemy.orm.attributes import flag_modified

from services.character_roster import CharacterRoster
from services.combat_outcome_service import check_and_cleanup_combat_outcome
from services.combat_service import CombatService
from services.combat_spell_application_service import apply_confirmed_spell_effects
from services.combat_spell_resolution_service import (
    CombatSpellResolutionError,
    build_spell_mechanical_narration,
    build_spell_resolution_context,
    consume_spell_slot_for_confirmation,
)
from services.combat_spell_target_service import collect_spell_target_names, validate_ordinary_healing_targets
from services.combat_turn_state_service import DEFAULT_TURN_STATE, get_turn_state, save_turn_state
from services.spell_service import spell_service

svc = CombatService()


@dataclass
class CombatDirectSpellError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


@dataclass
class DirectSpellResult:
    narration: str
    damage: int
    heal: int
    target_id: str | None
    target_new_hp: int | None
    aoe_results: list[dict[str, Any]]
    remaining_slots: dict[str, Any]
    dice_detail: dict[str, Any]
    turn_state: dict[str, Any]
    next_turn_index: int
    round_number: int
    is_concentration: bool
    is_aoe: bool
    combat_over: bool
    outcome: str | None
    concentration_logs: list[Any] = field(default_factory=list)

    @property
    def log_dice_result(self) -> dict[str, Any]:
        return {
            "dice": self.dice_detail,
            "damage": self.damage,
            "heal": self.heal,
            "aoe": self.aoe_results,
        }

    def to_response(self) -> dict[str, Any]:
        return {
            "narration": self.narration,
            "damage": self.damage,
            "heal": self.heal,
            "target_id": self.target_id,
            "target_new_hp": self.target_new_hp,
            "aoe_results": self.aoe_results,
            "remaining_slots": self.remaining_slots,
            "dice_detail": self.dice_detail,
            "dice_result": {"total": self.damage or self.heal or 0},
            "turn_state": self.turn_state,
            "next_turn_index": self.next_turn_index,
            "round_number": self.round_number,
            "is_concentration": self.is_concentration,
            "is_aoe": self.is_aoe,
            "combat_over": self.combat_over,
            "outcome": self.outcome,
        }


async def cast_direct_spell(
    db,
    *,
    session_id: str,
    session,
    combat_obj,
    caster,
    caster_id: str,
    spell_name: str,
    spell_level: int,
    target_id: str | None,
    target_ids: list[str] | None,
    spell_service_obj=spell_service,
    flag_modified_func: Callable[[Any, str], None] = flag_modified,
    save_turn_state_func: Callable[[Any, str, dict[str, Any]], None] = save_turn_state,
    check_combat_outcome_func: Callable[..., Any] | None = check_and_cleanup_combat_outcome,
) -> DirectSpellResult:
    spell = spell_service_obj.get(spell_name)
    if not spell:
        raise CombatDirectSpellError(400, f"未知法术：{spell_name}")

    slot_error = spell_service_obj.validate_slot_level(spell_name, spell_level)
    if slot_error:
        raise CombatDirectSpellError(400, slot_error)

    spell_turn_state = get_turn_state(combat_obj, caster_id) if combat_obj else dict(DEFAULT_TURN_STATE)
    is_cantrip = spell["level"] == 0
    if spell_turn_state.get("action_used") and not is_cantrip:
        raise CombatDirectSpellError(400, "本回合行动已用尽")

    spell_context = build_spell_resolution_context(caster.derived)
    state = session.game_state or {}
    enemies = list(state.get("enemies", []))
    is_aoe = spell.get("aoe", False)
    spell_type = spell.get("type")
    resolved_target_ids = _resolve_direct_spell_targets(
        db=db,
        session=session,
        enemies=enemies,
        is_aoe=is_aoe,
        spell_type=spell_type,
        target_id=target_id,
        target_ids=target_ids,
    )
    await collect_spell_target_names(db, resolved_target_ids, enemies, session=session)
    if spell_type == "heal":
        await validate_ordinary_healing_targets(db, resolved_target_ids, enemies, session=session)

    try:
        new_slots = consume_spell_slot_for_confirmation(
            current_slots=caster.spell_slots,
            spell_level=spell_level,
            is_cantrip=is_cantrip,
            consume_slot=spell_service_obj.consume_slot,
        )
    except CombatSpellResolutionError as exc:
        raise CombatDirectSpellError(exc.status_code, exc.detail) from exc
    caster.spell_slots = new_slots

    result_damage = 0
    result_heal = 0
    dice_detail: dict[str, Any] = {}
    target_new_hp = None
    aoe_results: list[dict[str, Any]] = []
    concentration_logs: list[Any] = []

    if spell_type in ("damage", "heal") and (resolved_target_ids or is_aoe):
        spell_application = await apply_confirmed_spell_effects(
            db,
            session_id=session_id,
            enemies=enemies,
            target_ids=resolved_target_ids,
            is_aoe=is_aoe,
            spell_type=spell_type,
            spell_name=spell_name,
            spell_level=spell_level,
            spell_mod=spell_context["spell_mod"],
            bonus_healing=spell_context["bonus_healing"],
            spell=spell,
            damage_values=None,
            spell_save_dc=spell_context["spell_save_dc"],
            resolve_damage=spell_service_obj.resolve_damage,
            resolve_heal=spell_service_obj.resolve_heal,
        )
        result_damage = spell_application.result_damage
        result_heal = spell_application.result_heal
        dice_detail = spell_application.dice_detail
        target_new_hp = spell_application.target_new_hp
        aoe_results = spell_application.aoe_results
        concentration_logs = spell_application.concentration_logs
        if spell_application.enemies_changed:
            state["enemies"] = enemies
            session.game_state = dict(state)
            flag_modified_func(session, "game_state")

    if spell.get("concentration"):
        caster.concentration = spell_name

    narration = build_spell_mechanical_narration(
        caster_name=caster.name,
        spell_name=spell_name,
        spell_level=spell_level,
        is_cantrip=is_cantrip,
        is_aoe=is_aoe,
        aoe_results=aoe_results,
        result_damage=result_damage,
        result_heal=result_heal,
        spell_type=spell_type,
        save_detail=None,
        condition_name=None,
    )

    if combat_obj:
        if not is_cantrip:
            spell_turn_state["action_used"] = True
        save_turn_state_func(combat_obj, caster_id, spell_turn_state)

    combat_over, outcome = await _maybe_check_combat_outcome(
        db,
        session=session,
        session_id=session_id,
        enemies=enemies,
        check_combat_outcome_func=check_combat_outcome_func,
    )

    return DirectSpellResult(
        narration=narration,
        damage=result_damage,
        heal=result_heal,
        target_id=target_id,
        target_new_hp=target_new_hp,
        aoe_results=aoe_results,
        remaining_slots=new_slots,
        dice_detail=dice_detail,
        turn_state=spell_turn_state,
        next_turn_index=combat_obj.current_turn_index if combat_obj else 0,
        round_number=combat_obj.round_number if combat_obj else 1,
        is_concentration=spell.get("concentration", False),
        is_aoe=is_aoe,
        combat_over=combat_over,
        outcome=outcome,
        concentration_logs=concentration_logs,
    )


def _resolve_direct_spell_targets(
    *,
    db,
    session,
    enemies: list[dict[str, Any]],
    is_aoe: bool,
    spell_type: str | None,
    target_id: str | None,
    target_ids: list[str] | None,
) -> list[str]:
    if is_aoe and spell_type == "damage":
        raw_ids = target_ids if target_ids is not None else ([target_id] if target_id else [])
        return list(raw_ids) if raw_ids else [
            enemy["id"] for enemy in enemies if enemy.get("hp_current", 0) > 0
        ]

    if is_aoe and spell_type == "heal":
        if target_ids:
            return list(target_ids)
        roster = CharacterRoster(db, session)
        return [session.player_character_id] + roster.companion_ids()

    if spell_type in ("damage", "heal") and (target_id or target_ids):
        resolved = target_id or (target_ids[0] if target_ids else None)
        return [resolved] if resolved else []

    return []


async def _maybe_check_combat_outcome(
    db,
    *,
    session,
    session_id: str,
    enemies: list[dict[str, Any]],
    check_combat_outcome_func: Callable[..., Any] | None,
) -> tuple[bool, str | None]:
    if check_combat_outcome_func is None:
        return False, None

    result = check_combat_outcome_func(
        db,
        session=session,
        session_id=session_id,
        enemies=enemies,
        check_combat_over=svc.check_combat_over,
    )
    return await result if hasattr(result, "__await__") else result
