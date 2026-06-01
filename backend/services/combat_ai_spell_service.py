from typing import Any, Callable

from sqlalchemy.orm.attributes import flag_modified

from models import Character
from services.combat_concentration_effect_service import set_concentration_with_cleanup
from services.combat_ai_spell_damage_service import (
    apply_ai_damage_spell as _apply_ai_damage_spell,
    damage_after_ai_enemy_save as _damage_after_ai_enemy_save,
    damage_after_ai_save as _damage_after_ai_save,
    damage_enemy as _damage_enemy,
)
from services.combat_ai_spell_effect_service import (
    apply_ai_control_spell as _apply_ai_control_spell,
    apply_ai_heal_spell as _apply_ai_heal_spell,
)
from services.combat_ai_spell_models import (
    CONTROL_CONDITION_MAP,
    SLOT_KEYS,
    AiSpellResolution,
    build_ai_spell_narration,
    consume_ai_spell_slot,
    spell_modifier as _spell_modifier,
)
from services.combat_condition_service import get_attack_modifiers, get_defense_modifiers
from services.combat_grid_service import chebyshev_distance
from services.combat_service import CombatService
from services.combat_spell_roll_service import (
    build_spell_ability_context,
    spell_attack_is_ranged,
    spell_requires_attack_roll,
)
from services.combat_spell_target_service import parse_spell_range_tiles
from services.dnd_rules import can_receive_ordinary_healing, roll_attack, roll_dice
from services.spell_service import spell_service

svc = CombatService()


def _caster_id(caster) -> str | None:
    if isinstance(caster, dict):
        value = caster.get("id")
    else:
        value = getattr(caster, "id", None)
    return str(value) if value is not None else None


def _entity_field(entity, key: str, default=None):
    if isinstance(entity, dict):
        return entity.get(key, default)
    return getattr(entity, key, default)


def _entity_conditions(entity) -> list[str]:
    return list(_entity_field(entity, "conditions", []) or [])


def _entity_derived(entity) -> dict[str, Any]:
    return dict(_entity_field(entity, "derived", {}) or {})


def _entity_name(entity) -> str:
    return str(_entity_field(entity, "name", "") or "")


def resolve_ai_spell_level(decision: dict[str, Any], spell_data: dict[str, Any]) -> int:
    base_level = int(spell_data.get("level") or 0)
    requested_level = decision.get("spell_level")
    if requested_level is None:
        return base_level
    try:
        requested_level = int(requested_level)
    except (TypeError, ValueError):
        requested_level = base_level
    return max(base_level, requested_level)


def consume_named_spell_slot(caster, slot_key: str) -> bool:
    if isinstance(caster, dict):
        slots = dict(caster.get("spell_slots") or {})
    else:
        slots = dict(getattr(caster, "spell_slots", None) or {})
    if int(slots.get(slot_key) or 0) <= 0:
        return False
    slots[slot_key] -= 1
    if isinstance(caster, dict):
        caster["spell_slots"] = slots
    else:
        caster.spell_slots = slots
    return True


def _has_valid_ai_damage_target(
    target_id: str | None,
    *,
    is_enemy: bool,
    enemies_alive: list[dict[str, Any]],
    all_characters: list[dict[str, Any]],
) -> bool:
    if not target_id:
        return False
    target = str(target_id)
    legal_targets = all_characters if is_enemy else enemies_alive
    return any(
        str(item.get("id")) == target and int(item.get("hp_current", 0) or 0) > 0
        for item in legal_targets
    )


def _find_entity_by_id(items: list[dict[str, Any]], target_id: str | None):
    if not target_id:
        return None
    target = str(target_id)
    return next((item for item in items if str(item.get("id")) == target), None)


