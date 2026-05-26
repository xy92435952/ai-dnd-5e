from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from models import Session
from services.dnd_rules import roll_dice, roll_skill_check


def execute_creative_action(
    *,
    session: Session,
    state: dict[str, Any],
    enemies: list[dict[str, Any]],
    player,
    player_derived: dict[str, Any],
    action: dict[str, Any],
    action_results: list[str],
    dice_display: list[dict[str, Any]],
    executed_action_types: list[str],
    combat_service,
) -> int:
    check_type = action.get("check_type", "str")
    dc = action.get("dc", 15)
    description = action.get("description", "创意行动")
    check_result = roll_skill_check(
        character={
            "derived": player_derived,
            "proficient_skills": player.proficient_skills or [],
            "conditions": player.conditions or [],
            "condition_durations": player.condition_durations or {},
        },
        skill=check_type,
        dc=dc,
    )
    d20 = check_result.get("d20", 10)
    total = check_result.get("total", 10)
    success = check_result.get("success", False)
    dice_display.append({
        "label": f"{description} 检定",
        "dice_face": 20,
        "raw": d20,
        "modifier": f"+{check_result.get('modifier', 0)}",
        "total": total,
        "against": f"DC {dc}",
        "outcome": "成功" if success else "失败",
    })

    total_damage = 0
    if success:
        total_damage = apply_creative_damage(
            session=session,
            state=state,
            enemies=enemies,
            action=action,
            dice_display=dice_display,
            combat_service=combat_service,
        )
        action_results.append(
            f"{description} — 成功！（d20={d20}+{check_result.get('modifier', 0)}={total} vs DC{dc}）"
            + (f" {action.get('effect_on_success', '')}" if action.get("effect_on_success") else "")
        )
    else:
        action_results.append(
            f"{description} — 失败（d20={d20}+{check_result.get('modifier', 0)}={total} vs DC{dc}）"
            + (f" {action.get('effect_on_fail', '')}" if action.get("effect_on_fail") else "")
        )
    executed_action_types.append("creative")
    return total_damage


def apply_creative_damage(
    *,
    session: Session,
    state: dict[str, Any],
    enemies: list[dict[str, Any]],
    action: dict[str, Any],
    dice_display: list[dict[str, Any]],
    combat_service,
) -> int:
    damage_dice = action.get("damage_dice")
    if not damage_dice:
        return 0

    damage_roll = roll_dice(damage_dice)
    creative_damage = damage_roll["total"]
    target_id = action.get("target_id")
    if target_id:
        target_enemy = next((enemy for enemy in enemies if str(enemy["id"]) == str(target_id)), None)
        if target_enemy:
            target_enemy["hp_current"] = combat_service.apply_damage(
                target_enemy.get("hp_current", 0),
                creative_damage,
                target_enemy.get("derived", {}).get("hp_max", 10),
            )
            state["enemies"] = enemies
            session.game_state = dict(state)
            flag_modified(session, "game_state")
    dice_display.append({"label": "伤害", "raw": creative_damage, "total": creative_damage})
    return creative_damage
