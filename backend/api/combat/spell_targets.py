"""
api.combat.spell_targets — compatibility exports for spell target helpers.
"""
from services.combat_spell_target_service import (
    collect_spell_target_ids,
    collect_spell_target_names,
    parse_spell_range_ft,
    parse_spell_range_tiles,
    validate_spell_range,
)

__all__ = [
    "collect_spell_target_ids",
    "collect_spell_target_names",
    "parse_spell_range_ft",
    "parse_spell_range_tiles",
    "validate_spell_range",
]
