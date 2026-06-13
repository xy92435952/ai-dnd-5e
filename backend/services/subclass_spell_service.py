from services.dnd_data import SUBCLASS_BONUS_SPELLS


SUBCLASS_BONUS_SPELL_ALIASES = {
    "Life": "Life Domain",
    "Light": "Light Domain",
    "War": "War Domain",
    "Fiend": "The Fiend",
    "Archfey": "The Archfey",
    "Great Old One": "The Great Old One",
}


def subclass_bonus_spell_key(subclass: str | None) -> str | None:
    requested = (subclass or "").strip()
    if not requested:
        return None
    if requested in SUBCLASS_BONUS_SPELLS:
        return requested
    if requested in SUBCLASS_BONUS_SPELL_ALIASES:
        return SUBCLASS_BONUS_SPELL_ALIASES[requested]
    requested_lower = requested.lower()
    for key in SUBCLASS_BONUS_SPELLS:
        if key.lower() == requested_lower:
            return key
    for alias, key in SUBCLASS_BONUS_SPELL_ALIASES.items():
        if alias.lower() == requested_lower:
            return key
    return None


def raw_subclass_bonus_spell_names(
    subclass: str | None,
    *,
    level: int | None = None,
) -> list[str]:
    key = subclass_bonus_spell_key(subclass)
    if not key:
        return []

    names: list[str] = []
    for threshold, spells in sorted(SUBCLASS_BONUS_SPELLS.get(key, {}).items()):
        if level is not None and int(threshold) > int(level):
            continue
        names.extend(spells)
    return names


def spell_registry_by_name_or_alias(spell_service) -> dict[str, dict]:
    registry: dict[str, dict] = {}
    for spell in spell_service.get_all():
        name = spell.get("name")
        if name:
            registry[str(name)] = spell
        name_en = spell.get("name_en")
        if name_en:
            registry[str(name_en)] = spell
    return registry


def resolve_spell_by_name_or_alias(spell_service, spell_name: str) -> dict | None:
    return spell_registry_by_name_or_alias(spell_service).get(spell_name)


def resolved_spell_details_for_names(spell_service, spell_names: list[str]) -> list[dict]:
    details = []
    seen = set()
    registry = spell_registry_by_name_or_alias(spell_service)
    for spell_name in spell_names:
        spell = registry.get(spell_name)
        if not spell:
            continue
        canonical_name = spell.get("name")
        if not canonical_name or canonical_name in seen:
            continue
        seen.add(canonical_name)
        details.append(
            {
                "name": canonical_name,
                "name_en": spell.get("name_en"),
                "level": spell.get("level", 0),
            }
        )
    return details


def resolved_subclass_bonus_spell_details(
    spell_service,
    subclass: str | None,
    *,
    level: int | None = None,
) -> list[dict]:
    return resolved_spell_details_for_names(
        spell_service,
        raw_subclass_bonus_spell_names(subclass, level=level),
    )


def all_subclass_bonus_spell_details(spell_service) -> dict:
    details = {
        subclass: {
            str(level): resolved_spell_details_for_names(
                spell_service,
                spells,
            )
            for level, spells in sorted(levels.items())
        }
        for subclass, levels in SUBCLASS_BONUS_SPELLS.items()
    }

    for alias, key in SUBCLASS_BONUS_SPELL_ALIASES.items():
        if key in details:
            details[alias] = details[key]
    return details


def available_spells_with_subclass_bonus(
    spell_service,
    char_class: str,
    subclass: str | None,
    *,
    level: int | None = None,
) -> list[dict]:
    spells = list(spell_service.get_for_class(char_class))
    seen = {spell.get("name") for spell in spells if spell.get("name")}
    for bonus_spell in resolved_subclass_bonus_spell_details(
        spell_service,
        subclass,
        level=level,
    ):
        if bonus_spell["name"] in seen:
            continue
        spell = resolve_spell_by_name_or_alias(spell_service, bonus_spell["name"])
        spells.append(spell or bonus_spell)
        seen.add(bonus_spell["name"])
    return spells
