"""Character-level DnD rule helpers: class aliases, resources, slots, and passive stats."""

from services.dnd_data import (
    CANTRIPS_KNOWN, CASTER_TYPE, EXHAUSTION_EFFECTS, HIT_DICE,
    RACIAL_ABILITY_BONUSES, SPELL_SLOTS_FULL, SPELL_SLOTS_HALF,
    SPELL_SLOTS_WARLOCK,
)


def get_exhaustion_effects(exhaustion_level: int) -> list[str]:
    """返回当前力竭等级的所有累积效果"""
    effects = []
    for lvl in range(1, min(exhaustion_level, 6) + 1):
        effects.append(EXHAUSTION_EFFECTS[lvl])
    return effects


def get_exhaustion_level(character: dict | object | None) -> int:
    """Read a character's current 5e exhaustion level from condition_durations."""
    if not character:
        return 0
    if isinstance(character, dict):
        durations = character.get("condition_durations") or {}
    else:
        durations = getattr(character, "condition_durations", None) or {}
    try:
        return max(0, min(6, int(durations.get("exhaustion_level", 0) or 0)))
    except (TypeError, ValueError):
        return 0


def has_exhaustion_effect(character: dict | object | None, effect: str) -> bool:
    """Return whether a character's exhaustion level includes a named 5e effect."""
    return effect in get_exhaustion_effects(get_exhaustion_level(character))


