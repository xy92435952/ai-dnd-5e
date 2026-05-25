from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm.attributes import flag_modified

from models import Character
from services.combat_narrator import narrate_action
from services.combat_service import CombatService
from services.combat_turn_state_service import get_turn_state, save_turn_state
from services.dnd_rules import _normalize_class
from services.session_access_service import assert_character_in_session

svc = CombatService()


@dataclass
class CombatGrappleError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


@dataclass
class GrappleShoveResolution:
    narration: str
    payload: dict[str, Any]
    log_dice_result: dict[str, Any]


async def resolve_grapple_shove(
    db,
    *,
    session,
    combat,
    action_type: str,
    target_id: str,
    shove_type: str = "prone",
    combat_service: CombatService = svc,
    flag_modified_func: Callable[[Any, str], None] = flag_modified,
    save_turn_state_func: Callable[[Any, str, dict[str, Any]], None] = save_turn_state,
    narrate_action_func: Callable[..., Any] = narrate_action,
) -> GrappleShoveResolution:
    if not session.combat_active:
        raise CombatGrappleError(400, "当前不在战斗中")
    if not combat:
        raise CombatGrappleError(404, "战斗状态不存在")

    player_id = session.player_character_id
    if getattr(session, "is_multiplayer", False) and combat.turn_order:
        try:
            current = combat.turn_order[combat.current_turn_index or 0]
            current_id = current.get("character_id") if isinstance(current, dict) else None
            if current_id:
                player_id = current_id
        except (IndexError, AttributeError):
            pass

    player = await db.get(Character, player_id)
    if not player:
        raise CombatGrappleError(404, "玩家角色不存在")

    turn_state = get_turn_state(combat, player_id)
    max_attacks = combat_service.get_attack_count(
        player.derived or {},
        player.level,
        _normalize_class(player.char_class),
    )
    turn_state.setdefault("attacks_made", 0)
    turn_state["attacks_max"] = max_attacks
    if turn_state["attacks_made"] >= max_attacks:
        if turn_state.get("action_used"):
            raise CombatGrappleError(400, "本回合行动已用尽")
        raise CombatGrappleError(400, "本回合攻击次数已达上限")

    state = session.game_state or {}
    enemies = list(state.get("enemies", []))
    target = await _resolve_grapple_target(db, session=session, enemies=enemies, target_id=target_id)
    if not target:
        raise CombatGrappleError(404, "目标不存在")

    if action_type == "grapple":
        check_result = combat_service.resolve_grapple(
            player.derived or {},
            target["derived"],
            player.proficient_skills or [],
            target["skills"],
        )
        narration = _apply_grapple_result(
            session=session,
            state=state,
            enemies=enemies,
            target=target,
            player_name=player.name,
            target_name=target["name"],
            success=check_result["success"],
            flag_modified_func=flag_modified_func,
        )
    elif action_type == "shove":
        check_result = combat_service.resolve_shove(
            player.derived or {},
            target["derived"],
            player.proficient_skills or [],
            target["skills"],
            shove_type,
        )
        narration = _apply_shove_result(
            combat=combat,
            session=session,
            state=state,
            enemies=enemies,
            target=target,
            player_id=player_id,
            target_id=target_id,
            player_name=player.name,
            target_name=target["name"],
            shove_type=shove_type,
            success=check_result["success"],
            flag_modified_func=flag_modified_func,
        )
    else:
        raise CombatGrappleError(400, f"未知动作类型：{action_type}")

    turn_state["attacks_made"] = turn_state.get("attacks_made", 0) + 1
    if turn_state["attacks_made"] >= max_attacks:
        turn_state["action_used"] = True
    save_turn_state_func(combat, player_id, turn_state)

    vivid = narrate_action_func(
        actor_name=player.name,
        actor_class=_normalize_class(player.char_class),
        target_name=target["name"],
        action_type=action_type,
        hit=check_result["success"],
    )
    vivid = await vivid if hasattr(vivid, "__await__") else vivid
    if vivid:
        narration = vivid

    log_dice_result = {
        "type": action_type,
        "success": check_result["success"],
        "attacker_roll": check_result["attacker_roll"],
        "target_roll": check_result["target_roll"],
    }
    payload = {
        "action": action_type,
        "success": check_result["success"],
        "narration": narration,
        "attacker_roll": check_result["attacker_roll"],
        "target_roll": check_result["target_roll"],
        "turn_state": turn_state,
        "combat_over": False,
        "outcome": None,
    }
    return GrappleShoveResolution(
        narration=narration,
        payload=payload,
        log_dice_result=log_dice_result,
    )


