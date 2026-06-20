from dataclasses import dataclass
from typing import Any, Callable

from services.combat_action_rules_service import CombatActionRuleError, validate_can_take_action
from services.combat_charmed_service import (
    CHARMED_HARMFUL_SPELL_ERROR,
    charmed_harmful_spell_target_id,
)
from services.combat_pending_spell_service import build_pending_spell, store_pending_spell
from services.combat_spell_roll_service import (
    CombatSpellRollError,
    build_spell_ability_context,
    build_spell_roll_preview,
    spell_attack_is_ranged,
    spell_action_cost,
    spell_requires_attack_roll,
    validate_spell_turn_state,
)
from services.combat_spell_target_service import (
    collect_spell_target_ids,
    collect_spell_target_names,
    validate_spell_range,
)
from services.combat_temporary_hp_service import is_armor_of_agathys
from services.dnd_rules import roll_attack
from services.magic_initiate_spell_service import magic_initiate_spell_resource


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
    attack_roll_result: dict[str, Any] | None = None
    spell_attack_required: bool = False


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
    aoe_center: dict[str, Any] | None = None,
    enemies: list[dict[str, Any]],
    d20_value: int | None = None,
    second_d20_value: int | None = None,
    default_turn_state: dict[str, Any],
    get_turn_state: Callable[[Any, str], dict[str, Any]],
    consume_slot: Callable[[dict, int], tuple[dict, str | None]],
    calc_upcast_dice: Callable[[str, int], str | None],
    skip_turn_state_validation: bool = False,
    skip_slot_validation: bool = False,
    store_pending_spell_result: bool = True,
) -> PreparedSpellRoll:
    try:
        validate_can_take_action(caster)
    except CombatActionRuleError as exc:
        raise CombatSpellRollError(exc.status_code, exc.detail) from exc

    is_cantrip = spell["level"] == 0
    action_cost = spell_action_cost(spell)
    spell_turn_state = get_turn_state(combat_obj, caster_id) if combat_obj else dict(default_turn_state)
    if not skip_turn_state_validation:
        spell_turn_state = validate_spell_turn_state(
            spell_turn_state,
            is_cantrip=is_cantrip,
            action_cost=action_cost,
        )

    magic_initiate_resource = None
    use_magic_initiate_resource = False
    if not is_cantrip and not skip_slot_validation:
        magic_initiate_resource = magic_initiate_spell_resource(
            caster,
            spell_name=spell_name,
            spell=spell,
            spell_level=spell_level,
        )
        use_magic_initiate_resource = bool(
            magic_initiate_resource
            and magic_initiate_resource.get("uses_remaining", 0) > 0
        )

    if not is_cantrip and not skip_slot_validation and not use_magic_initiate_resource:
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
    if spell.get("type") == "damage" and not is_aoe and not raw_ids:
        raise CombatSpellRollError(400, "请选择一个法术目标")
    blocked_charmer_id = charmed_harmful_spell_target_id(
        getattr(caster, "conditions", None) or [],
        getattr(caster, "condition_durations", None) or {},
        spell_name=spell_name,
        spell=spell,
        target_ids=raw_ids,
    )
    if blocked_charmer_id:
        raise CombatSpellRollError(400, CHARMED_HARMFUL_SPELL_ERROR)
    target_names = await collect_spell_target_names(db, raw_ids, enemies, session=session)

    positions = dict(combat_obj.entity_positions or {}) if combat_obj else {}
    validate_spell_range(
        target_ids=raw_ids,
        positions=positions,
        caster_id=caster_id,
        spell_range_ft=spell.get("range", 0),
    )

    ability_context = build_spell_ability_context(caster.derived or {})
    spell_attack_required = (
        bool(raw_ids)
        and not is_aoe
        and spell_requires_attack_roll(spell_name, spell)
    )
    attack_roll_result = None
    if spell_attack_required:
        target = await _resolve_spell_attack_target(db, raw_ids[0], enemies, session=session)
        if target is None:
            raise CombatSpellRollError(400, "Target does not exist")

        target_conditions = list(target.get("conditions") or [])
        target_turn_state = get_turn_state(combat_obj, raw_ids[0]) if combat_obj else {}
        if target_turn_state.get("dodging") and "dodging" not in target_conditions:
            target_conditions.append("dodging")

        attacker_advantage_sources, attacker_disadvantage_sources = _spell_attack_modifier_sources(
            caster.conditions or [],
            caster,
        )
        defense_advantage_sources, defense_disadvantage_sources = _spell_defense_modifier_sources(
            target_conditions,
        )
        attacker_advantage = bool(attacker_advantage_sources)
        attacker_disadvantage = bool(attacker_disadvantage_sources)
        defense_advantage = bool(defense_advantage_sources)
        defense_disadvantage = bool(defense_disadvantage_sources)
        is_ranged_spell_attack = spell_attack_is_ranged(spell)
        positions = dict(combat_obj.entity_positions or {}) if combat_obj else {}
        cover_bonus = 0
        if is_ranged_spell_attack and combat_obj:
            cover_bonus = _calculate_spell_cover_bonus(
                grid_data=dict(combat_obj.grid_data or {}),
                positions=positions,
                caster_id=caster_id,
                target_id=raw_ids[0],
            )
        target_derived = dict(target.get("derived") or {})
        if "ac" not in target_derived and target.get("ac") is not None:
            target_derived["ac"] = target.get("ac")
        if cover_bonus:
            target_derived["ac"] = target_derived.get("ac", target.get("ac", 10)) + cover_bonus

        spell_attack_bonus = ability_context.get("spell_attack_bonus", 0)
        attack_roll_result = roll_attack(
            attacker={
                "derived": {
                    "attack_bonus": spell_attack_bonus,
                    "ranged_attack_bonus": spell_attack_bonus,
                    "crit_threshold": (caster.derived or {}).get("crit_threshold", 20),
                },
                "conditions": list(caster.conditions or []),
            },
            target={"derived": target_derived},
            is_ranged=is_ranged_spell_attack,
            advantage=attacker_advantage or defense_advantage,
            disadvantage=attacker_disadvantage or defense_disadvantage,
            crit_threshold=(caster.derived or {}).get("crit_threshold", 20),
        )
        if d20_value is not None:
            attack_roll_result = _apply_frontend_spell_attack_d20(
                attack_roll_result,
                d20_value=d20_value,
                second_d20_value=second_d20_value,
                advantage=attacker_advantage or defense_advantage,
                disadvantage=attacker_disadvantage or defense_disadvantage,
                crit_threshold=(caster.derived or {}).get("crit_threshold", 20),
            )
        attack_roll_result.update({
            "spell_attack": True,
            "cover_bonus": cover_bonus,
            "advantage": attacker_advantage or defense_advantage,
            "disadvantage": attacker_disadvantage or defense_disadvantage,
            "advantage_sources": [
                *attacker_advantage_sources,
                *defense_advantage_sources,
            ],
            "disadvantage_sources": [
                *attacker_disadvantage_sources,
                *defense_disadvantage_sources,
            ],
        })

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
        aoe_center=aoe_center,
        spell_type=spell["type"],
        action_cost=action_cost,
        attack_roll=attack_roll_result,
        resource_source=(
            magic_initiate_resource.get("resource_source")
            if use_magic_initiate_resource and magic_initiate_resource
            else None
        ),
        resource_key=(
            magic_initiate_resource.get("resource_key")
            if use_magic_initiate_resource and magic_initiate_resource
            else None
        ),
    )

    if combat_obj and store_pending_spell_result:
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
        attack_roll_result=attack_roll_result,
        spell_attack_required=spell_attack_required,
    )