def get_effective_hp_max(character: dict | object | None, base_hp_max: int | None = None) -> int:
    """Return the character's current HP maximum after exhaustion effects."""
    if isinstance(character, dict):
        derived = character.get("derived") or {}
        current_hp = character.get("hp_current", 1)
    else:
        derived = getattr(character, "derived", None) or {}
        current_hp = getattr(character, "hp_current", 1)

    raw_hp_max = base_hp_max
    if raw_hp_max is None:
        raw_hp_max = derived.get("hp_max", current_hp)
    try:
        hp_max = max(1, int(raw_hp_max or 1))
    except (TypeError, ValueError):
        hp_max = 1

    if has_exhaustion_effect(character, "hp_max_halved"):
        return max(1, hp_max // 2)
    return hp_max


def get_effective_derived(character: dict | object | None) -> dict:
    """Return derived stats with HP max adjusted for current exhaustion effects."""
    if isinstance(character, dict):
        derived = dict(character.get("derived") or {})
    else:
        derived = dict(getattr(character, "derived", None) or {})
    derived["base_hp_max"] = get_effective_hp_base(character, derived)
    derived["hp_max"] = get_effective_hp_max(character, derived["base_hp_max"])
    return derived


def get_effective_hp_base(character: dict | object | None, derived: dict | None = None) -> int:
    """Read the unmodified HP maximum used before exhaustion reductions."""
    data = derived or {}
    if not data:
        if isinstance(character, dict):
            data = character.get("derived") or {}
        else:
            data = getattr(character, "derived", None) or {}
    if isinstance(character, dict):
        current_hp = character.get("hp_current", 1)
    else:
        current_hp = getattr(character, "hp_current", 1)
    try:
        return max(1, int(data.get("hp_max", current_hp) or 1))
    except (TypeError, ValueError):
        return 1


def clamp_current_hp_to_effective_max(character: object) -> int:
    """Clamp a mutable character object's current HP to its effective maximum."""
    hp_max = get_effective_hp_max(character)
    current_hp = getattr(character, "hp_current", 0) or 0
    character.hp_current = max(0, min(int(current_hp), hp_max))
    return hp_max


def default_death_saves(*, stable: bool = False, failures: int = 0, successes: int = 0) -> dict:
    """Return a normalized death-save state."""
    return {
        "successes": max(0, min(3, int(successes or 0))),
        "failures": max(0, min(3, int(failures or 0))),
        "stable": bool(stable),
    }


def is_dead(character: dict | object | None) -> bool:
    """Return whether a character is mechanically dead."""
    if not character:
        return False
    if isinstance(character, dict):
        death_saves = character.get("death_saves") or {}
        hp_current = character.get("hp_current", 0) or 0
    else:
        death_saves = getattr(character, "death_saves", None) or {}
        hp_current = getattr(character, "hp_current", 0) or 0
    return int(hp_current) <= 0 and int(death_saves.get("failures", 0) or 0) >= 3


def is_dying(character: dict | object | None) -> bool:
    """Return whether a character is at 0 HP and still making death saves."""
    if not character:
        return False
    if isinstance(character, dict):
        hp_current = character.get("hp_current", 0) or 0
        death_saves = character.get("death_saves") or {}
    else:
        hp_current = getattr(character, "hp_current", 0) or 0
        death_saves = getattr(character, "death_saves", None) or {}
    return int(hp_current) <= 0 and not death_saves.get("stable") and not is_dead(character)


def get_life_state(character: dict | object | None) -> str:
    """Return alive, dying, stable, or dead for a character-like object."""
    if not character:
        return "alive"
    if isinstance(character, dict):
        hp_current = int(character.get("hp_current", 0) or 0)
        death_saves = character.get("death_saves") or {}
    else:
        hp_current = int(getattr(character, "hp_current", 0) or 0)
        death_saves = getattr(character, "death_saves", None) or {}
    if hp_current > 0:
        return "alive"
    if int(death_saves.get("failures", 0) or 0) >= 3:
        return "dead"
    if death_saves.get("stable"):
        return "stable"
    return "dying"


def apply_character_damage(character: object, damage: int) -> dict:
    """Apply damage and initialize death saves when a character drops to 0 HP."""
    before_hp = int(getattr(character, "hp_current", 0) or 0)
    dealt = max(0, int(damage or 0))
    after_hp = max(0, before_hp - dealt)
    character.hp_current = after_hp
    dropped_to_zero = before_hp > 0 and after_hp == 0
    if dropped_to_zero and getattr(character, "death_saves", None) is None:
        character.death_saves = default_death_saves()
    return {
        "hp_before": before_hp,
        "hp_after": after_hp,
        "damage": dealt,
        "dropped_to_zero": dropped_to_zero,
        "death_saves": getattr(character, "death_saves", None),
    }


def apply_character_healing(character: object, healing: int) -> dict:
    """Apply healing and clear death saves when HP rises above 0."""
    before_hp = int(getattr(character, "hp_current", 0) or 0)
    amount = max(0, int(healing or 0))
    hp_max = get_effective_hp_max(character)
    after_hp = min(hp_max, before_hp + amount)
    character.hp_current = after_hp
    revived = before_hp <= 0 and after_hp > 0
    if revived:
        character.death_saves = None
    return {
        "hp_before": before_hp,
        "hp_after": after_hp,
        "healing": amount,
        "revived": revived,
        "death_saves": getattr(character, "death_saves", None),
    }


def stabilize_character(character: object) -> dict:
    """Stabilize a 0-HP character without restoring HP."""
    death_saves = default_death_saves(stable=True)
    character.death_saves = death_saves
    return death_saves


def calc_passive_perception(derived: dict, proficient_skills: list, feats: list = None) -> int:
    """计算被动感知值 = 10 + WIS修正 + 熟练加值（如果熟练感知）+ 专长加值"""
    wis_mod = derived.get("ability_modifiers", {}).get("wis", 0)
    prof = derived.get("proficiency_bonus", 2)
    is_proficient = "感知" in proficient_skills or "Perception" in proficient_skills
    base = 10 + wis_mod + (prof if is_proficient else 0)
    # Observant 专长加 +5
    if feats:
        for feat_entry in feats:
            fname = feat_entry.get("name", "") if isinstance(feat_entry, dict) else str(feat_entry)
            if fname == "Observant":
                base += 5
    return base

def ability_modifier(score: int) -> int:
    return (score - 10) // 2


def proficiency_bonus(level: int) -> int:
    return 2 + (level - 1) // 4


def apply_racial_bonuses(ability_scores: dict, race: str) -> dict:
    """将种族能力值加值应用到基础属性上，返回新字典"""
    bonuses = RACIAL_ABILITY_BONUSES.get(race, {})
    result = dict(ability_scores)
    for ability, bonus in bonuses.items():
        result[ability] = result.get(ability, 10) + bonus
    return result


def get_spell_slots(char_class: str, level: int) -> dict:
    """根据职业和等级返回正确的法术位字典"""
    cls_key = _normalize_class(char_class)
    caster_type = CASTER_TYPE.get(cls_key)

    if caster_type == "full":
        raw = SPELL_SLOTS_FULL.get(min(level, 20), {})
        return {k: v for k, v in raw.items() if v > 0}
    elif caster_type == "half":
        raw = SPELL_SLOTS_HALF.get(min(level, 20), {})
        return {k: v for k, v in raw.items() if v > 0}
    elif caster_type == "pact":
        pact = SPELL_SLOTS_WARLOCK.get(min(level, 20), {})
        slot_lvl = pact.get("slot_level", "1st")
        return {slot_lvl: pact.get("slots", 0)}
    return {}


def get_cantrips_count(char_class: str, level: int) -> int:
    """返回该职业在该等级应知道的戏法数量"""
    cls_key = _normalize_class(char_class)
    table = CANTRIPS_KNOWN.get(cls_key, {})
    if not table:
        return 0
    count = 0
    for threshold, val in sorted(table.items()):
        if level >= threshold:
            count = val
    return count

def calc_hit_dice_pool(char_class: str, level: int) -> dict:
    """Calculate hit dice pool for short rest"""
    cls_key = _normalize_class(char_class)
    hit_die = HIT_DICE.get(cls_key, 8)
    return {"total": level, "remaining": level, "die": f"d{hit_die}"}


def get_class_resource_defaults(char_class: str, level: int, subclass: str = None) -> dict:
    """Return default class resource values for a class and level"""
    cls_key = _normalize_class(char_class)
    resources = {}
    if cls_key == "Fighter":
        resources["second_wind_used"] = False
        if level >= 2:
            resources["action_surge_used"] = False
        # Samurai: Fighting Spirit uses (WIS mod, minimum 1; default 1 without ability scores)
        if subclass and ("samurai" in subclass.lower() or "武士" in subclass.lower()):
            resources["fighting_spirit_remaining"] = max(1, 1)  # default 1, recalculated with actual WIS
        # Battle Master: Superiority Dice (replenish on short rest)
        if subclass and ("battle master" in subclass.lower() or "战争大师" in subclass.lower()):
            resources["superiority_dice_remaining"] = 4 if level < 7 else (5 if level < 15 else 6)
    elif cls_key == "Barbarian":
        if level >= 1:
            rage_uses = 2
            if level >= 20:
                rage_uses = 999
            elif level >= 17:
                rage_uses = 6
            elif level >= 12:
                rage_uses = 5
            elif level >= 6:
                rage_uses = 4
            elif level >= 3:
                rage_uses = 3
            resources["rage_remaining"] = rage_uses
            resources["raging"] = False
    elif cls_key == "Rogue":
        resources["cunning_action_available"] = True
    elif cls_key == "Paladin":
        resources["channel_divinity_used"] = False
        resources["lay_on_hands_remaining"] = level * 5
    elif cls_key == "Monk":
        resources["ki_remaining"] = level if level >= 2 else 0
    elif cls_key == "Bard":
        cha_mod_est = 3  # estimate, actual calculated at creation
        resources["bardic_inspiration_remaining"] = max(1, cha_mod_est)
    # Cleric resources
    elif cls_key == "Cleric":
        resources["channel_divinity_used"] = False
        if subclass and ("war" in subclass.lower() or "战争" in subclass.lower()):
            resources["war_priest_remaining"] = max(1, 1)  # WIS mod, default 1
    # Druid resources
    elif cls_key == "Druid":
        resources["wild_shape_remaining"] = 2  # 2 uses, replenish on short rest
    # Sorcerer resources
    elif cls_key == "Sorcerer":
        if subclass and ("wild" in subclass.lower() or "野蛮" in subclass.lower()):
            resources["tides_of_chaos_used"] = False
    # Wizard resources
    elif cls_key == "Wizard":
        if subclass and ("divination" in subclass.lower() or "预言" in subclass.lower()):
            resources["portent_remaining"] = 2  # 3 at Lv14+
            if level >= 14:
                resources["portent_remaining"] = 3
    return resources


def _normalize_class(char_class: str) -> str:
    """将中文/别名职业名转换为英文标准名"""
    mapping = {
        "战士": "Fighter", "圣武士": "Paladin", "野蛮人": "Barbarian",
        "游侠": "Ranger", "游荡者": "Rogue", "武僧": "Monk",
        "牧师": "Cleric", "德鲁伊": "Druid", "吟游诗人": "Bard",
        "法师": "Wizard", "术士": "Sorcerer", "邪术师": "Warlock",
        "魔契师": "Warlock",
    }
    return mapping.get(char_class, char_class)
