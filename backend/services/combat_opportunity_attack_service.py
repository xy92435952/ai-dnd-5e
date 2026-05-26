from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from models import Character, GameLog
from services.character_roster import CharacterRoster
from services.combat_concentration_service import do_concentration_check
from services.combat_damage_bonus_service import apply_sustained_damage_effects
from services.combat_guiding_bolt_service import consume_guiding_bolt_condition
from services.combat_grid_service import chebyshev_distance
from services.combat_service import CombatService
from services.combat_turn_state_service import get_turn_state, save_turn_state
from services.dnd_rules import apply_character_damage

svc = CombatService()


async def resolve_opportunity_attacks(
    db,
    session,
    combat,
    moving_id: str,
    old_pos: dict[str, Any],
    new_pos: dict[str, Any],
    positions: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    检查并解析因移动触发的借机攻击（Opportunity Attack，5e PHB p.195）。

    规则：
      - 移动方未脱离接战（disengaged=False）
      - 从威胁者的临近格（Chebyshev<=1）移入非临近格
      - 威胁者本轮 reaction 尚未使用
    """
    state = session.game_state or {}
    enemies = list(state.get("enemies", []))
    results = []
    is_enemy_moving = moving_id in {enemy["id"] for enemy in enemies}

    if not is_enemy_moving:
        moving_char = await db.get(Character, moving_id)
        if not moving_char:
            return results

        for enemy in enemies:
            if enemy.get("hp_current", 0) <= 0:
                continue
            enemy_position = positions.get(str(enemy["id"]))
            if not enemy_position:
                continue
            if chebyshev_distance(enemy_position, old_pos) <= 1 and chebyshev_distance(enemy_position, new_pos) > 1:
                enemy_turn_state = get_turn_state(combat, enemy["id"])
                if enemy_turn_state.get("reaction_used"):
                    continue
                moving_conditions = list(moving_char.conditions or [])
                advantage = "guiding_bolt" in moving_conditions
                if advantage:
                    await consume_guiding_bolt_condition(
                        db,
                        target_id=moving_char.id,
                        target_is_enemy=False,
                        enemies=enemies,
                        session=session,
                    )
                    moving_conditions = [
                        condition for condition in moving_conditions
                        if condition != "guiding_bolt"
                    ]
                result = svc.resolve_melee_attack(
                    attacker_derived=enemy.get("derived", {}),
                    target_derived=moving_char.derived or {},
                    advantage=advantage,
                    attacker_conditions=list(enemy.get("conditions", [])),
                    target_conditions=moving_conditions,
                    distance=chebyshev_distance(enemy_position, old_pos),
                )
                extra_damage_notes: list[str] = []
                if result.attack_roll["hit"]:
                    sustained = apply_sustained_damage_effects(
                        damage=result.damage,
                        extra_damage_notes=extra_damage_notes,
                        attacker_concentration=enemy.get("concentration"),
                        target_conditions=moving_conditions,
                        target_id=moving_char.id,
                        target_is_enemy=False,
                        enemies=enemies,
                        weapon_damage_type=enemy.get("damage_type") or enemy.get("derived", {}).get("damage_type", "piercing"),
                        apply_damage_with_resistance=svc.apply_damage_with_resistance,
                    )
                    result.damage = sustained.damage
                    extra_damage_notes = sustained.extra_damage_notes
                enemy_turn_state["reaction_used"] = True
                save_turn_state(combat, enemy["id"], enemy_turn_state)

                if result.attack_roll["hit"]:
                    apply_character_damage(
                        moving_char,
                        result.damage,
                        is_critical=result.attack_roll.get("is_crit", False),
                    )
                    concentration_log = await do_concentration_check(
                        moving_char,
                        result.damage,
                        session.id,
                    )
                    if concentration_log:
                        db.add(concentration_log)

                narration = svc._build_narration(
                    enemy["name"],
                    moving_char.name,
                    result.attack_roll,
                    result.damage,
                )
                results.append({
                    "attacker": enemy["name"],
                    "target": moving_char.name,
                    "log": GameLog(
                        session_id=session.id,
                        role="system",
                        content=f"⚔️ 借机攻击！{narration}",
                        log_type="combat",
                        dice_result={
                            "attack": result.attack_roll,
                            "damage": result.damage,
                            "opportunity": True,
                        },
                    ),
                    "result": result.to_dict(),
                    "extra_damage_notes": extra_damage_notes,
                })

    else:
        moving_enemy = next((enemy for enemy in enemies if enemy["id"] == moving_id), None)
        if not moving_enemy:
            return results

        player = await db.get(Character, session.player_character_id)
        if player and player.hp_current > 0:
            player_position = positions.get(str(session.player_character_id))
            if (
                player_position
                and chebyshev_distance(player_position, old_pos) <= 1
                and chebyshev_distance(player_position, new_pos) > 1
            ):
                player_turn_state = get_turn_state(combat, session.player_character_id)
                if not player_turn_state.get("reaction_used"):
                    moving_conditions = list(moving_enemy.get("conditions", []))
                    advantage = "guiding_bolt" in moving_conditions
                    if advantage:
                        await consume_guiding_bolt_condition(
                            db,
                            target_id=moving_enemy["id"],
                            target_is_enemy=True,
                            enemies=enemies,
                            session=session,
                        )
                        moving_conditions = [
                            condition for condition in moving_conditions
                            if condition != "guiding_bolt"
                        ]
                    result = svc.resolve_melee_attack(
                        attacker_derived=player.derived or {},
                        target_derived=moving_enemy.get("derived", {}),
                        advantage=advantage,
                        attacker_conditions=list(player.conditions or []),
                        target_conditions=moving_conditions,
                        distance=chebyshev_distance(player_position, old_pos),
                    )
                    extra_damage_notes: list[str] = []
                    if result.attack_roll["hit"]:
                        sustained = apply_sustained_damage_effects(
                            damage=result.damage,
                            extra_damage_notes=extra_damage_notes,
                            attacker_concentration=getattr(player, "concentration", None),
                            target_conditions=moving_conditions,
                            target_id=moving_enemy["id"],
                            target_is_enemy=True,
                            enemies=enemies,
                            weapon_damage_type=(player.derived or {}).get("damage_type", "piercing"),
                            apply_damage_with_resistance=svc.apply_damage_with_resistance,
                        )
                        result.damage = sustained.damage
                        extra_damage_notes = sustained.extra_damage_notes
                    player_turn_state["reaction_used"] = True
                    save_turn_state(combat, session.player_character_id, player_turn_state)

                    if result.attack_roll["hit"]:
                        moving_enemy["hp_current"] = svc.apply_damage(
                            moving_enemy.get("hp_current", 0),
                            result.damage,
                            moving_enemy.get("derived", {}).get("hp_max", 10),
                        )
                        state["enemies"] = enemies
                        session.game_state = dict(state)
                        flag_modified(session, "game_state")

                    narration = svc._build_narration(
                        player.name,
                        moving_enemy["name"],
                        result.attack_roll,
                        result.damage,
                    )
                    results.append({
                        "attacker": player.name,
                        "target": moving_enemy["name"],
                        "log": GameLog(
                            session_id=session.id,
                            role="player",
                            content=f"⚔️ 借机攻击！{narration}",
                            log_type="combat",
                            dice_result={
                                "attack": result.attack_roll,
                                "damage": result.damage,
                                "opportunity": True,
                            },
                        ),
                        "result": result.to_dict(),
                        "extra_damage_notes": extra_damage_notes,
                    })

        roster = CharacterRoster(db, session)
        for companion in await roster.companions_alive():
            companion_id = companion.id
            companion_position = positions.get(str(companion_id))
            if not companion_position:
                continue
            if (
                chebyshev_distance(companion_position, old_pos) <= 1
                and chebyshev_distance(companion_position, new_pos) > 1
            ):
                companion_turn_state = get_turn_state(combat, companion_id)
                if companion_turn_state.get("reaction_used"):
                    continue
                moving_conditions = list(moving_enemy.get("conditions", []))
                advantage = "guiding_bolt" in moving_conditions
                if advantage:
                    await consume_guiding_bolt_condition(
                        db,
                        target_id=moving_enemy["id"],
                        target_is_enemy=True,
                        enemies=enemies,
                        session=session,
                    )
                    moving_conditions = [
                        condition for condition in moving_conditions
                        if condition != "guiding_bolt"
                    ]
                result = svc.resolve_melee_attack(
                    attacker_derived=companion.derived or {},
                    target_derived=moving_enemy.get("derived", {}),
                    advantage=advantage,
                    attacker_conditions=list(companion.conditions or []),
                    target_conditions=moving_conditions,
                    distance=chebyshev_distance(companion_position, old_pos),
                )
                extra_damage_notes: list[str] = []
                if result.attack_roll["hit"]:
                    sustained = apply_sustained_damage_effects(
                        damage=result.damage,
                        extra_damage_notes=extra_damage_notes,
                        attacker_concentration=getattr(companion, "concentration", None),
                        target_conditions=moving_conditions,
                        target_id=moving_enemy["id"],
                        target_is_enemy=True,
                        enemies=enemies,
                        weapon_damage_type=(companion.derived or {}).get("damage_type", "piercing"),
                        apply_damage_with_resistance=svc.apply_damage_with_resistance,
                    )
                    result.damage = sustained.damage
                    extra_damage_notes = sustained.extra_damage_notes
                companion_turn_state["reaction_used"] = True
                save_turn_state(combat, companion_id, companion_turn_state)

                if result.attack_roll["hit"]:
                    moving_enemy["hp_current"] = svc.apply_damage(
                        moving_enemy.get("hp_current", 0),
                        result.damage,
                        moving_enemy.get("derived", {}).get("hp_max", 10),
                    )
                    state["enemies"] = enemies
                    session.game_state = dict(state)
                    flag_modified(session, "game_state")

                narration = svc._build_narration(
                    companion.name,
                    moving_enemy["name"],
                    result.attack_roll,
                    result.damage,
                )
                results.append({
                    "attacker": companion.name,
                    "target": moving_enemy["name"],
                    "log": GameLog(
                        session_id=session.id,
                        role=f"companion_{companion.name}",
                        content=f"⚔️ 借机攻击！{narration}",
                        log_type="combat",
                        dice_result={
                            "attack": result.attack_roll,
                            "damage": result.damage,
                            "opportunity": True,
                        },
                    ),
                    "result": result.to_dict(),
                    "extra_damage_notes": extra_damage_notes,
                })

    return results
