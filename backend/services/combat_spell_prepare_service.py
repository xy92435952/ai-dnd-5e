from dataclasses import dataclass
from typing import Any, Callable

from services.combat_action_rules_service import CombatActionRuleError, validate_can_take_action
from services.combat_pending_spell_service import build_pending_spell, store_pending_spell
from services.combat_spell_roll_service import (
    CombatSpellRollError,
    build_spell_ability_context,
    build_spell_roll_preview,
    spell_action_cost,
    validate_spell_turn_state,
)
from services.combat_spell_target_service import (
    collect_spell_target_ids,
    collect_spell_target_names,
    validate_spell_range,
)
from services.combat_temporary_hp_service import is_armor_of_agathys


@dataclass
class PreparedSpellRoll:
    turn_state: dict[str, Any]
    pending_spell: dict[str, Any]
    damage_dice: str | None
    heal_dice: str | None
    save_type: str | None
    spell_save_dc: int
    is_cantrip: bool
    is_aoe: bool
    targets: list[dict[str, Any]]
    is_concentration: bool


async def prepare_spell_roll(
    db,
    *,
    combat_obj,
    session,
    caster,
    caster_id: str,
    spell_name: str,
    spell_level: int,
    spell: dict[str, Any],
    target_id: str | None,
    target_ids: list[str] | None,
    enemies: list[dict[str, Any]],
    default_turn_state: dict[str, Any],
    get_turn_state: Callable[[Any, str], dict[str, Any]],
    consume_slot: Callable[[dict, int], tuple[dict, str | None]],
    calc_upcast_dice: Callable[[str, int], str | None],
) -> PreparedSpellRoll:
    try:
        validate_can_take_action(caster)
    except CombatActionRuleError as exc:
        raise CombatSpellRollError(exc.status_code, exc.detail) from exc

    is_cantrip = spell["level"] == 0
    action_cost = spell_action_cost(spell)
    spell_turn_state = get_turn_state(combat_obj, caster_id) if combat_obj else dict(default_turn_state)
    spell_turn_state = validate_spell_turn_state(
        spell_turn_state,
        is_cantrip=is_cantrip,
        action_cost=action_cost,
    )

    if not is_cantrip:
        current_slots = dict(caster.spell_slots or {})
        _, slot_error = consume_slot(dict(current_slots), spell_level)
        if slot_error:
            raise CombatSpellRollError(400, slot_error)

    is_aoe = spell.get("aoe", False)
    effective_target_id = target_id
    effective_target_ids = target_ids
    if is_armor_of_agathys(spell_name, spell) and not target_id and not target_ids:
        effective_target_id = caster_id

    raw_ids = collect_spell_target_ids(effective_target_id, effective_target_ids, enemies, is_aoe=is_aoe)
    target_names = await collect_spell_target_names(db, raw_ids, enemies, session=session)

    positions = dict(combat_obj.entity_positions or {}) if combat_obj else {}
    validate_spell_range(
        target_ids=raw_ids,
        positions=positions,
        caster_id=caster_id,
        spell_range_ft=spell.get("range", 0),
    )

    ability_context = build_spell_ability_context(caster.derived or {})
    preview = build_spell_roll_preview(
        spell_name=spell_name,
        spell_level=spell_level,
        spell=spell,
        calc_upcast_dice=calc_upcast_dice,
    )
    pending_spell = build_pending_spell(
        caster_id=caster_id,
        spell_name=spell_name,
        spell_level=spell_level,
        target_ids=raw_ids,
        is_cantrip=is_cantrip,
        is_aoe=is_aoe,
        spell_type=spell["type"],
        action_cost=action_cost,
    )

    if combat_obj:
        store_pending_spell(combat_obj, caster_id, spell_turn_state, pending_spell)

    return PreparedSpellRoll(
        turn_state=spell_turn_state,
        pending_spell=pending_spell,
        damage_dice=preview["damage_dice"],
        heal_dice=preview["heal_dice"],
        save_type=preview["save_type"],
        spell_save_dc=ability_context["spell_save_dc"],
        is_cantrip=is_cantrip,
        is_aoe=is_aoe,
        targets=[{"id": target_id, "name": name} for target_id, name in zip(raw_ids, target_names)],
        is_concentration=preview["is_concentration"],
    )
