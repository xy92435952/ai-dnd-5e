"""
api.combat.spell_effects — compatibility exports for spell effect helpers.
"""
from services.combat_spell_effect_service import (
    SPELL_CONDITIONS,
    apply_control_spell_to_target,
    apply_resurrection_spell_to_target,
    apply_frontend_dice_override,
    apply_spell_damage_to_target,
    apply_spell_heal_to_target,
    apply_armor_of_agathys_to_target,
    get_resurrection_spell_config,
    resolve_spell_condition_duration,
    spell_applies_condition,
    resolve_spell_condition,
    roll_spell_save,
)

__all__ = [
    "SPELL_CONDITIONS",
    "apply_control_spell_to_target",
    "apply_resurrection_spell_to_target",
    "apply_frontend_dice_override",
    "apply_spell_damage_to_target",
    "apply_spell_heal_to_target",
    "apply_armor_of_agathys_to_target",
    "get_resurrection_spell_config",
    "resolve_spell_condition_duration",
    "spell_applies_condition",
    "resolve_spell_condition",
    "roll_spell_save",
]
