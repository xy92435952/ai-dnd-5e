"""Subclass progression helpers shared by derived stats and class resources."""

SUBCLASS_UNLOCK_LEVELS: dict[str, int] = {
    "Barbarian": 3,
    "Bard": 3,
    "Cleric": 1,
    "Druid": 2,
    "Fighter": 3,
    "Monk": 3,
    "Paladin": 3,
    "Ranger": 3,
    "Rogue": 3,
    "Sorcerer": 1,
    "Warlock": 1,
    "Wizard": 2,
}

SUBCLASS_OPTIONS: dict[str, list[str]] = {
    "Barbarian": ["Berserker", "Totem Warrior", "Storm Herald", "Zealot"],
    "Bard": ["Lore", "Valor", "Glamour", "Swords"],
    "Cleric": ["Life", "Light", "War", "Knowledge", "Trickery", "Nature", "Tempest"],
    "Druid": ["Land", "Moon", "Spores"],
    "Fighter": ["Champion", "Battle Master", "Eldritch Knight", "Samurai"],
    "Monk": ["Open Hand", "Shadow", "Four Elements", "Drunken Master"],
    "Paladin": ["Devotion", "Ancients", "Vengeance", "Glory"],
    "Ranger": ["Hunter", "Beast Master", "Gloom Stalker", "Swarmkeeper"],
    "Rogue": ["Thief", "Assassin", "Arcane Trickster", "Swashbuckler"],
    "Sorcerer": ["Draconic", "Wild Magic", "Storm", "Divine Soul"],
    "Warlock": ["Fiend", "Archfey", "Great Old One", "Hexblade"],
    "Wizard": [
        "Evocation",
        "Abjuration",
        "Illusion",
        "Necromancy",
        "Conjuration",
        "Divination",
        "Enchantment",
        "Transmutation",
    ],
}


def subclass_unlock_level(cls_key: str) -> int:
    key = (cls_key or "").strip()
    canonical_key = key[:1].upper() + key[1:].lower()
    return SUBCLASS_UNLOCK_LEVELS.get(canonical_key, 3)


def subclass_unlocked(cls_key: str, level: int) -> bool:
    try:
        current_level = int(level or 0)
    except (TypeError, ValueError):
        current_level = 0
    return current_level >= subclass_unlock_level(cls_key)


def subclass_options_for_class(cls_key: str) -> list[str]:
    key = (cls_key or "").strip()
    canonical_key = key[:1].upper() + key[1:].lower()
    return list(SUBCLASS_OPTIONS.get(canonical_key, []))


def canonical_subclass_choice(cls_key: str, subclass: str | None) -> str | None:
    requested = (subclass or "").strip()
    if not requested:
        return None
    for option in subclass_options_for_class(cls_key):
        if option.lower() == requested.lower():
            return option
    return None
