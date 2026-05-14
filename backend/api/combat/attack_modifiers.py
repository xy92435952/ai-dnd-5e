"""
api.combat.attack_modifiers — compatibility exports for attack roll modifier helpers.
"""
from services.combat_attack_modifier_service import (
    FeatPowerAttack,
    WeaponDamageDice,
    apply_ranged_close_penalty,
    build_attack_deriveds,
    build_weapon_damage_dice,
    calculate_cover_bonus,
    choose_feat_power_attack,
)

__all__ = [
    "FeatPowerAttack",
    "WeaponDamageDice",
    "apply_ranged_close_penalty",
    "build_attack_deriveds",
    "build_weapon_damage_dice",
    "calculate_cover_bonus",
    "choose_feat_power_attack",
]
