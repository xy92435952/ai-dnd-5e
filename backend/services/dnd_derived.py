"""Derived character stat calculation for DnD 5e characters."""

from services.dnd_character_rules import (
    _normalize_class,
    ability_modifier,
    calc_passive_perception,
    get_cantrips_count,
    get_spell_slots,
    proficiency_bonus,
)
from services.dnd_data import (
    ARMOR,
    BASE_AC,
    CASTER_TYPE,
    CLASS_ARMOR_PROFICIENCY,
    CLASS_SAVE_PROFICIENCIES,
    CLASS_WEAPON_PROFICIENCY,
    FEATS,
    FIGHTING_STYLES,
    HIT_DICE,
    RACIAL_DARKVISION,
    SPELLCASTING_ABILITY,
)
from services.dnd_subclass_effects import apply_subclass_effects


def calc_derived(char_class: str, level: int, ability_scores: dict, subclass: str = None,
                 fighting_style: str = None, feats: list = None, equipment: dict = None,
                 race: str = None, proficient_skills: list = None) -> dict:
    """计算角色的所有衍生属性（输入已含种族加值的最终能力值）"""
    cls_key = _normalize_class(char_class)

    str_mod = ability_modifier(ability_scores.get("str", 10))
    dex_mod = ability_modifier(ability_scores.get("dex", 10))
    con_mod = ability_modifier(ability_scores.get("con", 10))
    int_mod = ability_modifier(ability_scores.get("int", 10))
    wis_mod = ability_modifier(ability_scores.get("wis", 10))
    cha_mod = ability_modifier(ability_scores.get("cha", 10))
    ability_modifiers = {
        "str": str_mod,
        "dex": dex_mod,
        "con": con_mod,
        "int": int_mod,
        "wis": wis_mod,
        "cha": cha_mod,
    }

    prof = proficiency_bonus(level)
    hit_die = HIT_DICE.get(cls_key, 8)
    base_ac = BASE_AC.get(cls_key, 13)

    if cls_key == "Barbarian":
        base_ac = max(base_ac, 10 + dex_mod + con_mod)
    if cls_key == "Monk":
        base_ac = max(base_ac, 10 + dex_mod + wis_mod)

    hp_max = hit_die + con_mod + max(0, level - 1) * (hit_die // 2 + 1 + con_mod)

    spell_ability_key = SPELLCASTING_ABILITY.get(cls_key)
    spell_mod = ability_modifiers.get(spell_ability_key or "", 0)
    spell_save_dc = 8 + prof + spell_mod if spell_ability_key else 0
    spell_attack_bonus = prof + spell_mod if spell_ability_key else 0
    spell_slots_max = get_spell_slots(cls_key, level)

    subclass_result = apply_subclass_effects(
        cls_key=cls_key,
        level=level,
        subclass=subclass,
        ability_modifiers=ability_modifiers,
        proficiency_bonus=prof,
        base_ac=base_ac,
        hp_max=hp_max,
        equipment=equipment,
    )
    base_ac = subclass_result["base_ac"]
    hp_max = subclass_result["hp_max"]
    crit_threshold = subclass_result["crit_threshold"]
    bonus_healing = subclass_result["bonus_healing"]
    attack_bonus_override = subclass_result["attack_bonus_override"]
    subclass_effects = subclass_result["subclass_effects"]

    save_profs = CLASS_SAVE_PROFICIENCIES.get(cls_key, [])
    saving_throws = {}
    for key, mod in ability_modifiers.items():
        saving_throws[key] = mod + (prof if key in save_profs else 0)

    melee_damage_bonus = 0
    two_weapon_fighting = False
    style_effects = {}
    if fighting_style and fighting_style in FIGHTING_STYLES:
        fs = FIGHTING_STYLES[fighting_style]
        style_effects = dict(fs)
        if fs.get("ac_bonus"):
            base_ac += fs["ac_bonus"]
        if fs.get("melee_damage_bonus"):
            melee_damage_bonus = fs["melee_damage_bonus"]
        if fs.get("two_weapon_fighting"):
            two_weapon_fighting = True

    ranged_atk_bonus = prof + dex_mod + (FIGHTING_STYLES.get(fighting_style or "", {}).get("ranged_attack_bonus", 0))

    equipped_weapon_damage = None
    equipped_weapon_type = None
    armor_proficiencies = CLASS_ARMOR_PROFICIENCY.get(cls_key, [])
    weapon_proficiencies = CLASS_WEAPON_PROFICIENCY.get(cls_key, [])

    if equipment and isinstance(equipment, dict):
        equipped_armor = equipment.get("armor", [])
        if equipped_armor:
            armor_item = equipped_armor[0] if isinstance(equipped_armor, list) else equipped_armor
            armor_name = armor_item.get("name", "") if isinstance(armor_item, dict) else str(armor_item)
            if armor_name in ARMOR:
                armor = ARMOR[armor_name]
                armor_ac = armor["ac"]
                if armor["dex_bonus"] == "full":
                    armor_ac += dex_mod
                elif armor["dex_bonus"] == "max2":
                    armor_ac += min(2, dex_mod)
                base_ac = armor_ac
                if fighting_style == "Defense":
                    base_ac += 1

        shield_item = equipment.get("shield")
        if shield_item and (not isinstance(shield_item, dict) or shield_item.get("equipped")):
            base_ac += 2

        weapons = equipment.get("weapons", [])
        if weapons:
            weapon = weapons[0] if isinstance(weapons, list) else weapons
            if isinstance(weapon, dict):
                equipped_weapon_damage = weapon.get("damage", "1d8")
                equipped_weapon_type = weapon.get("type", "")

    feat_effects = {}
    if feats:
        for feat_entry in feats:
            fname = feat_entry.get("name", "") if isinstance(feat_entry, dict) else str(feat_entry)
            if fname in FEATS:
                effects = FEATS[fname]["effects"]
                feat_effects[fname] = effects
                if effects.get("hp_per_level"):
                    hp_max += effects["hp_per_level"] * level
                if effects.get("concentration_advantage"):
                    subclass_effects["concentration_advantage"] = True

    initiative_val = dex_mod
    for fe in feat_effects.values():
        initiative_val += fe.get("initiative_bonus", 0)
    if subclass_effects.get("rakish_audacity"):
        initiative_val += cha_mod
    if subclass_effects.get("dread_ambusher"):
        initiative_val += wis_mod

    darkvision = RACIAL_DARKVISION.get(race or "", 0)
    passive_perception = calc_passive_perception(
        {"ability_modifiers": {"wis": wis_mod}, "proficiency_bonus": prof},
        proficient_skills or [],
        feats,
    )

    return {
        "hp_max": max(1, hp_max),
        "ac": base_ac,
        "initiative": initiative_val,
        "proficiency_bonus": prof,
        "attack_bonus": attack_bonus_override if attack_bonus_override is not None else (prof + str_mod),
        "attack_bonus_override": attack_bonus_override,
        "ranged_attack_bonus": ranged_atk_bonus,
        "melee_damage_bonus": melee_damage_bonus,
        "spell_save_dc": spell_save_dc,
        "spell_attack_bonus": spell_attack_bonus,
        "spell_ability": spell_ability_key,
        "ability_modifiers": ability_modifiers,
        "saving_throws": saving_throws,
        "spell_slots_max": spell_slots_max,
        "hit_die": hit_die,
        "caster_type": CASTER_TYPE.get(cls_key),
        "cantrips_count": get_cantrips_count(cls_key, level),
        "crit_threshold": crit_threshold,
        "bonus_healing": bonus_healing,
        "subclass_effects": subclass_effects,
        "fighting_style": fighting_style,
        "two_weapon_fighting": two_weapon_fighting,
        "style_effects": style_effects,
        "equipped_weapon_damage": equipped_weapon_damage,
        "equipped_weapon_type": equipped_weapon_type,
        "armor_proficiencies": armor_proficiencies,
        "weapon_proficiencies": weapon_proficiencies,
        "feat_effects": feat_effects,
        "passive_perception": passive_perception,
        "darkvision": darkvision,
    }
