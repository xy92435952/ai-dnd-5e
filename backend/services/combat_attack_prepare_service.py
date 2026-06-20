from dataclasses import dataclass
from typing import Any, Callable
from uuid import uuid4

from services.combat_attack_modifier_service import (
    apply_ranged_close_penalty,
    build_attack_deriveds,
    build_weapon_damage_dice,
    calculate_cover_bonus,
    choose_feat_power_attack,
    WeaponDamageDice,
)
from services.combat_action_rules_service import CombatActionRuleError, validate_can_take_action
from services.combat_ammunition_service import consume_attack_weapon_resource
from services.combat_attack_roll_service import (
    CombatAttackRollError,
    apply_d20_override,
    build_pending_attack,
    consume_attack_turn_state,
    validate_attack_turn_state,
)
from services.combat_charmed_service import CHARMED_ATTACK_ERROR, is_charmed_by_target
from services.combat_condition_service import (
    get_attack_modifier_sources,
    get_defense_modifier_sources,
)
from services.combat_attack_targeting_service import get_target_conditions, resolve_attack_target
from services.combat_defender_reaction_service import apply_defender_interception
from services.combat_grid_service import check_attack_range
from services.combat_guiding_bolt_service import consume_guiding_bolt_condition
from services.combat_monk_martial_arts_service import (
    build_martial_arts_attack_derived,
    build_martial_arts_damage_dice,
    is_martial_arts_attack,
)
from services.combat_service import CombatService
from services.combat_turn_state_service import (
    get_turn_state,
    record_mobile_opportunity_safe_target,
    save_turn_state,
)
from services.combat_two_weapon_service import validate_two_weapon_fighting_equipment
from services.bardic_inspiration_service import (
    BardicInspirationError,
    apply_bardic_inspiration_to_attack_roll,
    spend_bardic_inspiration,
)
from services.dnd_rules import _normalize_class, roll_attack, should_auto_crit_melee_target
from services.lucky_feat_service import (
    LuckyFeatError,
    apply_lucky_to_attack_roll,
    spend_lucky_point,
)

svc = CombatService()


@dataclass
class PreparedAttackRoll:
    attacker_name: str
    attacker_class: str
    target_name: str
    attack_roll_result: dict[str, Any]
    cover_bonus: int
    advantage: bool
    disadvantage: bool
    advantage_sources: list[str]
    disadvantage_sources: list[str]
    roll_state: str
    damage_dice: str
    pending_attack_id: str
    pending_attack: dict[str, Any]
    weapon_resource: dict[str, Any] | None
    turn_state: dict[str, Any]
    attacks_max: int
    defender_interception: dict[str, Any] | None


