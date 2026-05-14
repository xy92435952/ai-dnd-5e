"""
api.combat.attack_damage — compatibility exports for attack damage helpers.
"""
from services.combat_attack_damage_service import (
    AttackDamageResolution,
    DamageExtraResult,
    PendingDamageRoll,
    apply_basic_damage_bonuses,
    apply_divine_fury,
    apply_sneak_attack,
    apply_attack_damage_to_target,
    apply_target_resistance,
    find_pending_attack,
    resolve_damage_extras,
    resolve_pending_attack_damage,
    roll_pending_damage,
)

__all__ = [
    "AttackDamageResolution",
    "DamageExtraResult",
    "PendingDamageRoll",
    "apply_basic_damage_bonuses",
    "apply_divine_fury",
    "apply_sneak_attack",
    "apply_attack_damage_to_target",
    "apply_target_resistance",
    "find_pending_attack",
    "resolve_damage_extras",
    "resolve_pending_attack_damage",
    "roll_pending_damage",
]
