from dataclasses import dataclass
from typing import Any, Callable
import random

from sqlalchemy.orm.attributes import flag_modified

from models import Character
from services.combat_action_rules_service import CombatActionRuleError, validate_can_take_action
from services.dnd_rules import roll_dice
from services.session_access_service import assert_character_in_session


@dataclass
class CombatManeuverError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


@dataclass
class ManeuverResolution:
    narration: str
    payload: dict[str, Any]
    log_dice_result: dict[str, Any]


async def resolve_maneuver(
    db,
    *,
    session,
    combat,
    maneuver_name: str,
    target_id: str,
    flag_modified_func: Callable[[Any, str], None] = flag_modified,
) -> ManeuverResolution:
    if not combat:
        raise CombatManeuverError(404, "当前没有进行中的战斗")

    turn_order = combat.turn_order or []
    if not turn_order:
        raise CombatManeuverError(400, "无回合顺序")

    current_entry = turn_order[combat.current_turn_index % len(turn_order)]
    actor_id = str(current_entry.get("character_id", ""))
    actor_char = await db.get(Character, actor_id)
    if not actor_char:
        raise CombatManeuverError(404, "当前行动角色不存在")
    try:
        validate_can_take_action(actor_char)
    except CombatActionRuleError as exc:
        raise CombatManeuverError(exc.status_code, exc.detail) from exc

    derived = actor_char.derived or {}
    sub_effects = derived.get("subclass_effects", {})
    if not sub_effects.get("battle_master"):
        raise CombatManeuverError(400, "当前角色不是战争大师，无法使用战技")

    class_resources = dict(actor_char.class_resources or {})
    sd_remaining = class_resources.get("superiority_dice_remaining", 0)
    if sd_remaining <= 0:
        raise CombatManeuverError(400, "优势骰已耗尽（短休后恢复）")

    known_maneuvers = class_resources.get("maneuvers_known") or class_resources.get("maneuvers") or []
    valid_maneuvers = known_maneuvers or sub_effects.get("maneuvers", [])
    if maneuver_name not in valid_maneuvers:
        raise CombatManeuverError(400, f"无效战技: {maneuver_name}，可用: {valid_maneuvers}")

    class_resources["superiority_dice_remaining"] = sd_remaining - 1
    actor_char.class_resources = class_resources

    sd_die = sub_effects.get("superiority_die", "d8")
    sd_roll = roll_dice(sd_die)
    sd_value = sd_roll["total"]

    game_state = session.game_state or {}
    enemies = game_state.get("enemies", [])
    target = await _resolve_maneuver_target(db, session=session, enemies=enemies, target_id=target_id)
    target_name = target["name"]

    payload = {
        "maneuver": maneuver_name,
        "superiority_die_roll": sd_value,
        "superiority_die": sd_die,
        "dice_remaining": sd_remaining - 1,
        "actor": actor_char.name,
        "target": target_name,
    }

    maneuver_dc = _maneuver_save_dc(derived)
    msg = _resolve_maneuver_effect(
        maneuver_name=maneuver_name,
        payload=payload,
        actor_name=actor_char.name,
        target=target,
        target_name=target_name,
        maneuver_dc=maneuver_dc,
        sd_value=sd_value,
    )

    flag_modified_func(actor_char, "class_resources")
    if target["is_enemy"]:
        session.game_state = game_state
        flag_modified_func(session, "game_state")

    log_dice_result = dict(payload)
    payload["dice_roll"] = {
        "faces": _superiority_die_faces(sd_die),
        "result": sd_value,
        "label": f"战技·{maneuver_name}",
    }
    payload["narration"] = msg

    return ManeuverResolution(
        narration=msg,
        payload=payload,
        log_dice_result=log_dice_result,
    )


async def _resolve_maneuver_target(db, *, session, enemies: list[dict[str, Any]], target_id: str) -> dict[str, Any]:
    for enemy in enemies:
        if str(enemy.get("id")) == target_id:
            return {
                "enemy": enemy,
                "character": None,
                "name": enemy.get("name", "Enemy"),
                "is_enemy": True,
            }

    target_char = await db.get(Character, target_id)
    if target_char:
        await assert_character_in_session(target_char, session, db)
    return {
        "enemy": None,
        "character": target_char,
        "name": target_char.name if target_char else "Unknown",
        "is_enemy": False,
    }


def _maneuver_save_dc(actor_derived: dict[str, Any]) -> int:
    proficiency_bonus = actor_derived.get("proficiency_bonus", 2)
    ability_modifiers = actor_derived.get("ability_modifiers", {})
    return 8 + proficiency_bonus + max(
        ability_modifiers.get("str", 0),
        ability_modifiers.get("dex", 0),
    )


