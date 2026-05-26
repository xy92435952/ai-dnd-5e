from dataclasses import dataclass
from typing import Any, Callable

from services.character_roster import CharacterRoster
from services.combat_attack_modifier_service import (
    apply_ranged_close_penalty,
    build_attack_deriveds,
    calculate_cover_bonus,
    choose_feat_power_attack,
)
from services.combat_attack_roll_service import CombatAttackRollError
from services.combat_attack_targeting_service import get_target_conditions, resolve_attack_target
from services.combat_service import CombatService
from services.combat_turn_state_service import get_turn_state, save_turn_state
from services.dnd_rules import _normalize_class, roll_dice

svc = CombatService()


@dataclass
class PreparedDirectAttack:
    player_name: str
    player_class: str
    player_level: int
    player_derived: dict[str, Any]
    subclass_effects: dict[str, Any]
    target_id: str
    target_name: str
    target_is_enemy: bool
    attack_result: dict[str, Any]
    damage: int
    damage_roll: dict[str, Any] | None
    damage_type: str
    extra_damage_notes: list[str]
    sneak_attack_applied: bool
    sneak_attack_damage: int
    ranged_penalty: bool
    cover_bonus: int
    feat_power_attack: bool
    turn_state: dict[str, Any]
    attacks_max: int


