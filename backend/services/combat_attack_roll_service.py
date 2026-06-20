from dataclasses import dataclass


@dataclass
class CombatAttackRollError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


def validate_attack_turn_state(
    turn_state: dict,
    *,
    max_attacks: int,
    is_offhand: bool,
    is_bonus_action_attack: bool = False,
) -> dict:
    turn_state.setdefault("attacks_made", 0)
    turn_state["attacks_max"] = max_attacks

    if is_offhand or is_bonus_action_attack:
        if turn_state.get("attacks_made", 0) <= 0:
            raise CombatAttackRollError(400, "副手攻击需要先完成本回合的主手攻击")
        if turn_state.get("bonus_action_used"):
            raise CombatAttackRollError(400, "本回合附赠行动已用尽")
        return turn_state

    if turn_state["attacks_made"] >= max_attacks:
        if turn_state.get("action_used"):
            raise CombatAttackRollError(400, "本回合行动已用尽，请使用「结束回合」")
        raise CombatAttackRollError(400, "本回合攻击次数已达上限")

    return turn_state


def apply_d20_override(
    attack_roll: dict,
    *,
    d20_value: int | None,
    crit_threshold: int,
    second_d20_value: int | None = None,
    roll_state: str = "normal",
) -> dict:
    if d20_value is None:
        return attack_roll

    selected_d20 = d20_value
    d20_metadata = {}
    if second_d20_value is not None and roll_state in {"advantage", "disadvantage"}:
        d20_rolls = [d20_value, second_d20_value]
        if roll_state == "advantage":
            selected_d20 = max(d20_rolls)
        else:
            selected_d20 = min(d20_rolls)
        other_roll = second_d20_value if selected_d20 == d20_value else d20_value
        d20_metadata = {
            "d20_rolls": d20_rolls,
            "selected_d20": selected_d20,
            "other_roll": other_roll,
            "d20_selection": roll_state,
        }

    attack_bonus = attack_roll["attack_bonus"]
    condition_modifier = attack_roll.get("condition_modifier", 0) or 0
    attack_total = selected_d20 + attack_bonus + condition_modifier
    target_ac = attack_roll["target_ac"]
    is_crit = selected_d20 >= crit_threshold
    is_fumble = selected_d20 == 1
    hit = (not is_fumble) and (is_crit or attack_total >= target_ac)

    return {
        **attack_roll,
        "d20": selected_d20,
        "attack_total": attack_total,
        "hit": hit,
        "is_crit": is_crit,
        "is_fumble": is_fumble,
        **d20_metadata,
    }


def build_pending_attack(
    *,
    pending_attack_id: str,
    attacker_id: str,
    target_id: str,
    target_name: str,
    target_is_enemy: bool,
    attacker_name: str,
    attack_roll: dict,
    is_ranged: bool,
    is_offhand: bool,
    cover_bonus: int,
    ranged_penalty: bool,
    feat_power_active: bool,
    feat_power_bonus_damage: int,
    advantage: bool,
    disadvantage: bool,
    advantage_sources: list[str] | None = None,
    disadvantage_sources: list[str] | None = None,
    roll_state: str = "normal",
    is_raging: bool,
    target_conditions: list[str] | None = None,
    damage_dice: str,
    hit_die: int,
    dmg_mod: int,
    weapon_resource: dict | None = None,
    is_martial_arts: bool = False,
    damage_type: str | None = None,
) -> dict:
    pending = {
        "pending_attack_id": pending_attack_id,
        "attacker_id": attacker_id,
        "target_id": target_id,
        "target_name": target_name,
        "target_is_enemy": target_is_enemy,
        "attacker_name": attacker_name,
        "attack_roll": attack_roll,
        "is_ranged": is_ranged,
        "is_offhand": is_offhand,
        "is_crit": attack_roll["is_crit"],
        "hit": attack_roll["hit"],
        "cover_bonus": cover_bonus,
        "ranged_penalty": ranged_penalty,
        "feat_power_attack": feat_power_active,
        "feat_power_bonus_dmg": feat_power_bonus_damage,
        "advantage": advantage,
        "disadvantage": disadvantage,
        "advantage_sources": advantage_sources or [],
        "disadvantage_sources": disadvantage_sources or [],
        "roll_state": roll_state,
        "is_raging": is_raging,
        "target_conditions": target_conditions or [],
        "damage_dice": damage_dice,
        "hit_die": hit_die,
        "dmg_mod": dmg_mod,
    }
    if weapon_resource:
        pending["weapon_resource"] = weapon_resource
    if is_martial_arts:
        pending["is_martial_arts"] = True
    if damage_type:
        pending["damage_type"] = damage_type
    return pending


def consume_attack_turn_state(
    turn_state: dict,
    *,
    max_attacks: int,
    is_offhand: bool,
    is_bonus_action_attack: bool = False,
    pending_attack: dict,
) -> dict:
    if is_offhand or is_bonus_action_attack:
        turn_state["bonus_action_used"] = True
    else:
        turn_state["attacks_made"] = turn_state.get("attacks_made", 0) + 1
        if turn_state["attacks_made"] >= max_attacks:
            turn_state["action_used"] = True

    turn_state["pending_attack"] = pending_attack
    return turn_state
