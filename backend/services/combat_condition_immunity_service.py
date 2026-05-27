from typing import Any, Iterable


CONDITION_ALIASES = {
    "blind": "blinded",
    "blinded": "blinded",
    "目盲": "blinded",
    "charm": "charmed",
    "charmed": "charmed",
    "魅惑": "charmed",
    "deaf": "deafened",
    "deafened": "deafened",
    "耳聋": "deafened",
    "fear": "frightened",
    "frightened": "frightened",
    "恐惧": "frightened",
    "grapple": "grappled",
    "grappled": "grappled",
    "擒抱": "grappled",
    "incapacitated": "incapacitated",
    "失能": "incapacitated",
    "invisible": "invisible",
    "隐形": "invisible",
    "paralyze": "paralyzed",
    "paralyzed": "paralyzed",
    "麻痹": "paralyzed",
    "petrified": "petrified",
    "石化": "petrified",
    "poison": "poisoned",
    "poisoned": "poisoned",
    "中毒": "poisoned",
    "prone": "prone",
    "倒地": "prone",
    "restrain": "restrained",
    "restrained": "restrained",
    "束缚": "restrained",
    "stun": "stunned",
    "stunned": "stunned",
    "震慑": "stunned",
    "昏迷": "unconscious",
    "unconscious": "unconscious",
    "exhaustion": "exhaustion",
    "力竭": "exhaustion",
}


def normalize_condition(condition: str | None) -> str:
    value = str(condition or "").strip()
    if not value:
        return ""
    return CONDITION_ALIASES.get(value.lower(), CONDITION_ALIASES.get(value, value.lower()))


def normalized_conditions(values: Iterable | None) -> set[str]:
    return {
        normalized
        for normalized in (normalize_condition(value) for value in (values or []))
        if normalized
    }


def entity_condition_immunities(entity: Any) -> set[str]:
    if isinstance(entity, dict):
        values = list(entity.get("condition_immunities") or [])
        for value in entity.get("immunities") or []:
            normalized = normalize_condition(value)
            if normalized:
                values.append(normalized)
        return normalized_conditions(values)

    class_resources = getattr(entity, "class_resources", None) or {}
    values = list(getattr(entity, "condition_immunities", None) or [])
    values.extend(class_resources.get("condition_immunities") or [])
    return normalized_conditions(values)


def is_condition_immune(entity: Any, condition: str | None) -> bool:
    normalized = normalize_condition(condition)
    return bool(normalized and normalized in entity_condition_immunities(entity))