def _resolve_maneuver_effect(
    *,
    maneuver_name: str,
    payload: dict[str, Any],
    actor_name: str,
    target: dict[str, Any],
    target_name: str,
    maneuver_dc: int,
    sd_value: int,
) -> str:
    if maneuver_name == "precision":
        payload["effect"] = f"下次攻击骰+{sd_value}"
        payload["attack_bonus"] = sd_value
        return f"⚔️ {actor_name} 使用精准打击，攻击骰+{sd_value}"

    if maneuver_name == "trip":
        save = _roll_target_save(target, ability="str")
        tripped = save["total"] < maneuver_dc
        payload.update(save_roll=save["d20"], save_total=save["total"], dc=maneuver_dc)
        payload["tripped"] = tripped
        payload["extra_damage"] = sd_value
        if tripped:
            _add_target_condition(target, "prone")
            return f"⚔️ {actor_name} 使用绊摔攻击！{target_name} 摔倒（俯卧），额外伤害{sd_value}"
        return f"⚔️ {actor_name} 使用绊摔攻击，{target_name} 站稳了！额外伤害{sd_value}"

    if maneuver_name == "disarm":
        save = _roll_target_save(target, ability="str")
        disarmed = save["total"] < maneuver_dc
        payload.update(save_roll=save["d20"], save_total=save["total"], dc=maneuver_dc)
        payload["disarmed"] = disarmed
        if disarmed:
            return f"⚔️ {actor_name} 使用缴械打击！{target_name} 武器脱手！"
        return f"⚔️ {actor_name} 使用缴械打击，{target_name} 握紧了武器"

    if maneuver_name == "riposte":
        payload["extra_damage"] = sd_value
        payload["effect"] = "反击攻击"
        return f"⚔️ {actor_name} 使用反击！额外伤害+{sd_value}"

    if maneuver_name == "menacing":
        save = _roll_target_save(target, ability="wis")
        frightened = save["total"] < maneuver_dc
        payload.update(save_roll=save["d20"], save_total=save["total"], dc=maneuver_dc)
        payload["frightened"] = frightened
        payload["extra_damage"] = sd_value
        if frightened:
            _add_target_condition(target, "frightened")
            return f"⚔️ {actor_name} 使用威吓攻击！{target_name} 陷入恐惧，额外伤害{sd_value}"
        return f"⚔️ {actor_name} 使用威吓攻击，{target_name} 不为所动！额外伤害{sd_value}"

    if maneuver_name == "pushing":
        payload["push_distance"] = 15
        payload["extra_damage"] = sd_value
        return f"⚔️ {actor_name} 使用推击！{target_name} 被推开15尺，额外伤害{sd_value}"

    if maneuver_name == "goading":
        save = _roll_target_save(target, ability="wis")
        goaded = save["total"] < maneuver_dc
        payload.update(save_roll=save["d20"], save_total=save["total"], dc=maneuver_dc)
        payload["goaded"] = goaded
        payload["extra_damage"] = sd_value
        if goaded:
            return f"⚔️ {actor_name} 使用激怒攻击！{target_name} 攻击其他目标时有劣势，额外伤害{sd_value}"
        return f"⚔️ {actor_name} 使用激怒攻击，{target_name} 不受影响！额外伤害{sd_value}"

    return f"⚔️ {actor_name} 使用了未知战技"


def _roll_target_save(target: dict[str, Any], *, ability: str) -> dict[str, int]:
    d20 = random.randint(1, 20)
    modifier = 0
    if target["enemy"]:
        scores = target["enemy"].get("ability_scores", {})
        modifier = (scores.get(ability, 10) - 10) // 2
    elif target["character"]:
        modifier = (target["character"].derived or {}).get("ability_modifiers", {}).get(ability, 0)
    return {"d20": d20, "total": d20 + modifier}


def _add_target_condition(target: dict[str, Any], condition: str) -> None:
    if target["enemy"]:
        conditions = target["enemy"].get("conditions", [])
        if condition not in conditions:
            conditions.append(condition)
            target["enemy"]["conditions"] = conditions
    elif target["character"]:
        conditions = list(target["character"].conditions or [])
        if condition not in conditions:
            conditions.append(condition)
            target["character"].conditions = conditions


def _superiority_die_faces(sd_die: str) -> int:
    return int(sd_die.replace("d", "")) if sd_die.startswith("d") else 8