def _apply_frontend_spell_attack_d20(
    attack_roll_result: dict[str, Any],
    *,
    d20_value: int,
    second_d20_value: int | None,
    advantage: bool,
    disadvantage: bool,
    crit_threshold: int,
) -> dict[str, Any]:
    d20 = int(d20_value)
    other_roll = None
    selection = "single"
    if second_d20_value is not None and bool(advantage) != bool(disadvantage):
        second = int(second_d20_value)
        if advantage:
            selected = max(d20, second)
            other_roll = min(d20, second)
            selection = "advantage"
        else:
            selected = min(d20, second)
            other_roll = max(d20, second)
            selection = "disadvantage"
        d20 = selected

    attack_total = (
        d20
        + int(attack_roll_result["attack_bonus"])
        + int(attack_roll_result.get("condition_modifier", 0) or 0)
    )
    is_crit = d20 >= int(crit_threshold or 20)
    is_fumble = d20 == 1
    updated = {
        **attack_roll_result,
        "d20": d20,
        "attack_total": attack_total,
        "hit": (not is_fumble) and (is_crit or attack_total >= attack_roll_result["target_ac"]),
        "is_crit": is_crit,
        "is_fumble": is_fumble,
    }
    if second_d20_value is not None and bool(advantage) != bool(disadvantage):
        updated.update({
            "d20_rolls": [int(d20_value), int(second_d20_value)],
            "selected_d20": d20,
            "other_roll": other_roll,
            "d20_selection": selection,
            "roll_state": selection,
        })
    return updated


async def _resolve_spell_attack_target(db, target_id: str, enemies: list[dict[str, Any]], *, session=None):
    from models import Character
    from services.session_access_service import assert_character_in_session

    enemy = next((item for item in enemies if item.get("id") == target_id), None)
    if enemy:
        return enemy

    target_character = await db.get(Character, target_id)
    if target_character:
        if session is not None:
            await assert_character_in_session(target_character, session, db)
        return {
            "id": target_character.id,
            "name": target_character.name,
            "derived": target_character.derived or {},
            "conditions": target_character.conditions or [],
        }
    return None


def _spell_attack_modifier_sources(conditions: list[str], caster) -> tuple[list[str], list[str]]:
    from services.combat_condition_service import get_attack_modifier_sources

    return get_attack_modifier_sources(conditions, caster)


def _spell_defense_modifier_sources(conditions: list[str]) -> tuple[list[str], list[str]]:
    from services.combat_condition_service import get_defense_modifier_sources

    return get_defense_modifier_sources(conditions)


def _calculate_spell_cover_bonus(*, grid_data: dict, positions: dict, caster_id: str, target_id: str) -> int:
    from services.combat_service import CombatService

    caster_position = positions.get(str(caster_id))
    target_position = positions.get(str(target_id))
    if not caster_position or not target_position:
        return 0
    return CombatService.get_cover_bonus(grid_data, caster_position, target_position)
