"""
api.combat.attack_targeting — compatibility exports for attack target helpers.
"""
from services.combat_attack_targeting_service import (
    AttackTarget,
    get_target_conditions,
    resolve_attack_target,
)

__all__ = [
    "AttackTarget",
    "get_target_conditions",
    "resolve_attack_target",
]
