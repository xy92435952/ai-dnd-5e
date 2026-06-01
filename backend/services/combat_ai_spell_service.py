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
from services.combat_service import CombatService
from services.dnd_rules import can_receive_ordinary_healing, roll_dice
from services.spell_service import spell_service

svc = CombatService()


def _caster_id(caster) -> str | None:
    if isinstance(caster, dict):
        value = caster.get("id")
    else:
        value = getattr(caster, "id", None)
    return str(value) if value is not None else None


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

    if spell_type == "heal" and spell_target:
        target_character = await db.get(Character, spell_target)
        if target_character and not can_receive_ordinary_healing(target_character):
            return None
        target_enemy = next(
            (enemy for enemy in enemies if str(enemy.get("id")) == str(spell_target)),
            None,
        )
        if target_enemy and not can_receive_ordinary_healing(target_enemy):
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
