"""
api.combat.pending_spells — compatibility exports for two-step spell helpers.
"""
from services.combat_pending_spell_service import (
    build_pending_spell,
    complete_pending_spell,
    find_pending_spell,
    store_pending_spell,
)

__all__ = [
    "build_pending_spell",
    "complete_pending_spell",
    "find_pending_spell",
    "store_pending_spell",
]
