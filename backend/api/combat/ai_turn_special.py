"""AI special action branch for monster Recharge abilities."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from api.combat._shared import _get_ts, svc
from api.combat.ai_turn_utils import advance_ai_turn, tick_ai_actor_conditions
from models import Character, CombatState, GameLog
from services.combat_recharge_service import choose_recharge_ability, mark_recharge_ability_used
from services.combat_resistance_service import apply_character_damage_resistance
from services.combat_temporary_hp_service import build_character_target_state
from services.dnd_rules import apply_character_damage, roll_dice, roll_saving_throw


async def handle_ai_special_action(
    session_id: str,
    db,
    session,
    combat,
    turn_order,
    next_index: int,
    actor_id: str,
    actor_name: str,
    is_enemy: bool,
    enemy,
    enemies: list[dict[str, Any]],
    all_characters: list[dict[str, Any]],
    decided_target_id: str | None,
    decided_reason: str,
    decision: dict[str, Any],
):
    """Resolve enemy Recharge damage abilities before falling back to attack/spell."""
    if not is_enemy or not enemy:
        return None

    action_type = str(decision.get("action_type") or "").lower()
    action_name = decision.get("action_name")
    if action_type != "special" and not action_name:
        return None

    ability = choose_recharge_ability(enemy, action_name=action_name)
    if not ability:
        return None
    if action_name and _normalize_name(ability.get("name")) != _normalize_name(action_name):
        return None
    if not ability.get("damage_dice"):
        return None

    target = _choose_special_target(decided_target_id, all_characters)
    if not target:
        return None

    damage_roll = roll_dice(str(ability.get("damage_dice") or "1d6"))
    base_damage = int(damage_roll.get("total") or 0)
    save_detail = _roll_recharge_save(target, ability)
    saved = bool(save_detail and save_detail.get("success"))
    damage_after_save = base_damage // 2 if saved and _half_on_save(ability) else base_damage
    damage_type = ability.get("damage_type") or "bludgeoning"

    target_character = await db.get(Character, str(target.get("id")))
    target_state = None
    target_new_hp = None
    target_name = target.get("name", "target")
    applied_damage = damage_after_save

    if target_character:
        target_name = target_character.name
        applied_damage, _resisted = apply_character_damage_resistance(
            target_character,
            damage_after_save,
            damage_type,
        )
        apply_character_damage(target_character, applied_damage)
        target_new_hp = target_character.hp_current
        target_state = build_character_target_state(target_character)
    else:
        target_enemy = next((item for item in enemies if str(item.get("id")) == str(target.get("id"))), None)
        if target_enemy:
            target_name = target_enemy.get("name", target_name)
            applied_damage = svc.apply_damage_with_resistance(
                damage_after_save,
                damage_type,
                target_enemy.get("resistances", []),
                target_enemy.get("immunities", []),
                target_enemy.get("vulnerabilities", []),
            )
            target_enemy["hp_current"] = svc.apply_damage(
                target_enemy.get("hp_current", 0),
                applied_damage,
                target_enemy.get("derived", {}).get("hp_max", target_enemy.get("hp_max", 10)),
            )
            target_new_hp = target_enemy["hp_current"]
            target_state = _enemy_target_state(target_enemy)
        else:
            return None

    mark_recharge_ability_used(enemy, str(ability.get("id")))
    state = session.game_state or {}
    state["enemies"] = enemies
    session.game_state = dict(state)
    _safe_flag_modified(session, "game_state")

    actor_ts = _get_ts(combat, actor_id)
    actor_ts["action_used"] = True
    _save_turn_state(combat, actor_id, actor_ts)

    narration = _special_narration(
        actor_name=actor_name,
        ability=ability,
        target_name=target_name,
        damage=applied_damage,
        damage_type=damage_type,
        save_detail=save_detail,
        reason=decided_reason,
    )
    db.add(GameLog(
        session_id=session_id,
        role="enemy",
        content=narration,
        log_type="combat",
        dice_result={
            "special": {
                "ability": ability.get("name"),
                "damage": damage_roll,
                "save": save_detail,
            },
        },
    ))
    for log in tick_ai_actor_conditions(
        session_id=session_id,
        session=session,
        actor_name=actor_name,
        is_enemy=True,
        enemy=enemy,
        character=None,
        enemies=enemies,
    ):
        db.add(log)

    await advance_ai_turn(combat, session, db, turn_order, next_index)

    combat_over, outcome = await _check_party_combat_outcome(db, session, enemies, all_characters)
    if combat_over:
        session.combat_active = False
        old_combat = (
            await db.execute(select(CombatState).where(CombatState.session_id == session_id))
        ).scalars().first()
        if old_combat:
            await db.delete(old_combat)

    await db.commit()
    return {
        "actor_name": actor_name,
        "actor_id": actor_id,
        "narration": narration,
        "attack_result": {},
        "damage": applied_damage,
        "damage_roll": damage_roll,
        "damage_type": damage_type,
        "save": save_detail,
        "special_action": {
            "ability_id": ability.get("id"),
            "name": ability.get("name"),
            "recharge": ability.get("recharge"),
            "available": False,
        },
        "target_id": str(target.get("id")),
        "target_new_hp": target_new_hp,
        "target_state": target_state,
        "next_turn_index": next_index,
        "round_number": combat.round_number,
        "combat_over": combat_over,
        "outcome": outcome,
        "entity_positions": dict(combat.entity_positions or {}),
    }


def _choose_special_target(target_id: str | None, all_characters: list[dict[str, Any]]) -> dict[str, Any] | None:
    alive = [item for item in all_characters if item.get("hp_current", 0) > 0]
    if target_id:
        for item in alive:
            if str(item.get("id")) == str(target_id):
                return item
    if alive:
        return min(alive, key=lambda item: item.get("hp_current", 999))
    return None


def _roll_recharge_save(target: dict[str, Any], ability: dict[str, Any]) -> dict[str, Any] | None:
    save_ability = ability.get("saving_throw") or ability.get("save")
    save_dc = ability.get("save_dc")
    if not save_ability or save_dc is None:
        return None
    return roll_saving_throw(target, str(save_ability), int(save_dc))


def _half_on_save(ability: dict[str, Any]) -> bool:
    if "half_on_save" in ability:
        return bool(ability.get("half_on_save"))
    text = f"{ability.get('description', '')} {ability.get('extra_effects', '')}".lower()
    return "half" in text or "save for half" in text or "successful save" in text


def _enemy_target_state(enemy: dict[str, Any]) -> dict[str, Any]:
    hp = enemy.get("hp_current", 0)
    return {
        "target_id": enemy.get("id"),
        "target_name": enemy.get("name", "Enemy"),
        "hp_current": hp,
        "new_hp": hp,
        "conditions": enemy.get("conditions", []),
        "condition_durations": enemy.get("condition_durations", {}),
        "life_state": "dead" if hp <= 0 else "alive",
    }


async def _check_party_combat_outcome(db, session, enemies: list[dict[str, Any]], all_characters: list[dict[str, Any]]):
    party_hps = []
    for character in all_characters:
        character_id = character.get("id")
        if not character_id:
            continue
        db_character = await db.get(Character, str(character_id))
        party_hps.append(db_character.hp_current if db_character else int(character.get("hp_current") or 0))
    return svc.check_combat_over(enemies, max(party_hps, default=0))


def _special_narration(
    *,
    actor_name: str,
    ability: dict[str, Any],
    target_name: str,
    damage: int,
    damage_type: str,
    save_detail: dict[str, Any] | None,
    reason: str,
) -> str:
    save_text = ""
    if save_detail:
        outcome = "succeeds" if save_detail.get("success") else "fails"
        save_text = f" {target_name} {outcome} a DC {save_detail.get('dc')} {save_detail.get('ability')} save."
    reason_text = f" ({reason})" if reason else ""
    return (
        f"{actor_name} uses {ability.get('name', 'a special ability')} on {target_name}, "
        f"dealing {damage} {damage_type} damage.{save_text}{reason_text}"
    )


def _normalize_name(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


def _safe_flag_modified(instance: Any, field: str) -> None:
    try:
        flag_modified(instance, field)
    except Exception:
        pass


def _save_turn_state(combat: Any, entity_id: str, turn_state: dict[str, Any]) -> None:
    states = dict(getattr(combat, "turn_states", None) or {})
    states[str(entity_id)] = turn_state
    combat.turn_states = states
    _safe_flag_modified(combat, "turn_states")
