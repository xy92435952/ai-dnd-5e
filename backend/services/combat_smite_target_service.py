SMITE_EXTRA_DAMAGE_TYPES = (
    "undead",
    "fiend",
    "\u4ea1\u7075",
    "\u4e0d\u6b7b",
    "\u90aa\u9b54",
    "\u6076\u9b54",
    "\u9b54\u9b3c",
    "\u70bc\u72f1",
)


def target_gets_divine_smite_extra_damage(target: dict | None) -> bool:
    if not isinstance(target, dict):
        return False
    values = [
        target.get("type"),
        target.get("creature_type"),
        target.get("creatureType"),
        target.get("monster_type"),
        target.get("monsterType"),
        target.get("category"),
    ]
    text = " ".join(str(value or "") for value in values).lower()
    return any(token in text for token in SMITE_EXTRA_DAMAGE_TYPES)
