"""
services.combat_attack_damage_service — helpers for the two-step damage-roll endpoint.
"""
from dataclasses import dataclass
from typing import Any, Callable

from models import Character
from services.character_roster import CharacterRoster
from services.combat_concentration_service import do_concentration_check
from services.combat_concentration_effect_service import clear_concentration_effects_for_caster
from services.combat_damage_bonus_service import (
    DamageExtraResult,
    PendingDamageRoll,
    apply_basic_damage_bonuses,
    apply_divine_fury,
    apply_sneak_attack,
    apply_target_resistance,
    resolve_damage_extras,
    roll_pending_damage,
)
from services.combat_service import CombatService
from services.combat_temporary_hp_service import (
    apply_armor_of_agathys_retaliation_to_character,
    apply_armor_of_agathys_retaliation_to_enemy,
    build_character_target_state,
    get_armor_of_agathys_retaliation_damage,
)
from services.combat_turn_state_service import get_turn_state
from services.dnd_rules import _normalize_class, apply_character_damage
from services.session_access_service import assert_character_in_session

svc = CombatService()


@dataclass(frozen=True)
class AttackDamageResolution:
    player_derived: dict[str, Any]
    player_class: str
    player_level: int
    target_id: str
    target_name: str
    target_is_enemy: bool
    is_crit: bool
    dmg_mod: int
    attack_roll_result: dict[str, Any]
    damage_dice_expr: str
    damage_roll_result: dict[str, Any]
    damage_rolls: list[int]
    crit_extra: int
    damage_type: str
    total_damage: int
    extra_damage_notes: list[str]
    sneak_attack_applied: bool
    sneak_attack_damage: int
    sneak_attack_dice: str
    dueling_bonus: int
    rage_bonus: int
    feat_power_bonus_dmg: int
    damage_before_resistance: int
    damage_after_resistance: int
    resistance_applied: bool
    resistance_sources: tuple[str, ...]


def find_pending_attack(turn_states: dict[str, Any], pending_attack_id: str):
    """Find a pending attack by id across all entity turn states."""
    for entity_id, entity_ts in (turn_states or {}).items():
        pending = entity_ts.get("pending_attack")
        if pending and pending.get("pending_attack_id") == pending_attack_id:
            return entity_id, pending
    return None, None


async def resolve_pending_attack_damage(
    db,
    *,
    session,
    combat,
    player,
    attacker_entity_id: str,
    pending: dict[str, Any],
    enemies: list[dict[str, Any]],
    damage_values: list[int] | None,
    has_ally_adjacent_to: Callable[[str, str, list[dict[str, Any]], dict[str, Any]], bool],
) -> AttackDamageResolution:
    player_derived = player.derived or {}
    player_class = _normalize_class(player.char_class)
    player_level = player.level

    target_id = pending["target_id"]
    target_name = pending["target_name"]
    target_is_enemy = pending["target_is_enemy"]
    target_conditions = list(pending.get("target_conditions", []))
    is_crit = pending["is_crit"]
    is_ranged = pending["is_ranged"]
    hit_die = pending["hit_die"]
    dmg_mod = pending["dmg_mod"]
    attack_roll_result = pending["attack_roll"]

    pending_damage = roll_pending_damage(
        hit_die=hit_die,
        dmg_mod=dmg_mod,
        is_crit=is_crit,
        damage_values=damage_values,
    )

    damage, extra_damage_notes, dueling_bonus, rage_bonus, feat_power_bonus_dmg = apply_basic_damage_bonuses(
        base_damage=pending_damage.damage,
        pending=pending,
        attacker_derived=player_derived,
        level=player_level,
        is_ranged=is_ranged,
        get_rage_bonus=svc.get_rage_bonus,
    )
    defender_interception = pending.get("defender_interception")
    if defender_interception:
        extra_damage_notes.append(f"{defender_interception['defender_name']}护卫干扰")

    subclass_effects = player_derived.get("subclass_effects", {})
    turn_state = get_turn_state(combat, attacker_entity_id)
    ally_list = []
    if player_class == "Rogue":
        positions = dict(combat.entity_positions or {})
        roster = CharacterRoster(db, session)
        ally_list = [{"id": session.player_character_id, "hp_current": player.hp_current}]
        for companion in await roster.companions():
            ally_list.append({"id": companion.id, "hp_current": companion.hp_current})
    else:
        positions = {}

    damage_type = player_derived.get("damage_type", "钝击")
    damage_extras = resolve_damage_extras(
        damage=damage,
        extra_damage_notes=extra_damage_notes,
        pending=pending,
        attacker_class=player_class,
        level=player_level,
        subclass_effects=subclass_effects,
        turn_state=turn_state,
        target_id=target_id,
        attacker_id=attacker_entity_id,
        target_is_enemy=target_is_enemy,
        ally_list=ally_list,
        enemies=enemies,
        positions=positions,
        damage_type=damage_type,
        is_ranged=is_ranged,
        attacker=player,
        attacker_concentration=getattr(player, "concentration", None),
        target_conditions=target_conditions,
        has_ally_adjacent_to=has_ally_adjacent_to,
        check_sneak_attack=svc.check_sneak_attack,
        calc_sneak_attack_dice=svc.calc_sneak_attack_dice,
        apply_damage_with_resistance=svc.apply_damage_with_resistance,
    )

    return AttackDamageResolution(
        player_derived=player_derived,
        player_class=player_class,
        player_level=player_level,
        target_id=target_id,
        target_name=target_name,
        target_is_enemy=target_is_enemy,
        is_crit=is_crit,
        dmg_mod=dmg_mod,
        attack_roll_result=attack_roll_result,
        damage_dice_expr=pending_damage.damage_dice_expr,
        damage_roll_result=pending_damage.damage_roll_result,
        damage_rolls=pending_damage.damage_rolls,
        crit_extra=pending_damage.crit_extra,
        damage_type=damage_type,
        total_damage=damage_extras.damage,
        extra_damage_notes=damage_extras.extra_damage_notes,
        sneak_attack_applied=damage_extras.sneak_attack_applied,
        sneak_attack_damage=damage_extras.sneak_attack_damage,
        sneak_attack_dice=damage_extras.sneak_attack_dice,
        dueling_bonus=dueling_bonus,
        rage_bonus=rage_bonus,
        feat_power_bonus_dmg=feat_power_bonus_dmg,
        damage_before_resistance=(
            damage_extras.damage_before_resistance
            if damage_extras.damage_before_resistance is not None
            else damage
        ),
        damage_after_resistance=(
            damage_extras.damage_after_resistance
            if damage_extras.damage_after_resistance is not None
            else damage_extras.damage
        ),
        resistance_applied=damage_extras.resistance_applied,
        resistance_sources=damage_extras.resistance_sources,
    )

