from services.dnd_rules import (
    ALIGNMENTS,
    ALL_LANGUAGES,
    ALL_SKILLS,
    ARMOR,
    ASI_LEVELS,
    ASI_LEVELS_FIGHTER,
    ASI_LEVELS_ROGUE,
    BACKGROUNDS,
    BACKGROUND_EQUIPMENT,
    BACKGROUND_FEATURES,
    CLASSES,
    CLASS_ARMOR_PROFICIENCY,
    CLASS_SAVE_PROFICIENCIES,
    CLASS_SKILL_CHOICES,
    CLASS_WEAPON_PROFICIENCY,
    FEATS,
    FIGHTING_STYLES,
    FIGHTING_STYLE_CLASSES,
    RACIAL_ABILITY_BONUSES,
    RACIAL_LANGUAGES,
    RACES,
    SPELLCASTER_CLASSES,
    SPELL_PREPARATION_TYPE,
    STARTING_EQUIPMENT,
    STARTING_GEAR_PACKS,
    STARTING_SPELLS_COUNT,
    SUBCLASS_BONUS_SPELLS,
    WEAPONS,
    get_cantrips_count,
    get_item_zh,
)


def build_character_options(spell_service) -> dict:
    class_cantrips = {
        cls: [spell["name"] for spell in spell_service.get_cantrips_for_class(cls)]
        for cls in SPELLCASTER_CLASSES
    }
    class_spells = {
        cls: [spell["name"] for spell in spell_service.get_for_class(cls) if spell["level"] > 0]
        for cls in SPELLCASTER_CLASSES
    }
    starting_cantrips_count = {
        cls: get_cantrips_count(cls, 1)
        for cls in SPELLCASTER_CLASSES
    }

    return {
        "races": RACES,
        "classes": CLASSES,
        "backgrounds": BACKGROUNDS,
        "alignments": ALIGNMENTS,
        "racial_bonuses": RACIAL_ABILITY_BONUSES,
        "class_skill_choices": CLASS_SKILL_CHOICES,
        "class_save_proficiencies": CLASS_SAVE_PROFICIENCIES,
        "all_skills": ALL_SKILLS,
        "class_cantrips": class_cantrips,
        "class_spells": class_spells,
        "starting_cantrips_count": starting_cantrips_count,
        "starting_spells_count": STARTING_SPELLS_COUNT,
        "spellcaster_classes": SPELLCASTER_CLASSES,
        "fighting_styles": FIGHTING_STYLES,
        "fighting_style_classes": FIGHTING_STYLE_CLASSES,
        "weapons": WEAPONS,
        "armor": ARMOR,
        "starting_equipment": STARTING_EQUIPMENT,
        "starting_gear_packs": build_starting_gear_pack_options(),
        "background_equipment": build_background_equipment_options(),
        "background_features": BACKGROUND_FEATURES,
        "racial_languages": RACIAL_LANGUAGES,
        "all_languages": ALL_LANGUAGES,
        "spell_preparation_type": SPELL_PREPARATION_TYPE,
        "subclass_bonus_spells": SUBCLASS_BONUS_SPELLS,
        "feats": FEATS,
        "asi_levels": ASI_LEVELS,
        "asi_levels_fighter": ASI_LEVELS_FIGHTER,
        "asi_levels_rogue": ASI_LEVELS_ROGUE,
        "class_armor_proficiency": CLASS_ARMOR_PROFICIENCY,
        "class_weapon_proficiency": CLASS_WEAPON_PROFICIENCY,
    }


def build_starting_gear_pack_options() -> dict:
    return {
        pack_name: [
            {"name": item_name, "zh": get_item_zh(item_name), "quantity": quantity}
            for item_name, quantity in items
        ]
        for pack_name, items in STARTING_GEAR_PACKS.items()
    }


def build_background_equipment_options() -> dict:
    return {
        background: {
            "gold": config.get("gold", 0),
            "items": [
                {"name": item_name, "zh": get_item_zh(item_name), "quantity": quantity}
                for item_name, quantity in config.get("items", [])
            ],
        }
        for background, config in BACKGROUND_EQUIPMENT.items()
    }
