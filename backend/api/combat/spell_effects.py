"""
api.combat.spell_effects — compatibility exports for spell effect helpers.
"""
from services.combat_spell_effect_service import (
    SPELL_CONDITIONS,
    apply_control_spell_to_target,
    apply_frontend_dice_override,
    apply_spell_damage_to_target,
    apply_spell_heal_to_target,
    resolve_spell_condition,
    roll_spell_save,
)

__all__ = [
    "SPELL_CONDITIONS",
    "apply_control_spell_to_target",
    "apply_frontend_dice_override",
    "apply_spell_damage_to_target",
    "apply_spell_heal_to_target",
    "resolve_spell_condition",
    "roll_spell_save",
]