async def apply_attack_damage_to_target(
    db,
    *,
    session_id: str,
    enemies: list[dict[str, Any]],
    target_id: str,
    target_is_enemy: bool,
    damage: int,
    session=None,
    is_critical: bool = False,
    attacker_id: str | None = None,
    attacker_is_enemy: bool = False,
    is_melee: bool = True,
):
    """Apply final weapon damage to an enemy dict or Character."""
    if target_is_enemy:
        target_new_hp = None
        target_state = None
        for enemy in enemies:
            if enemy.get("id") == target_id:
                enemy["hp_current"] = svc.apply_damage(
                    enemy.get("hp_current", 0),
                    damage,
                    enemy.get("derived", {}).get("hp_max", 10),
                )
                target_new_hp = enemy["hp_current"]
                target_state = {
                    "target_id": target_id,
                    "hp_current": target_new_hp,
                    "new_hp": target_new_hp,
                    "conditions": enemy.get("conditions", []),
                    "life_state": "dead" if target_new_hp <= 0 else "alive",
                }
        return target_new_hp, None, target_state

    target_character = await db.get(Character, target_id)
    if not target_character:
        return None, None, None
    if session is not None:
        await assert_character_in_session(target_character, session, db)

    armor_retaliation_damage = (
        get_armor_of_agathys_retaliation_damage(target_character)
        if is_melee
        else 0
    )
    damage_result = apply_character_damage(target_character, damage, is_critical=is_critical)
    concentration_log = await do_concentration_check(target_character, damage, session_id)
    if (
        session is not None
        and concentration_log
        and concentration_log.dice_result
        and concentration_log.dice_result.get("broke")
    ):
        await clear_concentration_effects_for_caster(
            db,
            session,
            target_character.id,
            spell_name=concentration_log.dice_result.get("spell_name"),
        )
    target_state = build_character_target_state(target_character)
    temporary_hp_involved = (
        damage_result["temporary_hp_before"]
        or damage_result["temporary_hp_after"]
        or damage_result["damage_to_temporary_hp"]
    )
    wild_shape_hp_involved = (
        damage_result["wild_shape_hp_before"]
        or damage_result["wild_shape_hp_after"]
        or damage_result["damage_to_wild_shape_hp"]
    )
    if temporary_hp_involved or wild_shape_hp_involved:
        if temporary_hp_involved:
            target_state["temporary_hp"] = damage_result["temporary_hp_after"]
        if wild_shape_hp_involved:
            target_state["wild_shape_hp"] = damage_result["wild_shape_hp_after"]
        target_state["class_resources"] = target_character.class_resources or {}
        target_state["condition_durations"] = target_character.condition_durations or {}
        damage_summary = {
            "damage": damage_result["damage"],
            "damage_to_temporary_hp": damage_result["damage_to_temporary_hp"],
            "damage_to_hp": damage_result["damage_to_hp"],
            "temporary_hp_before": damage_result["temporary_hp_before"],
            "temporary_hp_after": damage_result["temporary_hp_after"],
        }
        if wild_shape_hp_involved:
            damage_summary.update({
                "damage_to_wild_shape_hp": damage_result["damage_to_wild_shape_hp"],
                "wild_shape_hp_before": damage_result["wild_shape_hp_before"],
                "wild_shape_hp_after": damage_result["wild_shape_hp_after"],
            })
        target_state["damage_result"] = damage_summary

    retaliation = None
    if is_melee:
        if attacker_is_enemy:
            attacker_enemy = next((enemy for enemy in enemies if enemy.get("id") == attacker_id), None)
            retaliation = apply_armor_of_agathys_retaliation_to_enemy(
                defender=target_character,
                attacker_enemy=attacker_enemy,
                enemies=enemies,
                melee_hit=True,
                retaliation_damage=armor_retaliation_damage,
            )
        else:
            retaliation = await apply_armor_of_agathys_retaliation_to_character(
                db,
                defender=target_character,
                attacker_character_id=attacker_id,
                melee_hit=True,
                retaliation_damage=armor_retaliation_damage,
            )
    if retaliation:
        target_state["retaliation"] = retaliation

    return damage_result["hp_after"], concentration_log, target_state
