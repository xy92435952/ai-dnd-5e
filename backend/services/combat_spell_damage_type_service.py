from typing import Any

from services.combat_damage_service import normalize_damage_type


SPELL_DAMAGE_TYPE_BY_NAME = {
    "acid splash": "acid",
    "burning hands": "fire",
    "chain lightning": "lightning",
    "chill touch": "necrotic",
    "cone of cold": "cold",
    "delayed blast fireball": "fire",
    "disintegrate": "force",
    "divine smite": "radiant",
    "eldritch blast": "force",
    "finger of death": "necrotic",
    "fire bolt": "fire",
    "fireball": "fire",
    "flame strike": "fire",
    "guardian of faith": "radiant",
    "guiding bolt": "radiant",
    "heat metal": "fire",
    "hellish rebuke": "fire",
    "ice storm": "cold",
    "inflict wounds": "necrotic",
    "lightning bolt": "lightning",
    "magic missile": "force",
    "meteor swarm": "fire",
    "moonbeam": "radiant",
    "poison spray": "poison",
    "ray of frost": "cold",
    "sacred flame": "radiant",
    "shadow blade": "psychic",
    "shatter": "thunder",
    "shocking grasp": "lightning",
    "spirit guardians": "radiant",
    "spiritual weapon": "force",
    "thorn whip": "piercing",
    "thunderwave": "thunder",
    "toll the dead": "necrotic",
    "vampiric touch": "necrotic",
    "vicious mockery": "psychic",
}


DAMAGE_TYPE_KEYWORDS = (
    ("力场", "force"),
    ("force", "force"),
    ("火焰", "fire"),
    ("fire", "fire"),
    ("冰冷", "cold"),
    ("cold", "cold"),
    ("闪电", "lightning"),
    ("lightning", "lightning"),
    ("雷鸣", "thunder"),
    ("thunder", "thunder"),
    ("辐射", "radiant"),
    ("光耀", "radiant"),
    ("radiant", "radiant"),
    ("坏死", "necrotic"),
    ("necrotic", "necrotic"),
    ("毒素", "poison"),
    ("poison", "poison"),
    ("酸液", "acid"),
    ("acid", "acid"),
    ("心灵", "psychic"),
    ("精神", "psychic"),
    ("psychic", "psychic"),
    ("穿刺", "piercing"),
    ("piercing", "piercing"),
    ("钝击", "bludgeoning"),
    ("bludgeoning", "bludgeoning"),
    ("挥砍", "slashing"),
    ("挥斩", "slashing"),
    ("slashing", "slashing"),
)


def _spell_names(spell_name: str | None, spell: dict[str, Any] | None) -> list[str]:
    names = [spell_name] if spell_name else []
    if spell:
        for key in ("name", "name_en"):
            value = spell.get(key)
            if value and value not in names:
                names.append(value)
    return names


def resolve_spell_damage_type(
    spell_name: str | None,
    spell: dict[str, Any] | None,
) -> str | None:
    """Infer a canonical damage type for a spell from explicit data, name, or description."""
    spell = spell or {}
    explicit = spell.get("damage_type")
    if explicit:
        return normalize_damage_type(explicit)

    explicit_types = spell.get("damage_types")
    if explicit_types:
        if isinstance(explicit_types, str):
            return normalize_damage_type(explicit_types)
        for value in explicit_types:
            normalized = normalize_damage_type(value)
            if normalized:
                return normalized

    for name in _spell_names(spell_name, spell):
        mapped = SPELL_DAMAGE_TYPE_BY_NAME.get(str(name).strip().lower())
        if mapped:
            return mapped

    desc = str(spell.get("desc") or "").lower()
    for keyword, damage_type in DAMAGE_TYPE_KEYWORDS:
        if keyword.lower() in desc:
            return damage_type
    return None
