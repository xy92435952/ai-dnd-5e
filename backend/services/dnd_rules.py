"""
DnD 5e 规则计算引擎兼容入口。
具体实现已拆分到 dnd_data / dnd_character_rules / dnd_derived / dnd_dice 等模块。
"""

from services.dnd_data import *  # noqa: F401,F403
from services.dnd_character_rules import (  # noqa: F401
    _normalize_class,
    ability_modifier,
    apply_racial_bonuses,
    calc_hit_dice_pool,
    calc_passive_perception,
    apply_character_damage,
    apply_character_healing,
    clamp_current_hp_to_effective_max,
    default_death_saves,
    get_effective_derived,
    get_effective_hp_base,
    get_effective_hp_max,
    get_cantrips_count,
    get_class_resource_defaults,
    get_exhaustion_effects,
    get_exhaustion_level,
    get_incapacitating_reasons,
    get_life_state,
    get_spell_slots,
    has_exhaustion_effect,
    is_dead,
    is_dying,
    is_incapacitated,
    proficiency_bonus,
    stabilize_character,
)
from services.dnd_derived import calc_derived  # noqa: F401
from services.dnd_dice import (  # noqa: F401
    roll_advantage,
    roll_attack,
    roll_dice,
    roll_dice_gwf,
    roll_disadvantage,
    roll_initiative,
    roll_saving_throw,
    roll_skill_check,
)
from services.dnd_items import get_item_zh  # noqa: F401
from services.dnd_wild_magic import roll_wild_magic_surge  # noqa: F401