async def prepare_direct_attack(
    db,
    *,
    combat,
    player,
    player_id: str,
    target_id: str | None,
    enemies: list[dict[str, Any]],
    is_ranged: bool,
    session=None,
    combat_service: CombatService = svc,
    get_turn_state_func: Callable[[Any, str], dict[str, Any]] = get_turn_state,
    save_turn_state_func: Callable[[Any, str, dict[str, Any]], None] = save_turn_state,
    has_ally_adjacent_to: Callable[[str, str, list[dict[str, Any]], dict[str, Any]], bool] | None = None,
) -> PreparedDirectAttack:
    """Prepare and roll the legacy immediate-damage /action attack path."""
    turn_state = get_turn_state_func(combat, player_id)
    player_derived = player.derived or {} if player else {}
    player_class = _normalize_class(player.char_class) if player else ""
    player_level = player.level if player else 1
    player_name = player.name if player else "你"

    max_attacks = combat_service.get_attack_count(player_derived, player_level, player_class)
    turn_state.setdefault("attacks_made", 0)
    turn_state["attacks_max"] = max_attacks
    if turn_state["attacks_made"] >= max_attacks:
        if turn_state.get("action_used"):
            raise CombatAttackRollError(400, "本回合行动已用尽，请使用「结束回合」")
        raise CombatAttackRollError(400, "本回合攻击次数已达上限")

    target = await resolve_attack_target(db, target_id, enemies, allow_auto_enemy=True, session=session)
    if not target:
        raise CombatAttackRollError(400, "没有可攻击的目标")

    target_derived = target.derived
    target_name = target.name
    resolved_target_id = target.id

    player_conditions = list(player.conditions or []) if player else []
    target_conditions = await get_target_conditions(db, target, enemies)
    target_turn_state = get_turn_state_func(combat, resolved_target_id)
    if target_turn_state.get("dodging") and "dodging" not in target_conditions:
        target_conditions.append("dodging")
    attack_advantage, attack_disadvantage = combat_service.get_attack_modifiers(player_conditions, player)
    defense_advantage, defense_disadvantage = combat_service.get_defense_modifiers(target_conditions)

    if turn_state.get("being_helped"):
        attack_advantage = True
        turn_state["being_helped"] = False

    positions = dict(combat.entity_positions or {})
    attacker_pos = positions.get(str(player_id), {})
    target_pos = positions.get(str(resolved_target_id), {})
    target_distance = max(
        abs((attacker_pos.get("x", 0) or 0) - (target_pos.get("x", 0) or 0)),
        abs((attacker_pos.get("y", 0) or 0) - (target_pos.get("y", 0) or 0)),
    )
    attack_disadvantage, ranged_penalty = apply_ranged_close_penalty(
        atk_dis=attack_disadvantage,
        is_ranged=is_ranged,
        attacker_id=player_id,
        enemies=enemies,
        positions=positions,
        attacker_derived=player_derived,
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

    attack_attacker_derived, attack_target_derived = build_attack_deriveds(
        attacker_derived=player_derived,
        target_derived=target_derived,
        cover_bonus=cover_bonus,
        is_ranged=is_ranged,
        power=feat_power,
    )

    class_resources = player.class_resources or {} if player else {}
    is_raging = class_resources.get("raging", False)
    subclass_effects = player_derived.get("subclass_effects", {})
    assassinate_active = _is_assassinate_active(
        subclass_effects=subclass_effects,
        combat=combat,
        target_id=resolved_target_id,
    )
    if assassinate_active:
        attack_advantage = True

    attack_result_obj = combat_service.resolve_melee_attack(
        attacker_derived=attack_attacker_derived,
        target_derived=attack_target_derived,
        advantage=attack_advantage or defense_advantage,
        disadvantage=attack_disadvantage or defense_disadvantage,
        is_ranged=is_ranged,
        target_conditions=target_conditions,
        distance=target_distance,
    )
    attack_result = attack_result_obj.attack_roll
    damage = attack_result_obj.damage
    damage_roll = attack_result_obj.damage_roll
    extra_damage_notes: list[str] = []
    sneak_attack_applied = False
    sneak_attack_damage = 0

    if assassinate_active and attack_result["hit"] and not attack_result["is_crit"]:
        attack_result["is_crit"] = True
        hit_die = player_derived.get("hit_die", 8)
        extra_crit = roll_dice(f"1d{hit_die}")
        damage += extra_crit["total"]
        extra_damage_notes.append(f"暗杀暴击+{extra_crit['total']}")

    if attack_result["hit"] and feat_power.active:
        damage += feat_power.bonus_damage
        feat_name = "巨武器大师" if not is_ranged else "神射手"
        extra_damage_notes.append(f"{feat_name}+{feat_power.bonus_damage}")

    if attack_result["hit"] and not is_ranged:
        melee_bonus = player_derived.get("melee_damage_bonus", 0)
        if melee_bonus > 0:
            damage += melee_bonus
            extra_damage_notes.append(f"决斗+{melee_bonus}")

    if attack_result["hit"] and is_raging and not is_ranged:
        rage_bonus = combat_service.get_rage_bonus(player_level)
        damage += rage_bonus
        extra_damage_notes.append(f"狂暴+{rage_bonus}")

    if (
        attack_result["hit"]
        and is_raging
        and subclass_effects.get("divine_fury")
        and turn_state.get("attacks_made", 0) <= 1
    ):
        fury_roll = roll_dice(f"1d6+{player_level // 2}")
        damage += fury_roll["total"]
        extra_damage_notes.append(f"神圣狂怒+{fury_roll['total']}")

    if attack_result["hit"] and player_class == "Rogue":
        sneak_result = await _apply_direct_sneak_attack(
            db,
            session=session,
            player=player,
            player_id=player_id,
            target_id=resolved_target_id,
            enemies=enemies,
            companions_alive_positions=positions,
            damage=damage,
            extra_damage_notes=extra_damage_notes,
            subclass_effects=subclass_effects,
            turn_state=turn_state,
            has_advantage=attack_advantage or defense_advantage,
            combat_service=combat_service,
            has_ally_adjacent_to=has_ally_adjacent_to,
        )
        damage = sneak_result["damage"]
        extra_damage_notes = sneak_result["extra_damage_notes"]
        sneak_attack_applied = sneak_result["sneak_attack_applied"]
        sneak_attack_damage = sneak_result["sneak_attack_damage"]

    damage_type = player_derived.get("damage_type", "钝击")
    if attack_result["hit"] and target.is_enemy:
        enemy_data = next((enemy for enemy in enemies if enemy["id"] == resolved_target_id), {})
        damage = combat_service.apply_damage_with_resistance(
            damage,
            damage_type,
            enemy_data.get("resistances", []),
            enemy_data.get("immunities", []),
            enemy_data.get("vulnerabilities", []),
        )

    save_turn_state_func(combat, player_id, turn_state)

    return PreparedDirectAttack(
        player_name=player_name,
        player_class=player_class,
        player_level=player_level,
        player_derived=player_derived,
        subclass_effects=subclass_effects,
        target_id=resolved_target_id,
        target_name=target_name,
        target_is_enemy=target.is_enemy,
        attack_result=attack_result,
        damage=damage,
        damage_roll=damage_roll,
        damage_type=damage_type,
        extra_damage_notes=extra_damage_notes,
        sneak_attack_applied=sneak_attack_applied,
        sneak_attack_damage=sneak_attack_damage,
        ranged_penalty=ranged_penalty,
        cover_bonus=cover_bonus,
        feat_power_attack=feat_power.active,
        turn_state=turn_state,
        attacks_max=max_attacks,
    )


def consume_direct_attack_turn(
    turn_state: dict[str, Any],
    *,
    attacks_max: int,
) -> dict[str, Any]:
    turn_state["attacks_made"] = turn_state.get("attacks_made", 0) + 1
    if turn_state["attacks_made"] >= attacks_max:
        turn_state["action_used"] = True
    return turn_state


def apply_dark_ones_blessing_note(
    *,
    target_new_hp: int | None,
    target_is_enemy: bool,
    subclass_effects: dict[str, Any],
    player_derived: dict[str, Any],
    player_level: int,
    extra_damage_notes: list[str],
) -> list[str]:
    if target_new_hp is not None and target_new_hp <= 0 and target_is_enemy:
        if subclass_effects.get("dark_ones_blessing"):
            charisma_mod = player_derived.get("ability_modifiers", {}).get("cha", 0)
            temp_hp = charisma_mod + player_level
            extra_damage_notes.append(f"黑暗祝福+{temp_hp}临时HP")
    return extra_damage_notes


def _is_assassinate_active(
    *,
    subclass_effects: dict[str, Any],
    combat,
    target_id: str,
) -> bool:
    if not subclass_effects.get("assassinate") or combat.round_number != 1:
        return False
    turn_order = list(combat.turn_order or [])
    target_turn_index = next(
        (idx for idx, turn in enumerate(turn_order) if turn.get("character_id") == target_id),
        None,
    )
    return target_turn_index is not None and target_turn_index >= combat.current_turn_index


async def _apply_direct_sneak_attack(
    db,
    *,
    session,
    player,
    player_id: str,
    target_id: str,
    enemies: list[dict[str, Any]],
    companions_alive_positions: dict[str, Any],
    damage: int,
    extra_damage_notes: list[str],
    subclass_effects: dict[str, Any],
    turn_state: dict[str, Any],
    has_advantage: bool,
    combat_service: CombatService,
    has_ally_adjacent_to: Callable[[str, str, list[dict[str, Any]], dict[str, Any]], bool] | None,
) -> dict[str, Any]:
    if has_ally_adjacent_to is None:
        from services.combat_grid_service import has_ally_adjacent_to as has_ally_adjacent_to

    ally_list = [{"id": session.player_character_id, "hp_current": player.hp_current}] if session and player else []
    if session:
        roster = CharacterRoster(db, session)
        for companion in await roster.companions():
            ally_list.append({"id": companion.id, "hp_current": companion.hp_current})

    ally_adjacent = has_ally_adjacent_to(
        target_id,
        player_id,
        ally_list,
        companions_alive_positions,
    )
    is_swashbuckler = subclass_effects.get("swashbuckler", False)
    no_other_enemy_adjacent = False
    if is_swashbuckler:
        other_enemies = [
            enemy for enemy in enemies
            if enemy["id"] != target_id and enemy.get("hp_current", 0) > 0
        ]
        no_other_enemy_adjacent = not has_ally_adjacent_to(
            player_id,
            target_id,
            other_enemies,
            companions_alive_positions,
        )

    sneak_attack_damage = 0
    sneak_attack_applied = False
    if (
        combat_service.check_sneak_attack(
            "Rogue",
            has_advantage,
            ally_adjacent,
            swashbuckler=is_swashbuckler,
            no_other_enemy_adjacent=no_other_enemy_adjacent,
        )
        and turn_state.get("attacks_made", 0) == 0
    ):
        dice_count = combat_service.calc_sneak_attack_dice(player.level)
        sneak_roll = roll_dice(f"{dice_count}d6")
        sneak_attack_damage = sneak_roll["total"]
        damage += sneak_attack_damage
        sneak_attack_applied = True
        extra_damage_notes.append(f"偷袭{dice_count}d6={sneak_attack_damage}")

    return {
        "damage": damage,
        "extra_damage_notes": extra_damage_notes,
        "sneak_attack_applied": sneak_attack_applied,
        "sneak_attack_damage": sneak_attack_damage,
    }