async def prepare_attack_roll(
    db,
    *,
    combat,
    session,
    player,
    player_id: str,
    target_id: str,
    action_type: str,
    is_offhand: bool,
    d20_value: int | None,
    second_d20_value: int | None = None,
    use_lucky: bool = False,
    lucky_d20_value: int | None = None,
    use_bardic_inspiration: bool = False,
    bardic_inspiration_roll: int | None = None,
    enemies: list[dict[str, Any]],
    weapon_name: str | None = None,
    combat_service: CombatService = svc,
    roll_attack_func: Callable[..., dict[str, Any]] = roll_attack,
    get_turn_state_func: Callable[[Any, str], dict[str, Any]] = get_turn_state,
    save_turn_state_func: Callable[[Any, str, dict[str, Any]], None] = save_turn_state,
    check_attack_range_func: Callable[..., tuple[bool, int, str | None]] = check_attack_range,
) -> PreparedAttackRoll:
    """Prepare the first step of the two-step attack flow and store pending_attack."""
    turn_state = get_turn_state_func(combat, player_id)

    player_derived = player.derived or {}
    player_class = _normalize_class(player.char_class)
    player_level = player.level
    try:
        validate_can_take_action(player)
    except CombatActionRuleError as exc:
        raise CombatAttackRollError(exc.status_code, exc.detail) from exc

    max_attacks = combat_service.get_attack_count(player_derived, player_level, player_class)
    is_martial_arts = is_martial_arts_attack(action_type)
    is_bonus_action_attack = bool(is_offhand or is_martial_arts)
    turn_state = validate_attack_turn_state(
        turn_state,
        max_attacks=max_attacks,
        is_offhand=is_offhand,
        is_bonus_action_attack=is_martial_arts,
    )
    if is_offhand:
        validate_two_weapon_fighting_equipment(player)

    target = await resolve_attack_target(db, target_id, enemies, allow_auto_enemy=False, session=session)
    if not target:
        raise CombatAttackRollError(400, "目标不存在")

    target_derived = target.derived
    target_name = target.name
    resolved_target_id = target.id
    if is_charmed_by_target(
        getattr(player, "conditions", None) or [],
        getattr(player, "condition_durations", None) or {},
        resolved_target_id,
    ):
        raise CombatAttackRollError(400, CHARMED_ATTACK_ERROR)

    positions = dict(combat.entity_positions or {})
    attacker_position = positions.get(str(player_id))
    target_position = positions.get(str(resolved_target_id))
    is_ranged = action_type == "ranged"
    in_range, distance, range_error = check_attack_range_func(
        attacker_position,
        target_position,
        is_ranged,
    )
    if not in_range:
        raise CombatAttackRollError(400, range_error or "目标不在攻击范围内")

    if is_martial_arts:
        weapon_resource_use = None
        weapon_resource = None
    else:
        weapon_resource_use = consume_attack_weapon_resource(
            player,
            is_ranged=is_ranged,
            weapon_name=weapon_name,
        )
        weapon_resource = weapon_resource_use.to_dict() or None

    player_conditions = list(player.conditions or [])
    target_conditions = await get_target_conditions(db, target, enemies)
    target_turn_state = get_turn_state_func(combat, resolved_target_id)
    if target_turn_state.get("dodging") and "dodging" not in target_conditions:
        target_conditions.append("dodging")

    attacker_advantage_sources, attacker_disadvantage_sources = get_attack_modifier_sources(
        player_conditions,
        player,
    )
    defense_advantage_sources, defense_disadvantage_sources = get_defense_modifier_sources(
        target_conditions,
    )
    attacker_advantage = bool(attacker_advantage_sources)
    attacker_disadvantage = bool(attacker_disadvantage_sources)
    defense_advantage = bool(defense_advantage_sources)
    defense_disadvantage = bool(defense_disadvantage_sources)
    if "prone" in target_conditions and distance > 1:
        non_prone_conditions = [condition for condition in target_conditions if condition != "prone"]
        defense_advantage_sources, defense_disadvantage_sources = get_defense_modifier_sources(
            non_prone_conditions,
        )
        defense_disadvantage = True
        defense_disadvantage_sources = _append_unique(
            defense_disadvantage_sources,
            "target prone at range",
        )
        defense_advantage = bool(defense_advantage_sources)

    if turn_state.get("being_helped"):
        attacker_advantage = True
        attacker_advantage_sources = _append_unique(attacker_advantage_sources, "help action")
        turn_state["being_helped"] = False

    attacker_disadvantage, ranged_penalty = apply_ranged_close_penalty(
        atk_dis=attacker_disadvantage,
        is_ranged=is_ranged,
        attacker_id=player_id,
        enemies=enemies,
        positions=positions,
        attacker_derived=player_derived,
    )
    if ranged_penalty:
        attacker_disadvantage_sources = _append_unique(
            attacker_disadvantage_sources,
            "attacker ranged close",
        )

    cover_bonus = calculate_cover_bonus(
        grid_data=dict(combat.grid_data or {}),
        positions=positions,
        attacker_id=player_id,
        target_id=resolved_target_id,
        attacker_derived=player_derived,
        is_ranged=is_ranged,
    )

    feat_power = choose_feat_power_attack(
        attacker_derived=player_derived,
        target_derived=target_derived,
        cover_bonus=cover_bonus,
        is_ranged=is_ranged,
    )
    defender_interception = None
    if target.is_enemy and not (attacker_disadvantage or defense_disadvantage):
        defender_interception = apply_defender_interception(
            combat=combat,
            attacker_id=player_id,
            target_id=resolved_target_id,
            enemies=enemies,
            positions=positions,
            get_turn_state_func=get_turn_state_func,
            save_turn_state_func=save_turn_state_func,
        )
        if defender_interception:
            defense_disadvantage = True
            defense_disadvantage_sources = _append_unique(
                defense_disadvantage_sources,
                "defender interception",
            )

    attack_source_derived = (
        build_martial_arts_attack_derived(player, player_derived)
        if is_martial_arts
        else player_derived
    )
    attack_attacker_derived, attack_target_derived = build_attack_deriveds(
        attacker_derived=attack_source_derived,
        target_derived=target_derived,
        cover_bonus=cover_bonus,
        is_ranged=is_ranged,
        power=feat_power,
    )

    class_resources = player.class_resources or {}
    is_raging = class_resources.get("raging", False)
    crit_threshold = attack_attacker_derived.get("crit_threshold", 20)
    advantage_sources = [*attacker_advantage_sources, *defense_advantage_sources]
    disadvantage_sources = [*attacker_disadvantage_sources, *defense_disadvantage_sources]
    roll_state = _resolve_roll_state(
        attacker_advantage or defense_advantage,
        attacker_disadvantage or defense_disadvantage,
    )
    final_advantage = roll_state == "advantage"
    final_disadvantage = roll_state == "disadvantage"
    attack_roll_result = roll_attack_func(
        attacker={"derived": attack_attacker_derived, "conditions": player_conditions},
        target={"derived": attack_target_derived},
        is_ranged=is_ranged,
        advantage=final_advantage,
        disadvantage=final_disadvantage,
        crit_threshold=crit_threshold,
    )
    attack_roll_result = apply_d20_override(
        attack_roll_result,
        d20_value=d20_value,
        second_d20_value=second_d20_value,
        crit_threshold=crit_threshold,
        roll_state=roll_state,
    )
    if use_lucky:
        try:
            lucky = spend_lucky_point(
                player,
                d20_before=attack_roll_result.get("d20"),
                lucky_d20_value=lucky_d20_value,
                context="attack_roll",
            )
        except LuckyFeatError as exc:
            raise CombatAttackRollError(exc.status_code, exc.detail) from exc
        attack_roll_result = apply_lucky_to_attack_roll(
            attack_roll_result,
            lucky=lucky,
            crit_threshold=crit_threshold,
        )
    if use_bardic_inspiration:
        try:
            bardic_inspiration = spend_bardic_inspiration(
                player,
                bardic_roll=bardic_inspiration_roll,
                context="attack_roll",
            )
        except BardicInspirationError as exc:
            raise CombatAttackRollError(exc.status_code, exc.detail) from exc
        attack_roll_result = apply_bardic_inspiration_to_attack_roll(
            attack_roll_result,
            bardic_inspiration=bardic_inspiration,
        )
    attack_roll_result = {
        **attack_roll_result,
        "advantage": final_advantage,
        "disadvantage": final_disadvantage,
        "advantage_sources": advantage_sources,
        "disadvantage_sources": disadvantage_sources,
        "roll_state": roll_state,
    }
    if defender_interception:
        attack_roll_result = {**attack_roll_result, "defender_interception": defender_interception}
    if (
        should_auto_crit_melee_target(target_conditions, distance=distance, is_ranged=is_ranged)
        and attack_roll_result.get("hit")
        and not attack_roll_result.get("is_crit")
    ):
        attack_roll_result = {**attack_roll_result, "is_crit": True, "forced_crit": "incapacitated_target"}
    if "guiding_bolt" in target_conditions:
        await consume_guiding_bolt_condition(
            db,
            target_id=resolved_target_id,
            target_is_enemy=target.is_enemy,
            enemies=enemies,
            session=session,
        )

    if is_martial_arts:
        martial_damage_dice, martial_hit_die, martial_dmg_mod = build_martial_arts_damage_dice(player)
        weapon_damage = WeaponDamageDice(
            damage_dice=martial_damage_dice,
            hit_die=martial_hit_die,
            dmg_mod=martial_dmg_mod,
        )
    else:
        weapon_damage = build_weapon_damage_dice(
            player,
            is_ranged=is_ranged,
            is_offhand=is_offhand,
            weapon=weapon_resource_use.weapon if weapon_resource_use else None,
        )

    pending_attack_id = str(uuid4())
    pending_attack = build_pending_attack(
        pending_attack_id=pending_attack_id,
        attacker_id=player_id,
        target_id=resolved_target_id,
        target_name=target_name,
        target_is_enemy=target.is_enemy,
        attacker_name=player.name,
        attack_roll=attack_roll_result,
        is_ranged=is_ranged,
        is_offhand=is_offhand,
        cover_bonus=cover_bonus,
        ranged_penalty=ranged_penalty,
        feat_power_active=feat_power.active,
        feat_power_bonus_damage=feat_power.bonus_damage,
        advantage=final_advantage,
        disadvantage=final_disadvantage,
        advantage_sources=advantage_sources,
        disadvantage_sources=disadvantage_sources,
        roll_state=roll_state,
        is_raging=is_raging,
        target_conditions=target_conditions,
        damage_dice=weapon_damage.damage_dice,
        hit_die=weapon_damage.hit_die,
        dmg_mod=weapon_damage.dmg_mod,
        weapon_resource=weapon_resource,
        is_martial_arts=is_martial_arts,
        damage_type="bludgeoning" if is_martial_arts else None,
    )
    if defender_interception:
        pending_attack["defender_interception"] = defender_interception
    turn_state = consume_attack_turn_state(
        turn_state,
        max_attacks=max_attacks,
        is_offhand=is_offhand,
        is_bonus_action_attack=is_bonus_action_attack,
        pending_attack=pending_attack,
    )
    turn_state = record_mobile_opportunity_safe_target(
        turn_state,
        resolved_target_id,
        attacker_derived=player_derived,
        is_ranged=is_ranged,
    )
    save_turn_state_func(combat, player_id, turn_state)

    return PreparedAttackRoll(
        attacker_name=player.name,
        attacker_class=player_class,
        target_name=target_name,
        attack_roll_result=attack_roll_result,
        cover_bonus=cover_bonus,
        advantage=final_advantage,
        disadvantage=final_disadvantage,
        advantage_sources=advantage_sources,
        disadvantage_sources=disadvantage_sources,
        roll_state=roll_state,
        damage_dice=weapon_damage.damage_dice,
        pending_attack_id=pending_attack_id,
        pending_attack=pending_attack,
        weapon_resource=weapon_resource,
        turn_state=turn_state,
        attacks_max=max_attacks,
        defender_interception=defender_interception,
    )


def _append_unique(values: list[str], value: str) -> list[str]:
    if value in values:
        return values
    return [*values, value]


def _resolve_roll_state(advantage: bool, disadvantage: bool) -> str:
    if advantage and disadvantage:
        return "cancelled"
    if advantage:
        return "advantage"
    if disadvantage:
        return "disadvantage"
    return "normal"
