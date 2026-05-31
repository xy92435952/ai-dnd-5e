from typing import Optional

from services.dnd_rules import has_exhaustion_effect, normalize_conditions

ATTACK_ADVANTAGE_SOURCES = {
    "invisible": "attacker invisible",
    "hidden": "attacker hidden",
}

ATTACK_DISADVANTAGE_SOURCES = {
    "poisoned": "attacker poisoned",
    "frightened": "attacker frightened",
    "prone": "attacker prone",
    "blinded": "attacker blinded",
    "restrained": "attacker restrained",
}

DEFENSE_ADVANTAGE_SOURCES = {
    "paralyzed": "target paralyzed",
    "petrified": "target petrified",
    "stunned": "target stunned",
    "unconscious": "target unconscious",
    "prone": "target prone",
    "blinded": "target blinded",
    "restrained": "target restrained",
    "faerie_fire": "target faerie fire",
    "guiding_bolt": "target guiding bolt",
}

DEFENSE_DISADVANTAGE_SOURCES = {
    "invisible": "target invisible",
    "dodging": "target dodging",
}


def get_attack_modifiers(conditions: list[str], character: dict | object | None = None) -> tuple[bool, bool]:
    advantage_sources, disadvantage_sources = get_attack_modifier_sources(conditions, character)
    return bool(advantage_sources), bool(disadvantage_sources)


def get_defense_modifiers(conditions: list[str]) -> tuple[bool, bool]:
    advantage_sources, disadvantage_sources = get_defense_modifier_sources(conditions)
    return bool(advantage_sources), bool(disadvantage_sources)


def get_attack_modifier_sources(
    conditions: list[str],
    character: dict | object | None = None,
) -> tuple[list[str], list[str]]:
    conditions = normalize_conditions(conditions)
    advantage_sources = _condition_sources(conditions, ATTACK_ADVANTAGE_SOURCES)
    disadvantage_sources = _condition_sources(conditions, ATTACK_DISADVANTAGE_SOURCES)
    if has_exhaustion_effect(character, "attack_save_disadvantage"):
        disadvantage_sources.append("attacker exhaustion")
    return advantage_sources, disadvantage_sources


def get_defense_modifier_sources(conditions: list[str]) -> tuple[list[str], list[str]]:
    conditions = normalize_conditions(conditions)
    return (
        _condition_sources(conditions, DEFENSE_ADVANTAGE_SOURCES),
        _condition_sources(conditions, DEFENSE_DISADVANTAGE_SOURCES),
    )


def _condition_sources(conditions: list[str], source_map: dict[str, str]) -> list[str]:
    sources: list[str] = []
    for condition in conditions:
        source = source_map.get(condition)
        if source and source not in sources:
            sources.append(source)
    return sources


def check_concentration(character_dict: dict, damage: int) -> Optional[dict]:
    if not character_dict.get("concentration") or damage <= 0:
        return None

    from services.dnd_rules import roll_saving_throw
    dc = max(10, damage // 2)

    derived = character_dict.get("derived", {})
    feat_effects = derived.get("feat_effects", {})
    has_war_caster = bool(feat_effects.get("War Caster")) or derived.get("subclass_effects", {}).get("concentration_advantage", False)
    roll_result = roll_saving_throw(character_dict, "con", dc, advantage=has_war_caster)

    return {
        "required": True,
        "dc": dc,
        "spell_name": character_dict["concentration"],
        "broke": not roll_result["success"],
        "roll_result": roll_result,
        "war_caster": has_war_caster,
    }
