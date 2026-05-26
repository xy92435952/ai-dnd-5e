from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm.attributes import flag_modified

from models import Character
from services.combat_attack_damage_service import apply_attack_damage_to_target
from services.combat_attack_roll_service import CombatAttackRollError
from services.combat_grid_service import chebyshev_distance
from services.combat_service import CombatService
from services.combat_turn_state_service import get_turn_state, save_turn_state
from services.session_access_service import assert_character_in_session

svc = CombatService()


@dataclass
class OffhandAttackResult:
    narration: str
    attack_result: dict[str, Any]
    damage: int
    damage_roll: dict[str, Any] | None
    target_id: str
    target_new_hp: int | None
    target_state: dict[str, Any] | None
    concentration_log: Any | None
    turn_state: dict[str, Any]
    combat_over: bool
    outcome: str | None


async def resolve_offhand_attack(
    db,
    *,
    session_id: str,
    session,
    combat,
    player,
    player_id: str,
    player_name: str,
    target_id: str | None,
    state: dict[str, Any],
    enemies: list[dict[str, Any]],
    combat_service: CombatService = svc,
    flag_modified_func: Callable[[Any, str], None] = flag_modified,
    save_turn_state_func: Callable[[Any, str, dict[str, Any]], None] = save_turn_state,
) -> OffhandAttackResult:
    turn_state = get_turn_state(combat, player_id)
    if not turn_state.get("action_used"):
        raise CombatAttackRollError(400, "副手攻击需要先完成本回合的主手攻击")
    if turn_state.get("bonus_action_used"):
        raise CombatAttackRollError(400, "本回合附赠行动已用尽")

    target = await _resolve_offhand_target(db, session=session, target_id=target_id, enemies=enemies)
    if not target:
        raise CombatAttackRollError(400, "没有可攻击的目标")

    attack = combat_service.resolve_melee_attack(
        attacker_derived=player.derived or {} if player else {},
        target_derived=target["derived"],
        is_offhand=True,
        target_conditions=target["conditions"],
        distance=chebyshev_distance(
            (getattr(combat, "entity_positions", None) or {}).get(str(player_id), {}),
            (getattr(combat, "entity_positions", None) or {}).get(str(target["id"]), {}),
        ),
    )

    concentration_log = None
    target_new_hp = None
    target_state = None
    if attack.attack_roll["hit"]:
        target_new_hp, concentration_log, target_state = await apply_attack_damage_to_target(
            db,
            session_id=session_id,
            enemies=enemies,
            target_id=target["id"],
            target_is_enemy=target["is_enemy"],
            damage=attack.damage,
            session=session,
            is_critical=attack.attack_roll.get("is_crit", False),
        )
        if target["is_enemy"]:
            state["enemies"] = enemies
            session.game_state = dict(state)
            flag_modified_func(session, "game_state")

    turn_state["bonus_action_used"] = True
    save_turn_state_func(combat, player_id, turn_state)

    narration = (
        f"【副手攻击】"
        + combat_service._build_narration(
            player_name,
            target["name"],
            attack.attack_roll,
            attack.damage,
        )
    )

    player_check = await db.get(Character, session.player_character_id) if session.player_character_id else None
    combat_over, outcome = combat_service.check_combat_over(
        enemies,
        player_check.hp_current if player_check else 0,
    )
    if combat_over:
        session.combat_active = False

    return OffhandAttackResult(
        narration=narration,
        attack_result=attack.attack_roll,
        damage=attack.damage,
        damage_roll=attack.damage_roll,
        target_id=target["id"],
        target_new_hp=target_new_hp,
        target_state=target_state,
        concentration_log=concentration_log,
        turn_state=turn_state,
        combat_over=combat_over,
        outcome=outcome,
    )


async def _resolve_offhand_target(
    db,
    *,
    session,
    target_id: str | None,
    enemies: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if target_id:
        target_character = await db.get(Character, target_id)
        if target_character:
            await assert_character_in_session(target_character, session, db)
            return {
                "id": target_character.id,
                "name": target_character.name,
                "derived": target_character.derived or {},
                "conditions": list(target_character.conditions or []),
                "is_enemy": False,
            }

        enemy = next((item for item in enemies if item["id"] == target_id), None)
        if enemy:
            return {
                "id": enemy["id"],
                "name": enemy.get("name", "敌人"),
                "derived": enemy.get("derived", {}),
                "conditions": list(enemy.get("conditions", [])),
                "is_enemy": True,
            }

    alive = [enemy for enemy in enemies if enemy.get("hp_current", 0) > 0]
    if not alive:
        return None

    enemy = alive[0]
    return {
        "id": enemy["id"],
        "name": enemy.get("name", "敌人"),
            "derived": enemy.get("derived", {}),
            "conditions": list(enemy.get("conditions", [])),
            "is_enemy": True,
        }