async def _has_valid_ai_heal_target(
    db,
    target_id: str | None,
    *,
    is_enemy: bool,
    enemies: list[dict[str, Any]],
    all_characters: list[dict[str, Any]],
) -> bool:
    if not target_id:
        return False
    if is_enemy:
        target_enemy = _find_entity_by_id(enemies, target_id)
        return bool(target_enemy and can_receive_ordinary_healing(target_enemy))

    if _find_entity_by_id(enemies, target_id):
        return False
    target_character = await db.get(Character, target_id)
    if target_character:
        return can_receive_ordinary_healing(target_character)
    target_snapshot = _find_entity_by_id(all_characters, target_id)
    return bool(target_snapshot and can_receive_ordinary_healing(target_snapshot))


def _has_valid_ai_control_target(
    target_id: str | None,
    *,
    is_enemy: bool,
    enemies_alive: list[dict[str, Any]],
    all_characters: list[dict[str, Any]],
) -> bool:
    if not target_id:
        return False
    legal_targets = all_characters if is_enemy else enemies_alive
    return any(
        str(item.get("id")) == str(target_id) and int(item.get("hp_current", 0) or 0) > 0
        for item in legal_targets
    )


def _ai_spell_target_in_range(
    caster,
    target_id: str | None,
    spell_data: dict[str, Any],
    positions: dict[str, Any] | None,
) -> bool:
    if not target_id or not positions:
        return True
    caster_id = _caster_id(caster)
    if not caster_id:
        return True
    caster_pos = positions.get(str(caster_id))
    target_pos = positions.get(str(target_id))
    if not caster_pos or not target_pos:
        return True
    spell_range_tiles = parse_spell_range_tiles(spell_data.get("range"))
    if spell_range_tiles <= 0:
        return chebyshev_distance(caster_pos, target_pos) <= 0
    return chebyshev_distance(caster_pos, target_pos) <= spell_range_tiles


def _find_ai_spell_attack_target_snapshot(
    target_id: str | None,
    enemies: list[dict[str, Any]],
    all_characters: list[dict[str, Any]],
):
    if not target_id:
        return None
    target = str(target_id)
    for enemy in enemies:
        if str(enemy.get("id")) == target:
            return enemy
    for character in all_characters:
        if str(character.get("id")) == target:
            return character
    return None


async def _resolve_ai_spell_attack_target(
    db,
    target_id: str | None,
    enemies: list[dict[str, Any]],
    all_characters: list[dict[str, Any]],
):
    target = _find_ai_spell_attack_target_snapshot(target_id, enemies, all_characters)
    if target is not None:
        return target
    if not target_id:
        return None
    return await db.get(Character, target_id)


async def _roll_ai_spell_attack(
    db,
    *,
    caster,
    actor_derived: dict[str, Any],
    spell_name: str,
    spell_data: dict[str, Any],
    spell_target: str | None,
    enemies: list[dict[str, Any]],
    all_characters: list[dict[str, Any]],
    positions: dict[str, Any] | None,
    grid_data: dict[str, Any] | None,
    turn_states: dict[str, Any] | None,
    roll_dice_func: Callable[[str], dict[str, Any]],
) -> tuple[dict[str, Any] | None, str]:
    if not spell_target or spell_data.get("aoe", False):
        return None, ""
    if not spell_requires_attack_roll(spell_name, spell_data):
        return None, ""

    target = await _resolve_ai_spell_attack_target(db, spell_target, enemies, all_characters)
    if target is None:
        return None, ""

    target_conditions = _entity_conditions(target)
    target_turn_state = (turn_states or {}).get(str(spell_target)) or {}
    if target_turn_state.get("dodging") and "dodging" not in target_conditions:
        target_conditions.append("dodging")

    caster_conditions = _entity_conditions(caster)
    attacker_advantage, attacker_disadvantage = get_attack_modifiers(caster_conditions, caster)
    defense_advantage, defense_disadvantage = get_defense_modifiers(target_conditions)
    is_ranged_spell_attack = spell_attack_is_ranged(spell_data)

    target_derived = _entity_derived(target)
    target_ac = _entity_field(target, "ac")
    if "ac" not in target_derived and target_ac is not None:
        target_derived["ac"] = target_ac

    cover_bonus = 0
    caster_id = _caster_id(caster)
    if is_ranged_spell_attack and caster_id and positions and grid_data:
        caster_pos = positions.get(str(caster_id))
        target_pos = positions.get(str(spell_target))
        if caster_pos and target_pos:
            cover_bonus = CombatService.get_cover_bonus(grid_data, caster_pos, target_pos)
    if cover_bonus:
        target_derived["ac"] = target_derived.get("ac", target_ac or 10) + cover_bonus

    ability_context = build_spell_ability_context(actor_derived or {})
    spell_attack_bonus = ability_context.get("spell_attack_bonus", 0)
    crit_threshold = int((actor_derived or {}).get("crit_threshold", 20) or 20)
    attack_roll = roll_attack(
        attacker={
            "derived": {
                "attack_bonus": spell_attack_bonus,
                "ranged_attack_bonus": spell_attack_bonus,
                "crit_threshold": crit_threshold,
            },
            "conditions": caster_conditions,
        },
        target={"derived": target_derived},
        is_ranged=is_ranged_spell_attack,
        advantage=attacker_advantage or defense_advantage,
        disadvantage=attacker_disadvantage or defense_disadvantage,
        crit_threshold=crit_threshold,
        d20_roller=roll_dice_func,
    )
    attack_roll.update({
        "spell_attack": True,
        "cover_bonus": cover_bonus,
        "advantage": attacker_advantage or defense_advantage,
        "disadvantage": attacker_disadvantage or defense_disadvantage,
    })
    return attack_roll, _entity_name(target)


