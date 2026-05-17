from typing import Any, Callable

from sqlalchemy.orm.attributes import flag_modified

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
from services.dnd_rules import roll_dice
from services.spell_service import spell_service

svc = CombatService()


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
    spell_level = decision.get("spell_level") or 1
    spell_target = decided_target_id
    spell_data = spell_service_obj.get(spell_name)
    if not spell_data:
        return None

    spell_mod = _spell_modifier(actor_derived)
    spell_save_dc = actor_derived.get("spell_save_dc", 13)
    bonus_healing = actor_derived.get("bonus_healing", False)
    is_cantrip = spell_data.get("level", 0) == 0
    spell_type = spell_data.get("type", "damage")

    if not is_cantrip and caster:
        if not consume_ai_spell_slot(caster, spell_level):
            return None

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
        )
    elif spell_type in ("control", "utility"):
        await _apply_ai_control_spell(
            db,
            resolution=resolution,
            session=session,
            enemies=enemies,
            spell_save_dc=spell_save_dc,
            state=state,
            flag_modified_func=flag_modified_func,
            roll_dice_func=roll_dice_func,
        )

    if spell_data.get("concentration") and caster:
        caster.concentration = spell_name

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
    "resolve_ai_spell_action",
]