async def _resolve_grapple_target(db, *, session, enemies: list[dict[str, Any]], target_id: str) -> dict[str, Any] | None:
    target_character = await db.get(Character, target_id)
    if target_character:
        await assert_character_in_session(target_character, session, db)
        return {
            "name": target_character.name,
            "derived": target_character.derived or {},
            "skills": target_character.proficient_skills or [],
            "is_enemy": False,
            "enemy": None,
            "character": target_character,
        }

    target_enemy = next((enemy for enemy in enemies if enemy["id"] == target_id), None)
    if not target_enemy:
        return None
    return {
        "name": target_enemy["name"],
        "derived": target_enemy.get("derived", {}),
        "skills": [],
        "is_enemy": True,
        "enemy": target_enemy,
        "character": None,
    }


def _apply_grapple_result(
    *,
    session,
    state: dict[str, Any],
    enemies: list[dict[str, Any]],
    target: dict[str, Any],
    player_name: str,
    target_name: str,
    success: bool,
    flag_modified_func: Callable[[Any, str], None],
) -> str:
    if not success:
        return f"🤼 {player_name} 尝试擒抱 {target_name}，但失败了！"

    _add_condition_to_grapple_target(
        session=session,
        state=state,
        enemies=enemies,
        target=target,
        condition="grappled",
        flag_modified_func=flag_modified_func,
    )
    return f"🤼 {player_name} 成功擒抱 {target_name}！{target_name} 速度降为0！"


def _apply_shove_result(
    *,
    combat,
    session,
    state: dict[str, Any],
    enemies: list[dict[str, Any]],
    target: dict[str, Any],
    player_id: str,
    target_id: str,
    player_name: str,
    target_name: str,
    shove_type: str,
    success: bool,
    flag_modified_func: Callable[[Any, str], None],
) -> str:
    if not success:
        return f"💥 {player_name} 尝试推撞 {target_name}，但失败了！"

    if shove_type == "prone":
        _add_condition_to_grapple_target(
            session=session,
            state=state,
            enemies=enemies,
            target=target,
            condition="prone",
            flag_modified_func=flag_modified_func,
        )
        return f"💥 {player_name} 成功推倒 {target_name}！{target_name} 陷入倒地状态！"

    _push_target_away(
        combat=combat,
        player_id=player_id,
        target_id=target_id,
        flag_modified_func=flag_modified_func,
    )
    return f"💥 {player_name} 推开 {target_name}！{target_name} 被推后5英尺！"


def _add_condition_to_grapple_target(
    *,
    session,
    state: dict[str, Any],
    enemies: list[dict[str, Any]],
    target: dict[str, Any],
    condition: str,
    flag_modified_func: Callable[[Any, str], None],
) -> None:
    if target["is_enemy"]:
        for enemy in enemies:
            if enemy["id"] == target["enemy"]["id"]:
                conditions = list(enemy.get("conditions", []))
                if condition not in conditions:
                    conditions.append(condition)
                enemy["conditions"] = conditions
        state["enemies"] = enemies
        session.game_state = dict(state)
        flag_modified_func(session, "game_state")
        return

    conditions = list(target["character"].conditions or [])
    if condition not in conditions:
        conditions.append(condition)
    target["character"].conditions = conditions


def _push_target_away(
    *,
    combat,
    player_id: str,
    target_id: str,
    flag_modified_func: Callable[[Any, str], None],
) -> None:
    positions = dict(combat.entity_positions or {})
    player_position = positions.get(str(player_id))
    target_position = positions.get(str(target_id))
    if not player_position or not target_position:
        return

    dx = target_position["x"] - player_position["x"]
    dy = target_position["y"] - player_position["y"]
    push_x = target_position["x"] + (1 if dx > 0 else (-1 if dx < 0 else 0))
    push_y = target_position["y"] + (1 if dy > 0 else (-1 if dy < 0 else 0))
    positions[str(target_id)] = {
        "x": max(0, min(19, push_x)),
        "y": max(0, min(11, push_y)),
    }
    combat.entity_positions = positions
    flag_modified_func(combat, "entity_positions")