def _persist_enemy_caster_state(
    *,
    session,
    state: dict[str, Any],
    enemies: list[dict[str, Any]],
    caster,
    flag_modified_func: Callable[[Any, str], None],
) -> None:
    if not isinstance(caster, dict):
        return
    state["enemies"] = enemies
    session.game_state = dict(state)
    flag_modified_func(session, "game_state")


async def resolve_ai_spell_action(
    db,
    *,
    session,
    actor_name: str,
    is_enemy: bool,
    caster,
    actor_derived: dict[str, Any],
    decided_target_id: str | None,
    decided_reason: str,
    decision: dict[str, Any],
    state: dict[str, Any],
    enemies: list[dict[str, Any]],
    enemies_alive: list[dict[str, Any]],
    all_characters: list[dict[str, Any]],
    spell_service_obj=spell_service,
    combat_service: CombatService = svc,
    flag_modified_func: Callable[[Any, str], None] = flag_modified,
    roll_dice_func: Callable[[str], dict[str, Any]] = roll_dice,
    positions: dict[str, Any] | None = None,
    grid_data: dict[str, Any] | None = None,
    turn_states: dict[str, Any] | None = None,
) -> AiSpellResolution | None:
    """Resolve the AI spell branch and mutate combat state like the legacy endpoint did."""
    if not (decision.get("action_type") == "spell" and decision.get("action_name")):
        return None

    spell_name = decision["action_name"]
    spell_target = decided_target_id
    spell_data = spell_service_obj.get(spell_name)
    if not spell_data:
        return None
    spell_level = resolve_ai_spell_level(decision, spell_data)

    spell_mod = _spell_modifier(actor_derived)
    spell_save_dc = actor_derived.get("spell_save_dc", 13)
    bonus_healing = actor_derived.get("bonus_healing", False)
    is_cantrip = spell_data.get("level", 0) == 0
    spell_type = spell_data.get("type", "damage")

    if (
        spell_target
        and not spell_data.get("aoe", False)
        and not _ai_spell_target_in_range(caster, spell_target, spell_data, positions)
    ):
        return None

    if (
        spell_type == "damage"
        and not spell_data.get("aoe", False)
        and not _has_valid_ai_damage_target(
            spell_target,
            is_enemy=is_enemy,
            enemies_alive=enemies_alive,
            all_characters=all_characters,
        )
    ):
        return None

    if spell_type == "heal" and not await _has_valid_ai_heal_target(
        db,
        spell_target,
        is_enemy=is_enemy,
        enemies=enemies,
        all_characters=all_characters,
    ):
        return None

    if spell_type == "control" and not _has_valid_ai_control_target(
        spell_target,
        is_enemy=is_enemy,
        enemies_alive=enemies_alive,
        all_characters=all_characters,
    ):
        return None

    if not is_cantrip and caster:
        if not consume_ai_spell_slot(caster, spell_level):
            return None
        _persist_enemy_caster_state(
            session=session,
            state=state,
            enemies=enemies,
            caster=caster,
            flag_modified_func=flag_modified_func,
        )

    caster_id = _caster_id(caster)
    if spell_data.get("concentration") and caster:
        await set_concentration_with_cleanup(
            db,
            session,
            caster,
            spell_name,
            caster_id=caster_id,
        )
        _persist_enemy_caster_state(
            session=session,
            state=state,
            enemies=enemies,
            caster=caster,
            flag_modified_func=flag_modified_func,
        )

    resolution = AiSpellResolution(
        spell_name=spell_name,
        spell_level=spell_level,
        spell_target=spell_target,
        spell_data=spell_data,
        is_cantrip=is_cantrip,
    )

    if spell_type == "damage":
        attack_roll, attack_target_name = await _roll_ai_spell_attack(
            db,
            caster=caster,
            actor_derived=actor_derived,
            spell_name=spell_name,
            spell_data=spell_data,
            spell_target=spell_target,
            enemies=enemies,
            all_characters=all_characters,
            positions=positions,
            grid_data=grid_data,
            turn_states=turn_states,
            roll_dice_func=roll_dice_func,
        )
        if attack_roll is not None:
            resolution.attack_roll = attack_roll
            resolution.spell_attack_required = True
            resolution.target_name = attack_target_name
            if not attack_roll.get("hit"):
                resolution.narration_parts.append("法术攻击检定未命中。")
            else:
                resolution.narration_parts.append("法术攻击检定命中。")
        if attack_roll is None or attack_roll.get("hit"):
            await _apply_ai_damage_spell(
                db,
                resolution=resolution,
                session=session,
                enemies=enemies,
                enemies_alive=enemies_alive,
                all_characters=all_characters,
                is_enemy=is_enemy,
                spell_mod=spell_mod,
                spell_save_dc=spell_save_dc,
                state=state,
                spell_service_obj=spell_service_obj,
                combat_service=combat_service,
                flag_modified_func=flag_modified_func,
                roll_dice_func=roll_dice_func,
            )
    elif spell_type == "heal":
        await _apply_ai_heal_spell(
            db,
            resolution=resolution,
            spell_mod=spell_mod,
            bonus_healing=bonus_healing,
            spell_service_obj=spell_service_obj,
            session=session,
            state=state,
            enemies=enemies,
            flag_modified_func=flag_modified_func,
        )
    elif spell_type in ("control", "utility"):
        await _apply_ai_control_spell(
            db,
            resolution=resolution,
            session=session,
            enemies=enemies,
            spell_save_dc=spell_save_dc,
            state=state,
            caster_id=caster_id,
            flag_modified_func=flag_modified_func,
            roll_dice_func=roll_dice_func,
        )

    resolution.mechanical_narration = build_ai_spell_narration(
        actor_name=actor_name,
        spell_name=spell_name,
        spell_level=spell_level,
        is_cantrip=is_cantrip,
        damage=resolution.damage,
        heal=resolution.heal,
        narration_parts=resolution.narration_parts,
        decided_reason=decided_reason,
    )
    return resolution


__all__ = [
    "AiSpellResolution",
    "CONTROL_CONDITION_MAP",
    "SLOT_KEYS",
    "_apply_ai_control_spell",
    "_apply_ai_damage_spell",
    "_apply_ai_heal_spell",
    "_damage_after_ai_enemy_save",
    "_damage_after_ai_save",
    "_damage_enemy",
    "_spell_modifier",
    "build_ai_spell_narration",
    "consume_ai_spell_slot",
    "consume_named_spell_slot",
    "resolve_ai_spell_action",
    "resolve_ai_spell_level",
]
