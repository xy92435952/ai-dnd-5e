from typing import Any

from services.dnd_rules import get_effective_derived, get_effective_hp_base


def serialize_character(char: Any) -> dict:
    derived = get_effective_derived(char)
    base_hp_max = get_effective_hp_base(char, char.derived or {})
    return {
        "id": char.id,
        "is_player": char.is_player,
        "name": char.name,
        "race": char.race,
        "char_class": char.char_class,
        "subclass": char.subclass,
        "level": char.level,
        "background": char.background,
        "alignment": char.alignment,
        "ability_scores": char.ability_scores,
        "derived": derived,
        "hp_current": char.hp_current,
        "hp_max": derived.get("hp_max", char.hp_current),
        "base_hp_max": base_hp_max,
        "ac": derived.get("ac", 10),
        "spell_slots": char.spell_slots or {},
        "spell_slots_max": derived.get("spell_slots_max", {}),
        "known_spells": char.known_spells or [],
        "prepared_spells": char.prepared_spells or [],
        "cantrips": char.cantrips or [],
        "concentration": char.concentration,
        "caster_type": derived.get("caster_type"),
        "cantrips_count": derived.get("cantrips_count", 0),
        "proficient_skills": char.proficient_skills or [],
        "proficient_saves": char.proficient_saves or [],
        "equipment": char.equipment or {},
        "fighting_style": char.fighting_style,
        "languages": char.languages or [],
        "tool_proficiencies": char.tool_proficiencies or [],
        "feats": char.feats or [],
        "conditions": char.conditions or [],
        "death_saves": char.death_saves,
        "personality": char.personality,
        "speech_style": char.speech_style,
        "combat_preference": char.combat_preference,
        "backstory": char.backstory,
        "catchphrase": char.catchphrase,
        "multiclass_info": char.multiclass_info,
        "subclass_effects": derived.get("subclass_effects", {}),
        "condition_durations": char.condition_durations or {},
    }
