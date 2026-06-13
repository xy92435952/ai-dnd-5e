from typing import Any

from services.dnd_character_rules import get_spell_slots
from services.dnd_data import BATTLE_MASTER_MANEUVERS


def apply_subclass_effects(
    *,
    cls_key: str,
    level: int,
    subclass: str | None,
    ability_modifiers: dict[str, int],
    proficiency_bonus: int,
    base_ac: int,
    hp_max: int,
    equipment: dict | None = None,
) -> dict[str, Any]:
    """Apply subclass-derived mechanical flags without changing the public derived schema."""
    crit_threshold = 20
    bonus_healing = False
    attack_bonus_override = None
    subclass_effects: dict[str, Any] = {}

    if not subclass:
        return {
            "base_ac": base_ac,
            "hp_max": hp_max,
            "crit_threshold": crit_threshold,
            "bonus_healing": bonus_healing,
            "attack_bonus_override": attack_bonus_override,
            "subclass_effects": subclass_effects,
        }

    sub = subclass.lower()
    str_mod = ability_modifiers.get("str", 0)
    dex_mod = ability_modifiers.get("dex", 0)
    con_mod = ability_modifiers.get("con", 0)
    int_mod = ability_modifiers.get("int", 0)
    wis_mod = ability_modifiers.get("wis", 0)
    cha_mod = ability_modifiers.get("cha", 0)

    if cls_key == "Fighter" and ("champion" in sub or "冠军" in sub):
        if level >= 15:
            crit_threshold = 18
        elif level >= 3:
            crit_threshold = 19
        subclass_effects["improved_critical"] = True
    if cls_key == "Cleric" and ("life" in sub or "生命" in sub):
        bonus_healing = True
        subclass_effects["bonus_healing"] = True
    if cls_key == "Barbarian" and ("berserker" in sub or "狂战士" in sub):
        subclass_effects["frenzy"] = True
    if cls_key == "Barbarian" and ("totem" in sub or "图腾" in sub):
        subclass_effects["totem_warrior"] = True
        subclass_effects["bear_totem"] = True
    if cls_key == "Barbarian" and ("zealot" in sub or "狂热" in sub):
        subclass_effects["zealot"] = True
        subclass_effects["divine_fury"] = True
    if cls_key == "Sorcerer" and ("draconic" in sub or "龙族" in sub):
        subclass_effects["draconic_resilience"] = True
        hp_max += level
        if not equipment or not equipment.get("armor"):
            base_ac = max(base_ac, 13 + dex_mod)
    if cls_key == "Warlock" and ("hexblade" in sub or "魔剑" in sub):
        subclass_effects["hexblade"] = True
        subclass_effects["hex_warrior"] = True
        if cha_mod > str_mod and cha_mod > dex_mod:
            attack_bonus_override = proficiency_bonus + cha_mod
    if cls_key == "Rogue" and ("swashbuckler" in sub or "剑客" in sub):
        subclass_effects["swashbuckler"] = True
        subclass_effects["rakish_audacity"] = True
    if cls_key == "Rogue" and ("assassin" in sub or "刺客" in sub):
        subclass_effects["assassin"] = True
        subclass_effects["assassinate"] = True
    if cls_key == "Fighter" and ("samurai" in sub or "武士" in sub):
        subclass_effects["samurai"] = True
        subclass_effects["fighting_spirit"] = True
        subclass_effects["fighting_spirit_uses"] = max(1, wis_mod)
    if cls_key == "Paladin" and ("devotion" in sub or "虔诚" in sub):
        subclass_effects["devotion"] = True
        subclass_effects["aura_of_devotion"] = True
    if cls_key == "Paladin" and ("vengeance" in sub or "复仇" in sub):
        subclass_effects["vengeance"] = True
        subclass_effects["vow_of_enmity"] = True
    if cls_key == "Warlock" and ("fiend" in sub or "恶魔" in sub):
        subclass_effects["fiend_patron"] = True
        subclass_effects["dark_ones_blessing"] = True
    if cls_key == "Wizard" and ("evocation" in sub or "塑能" in sub):
        subclass_effects["sculpt_spells"] = True
    if cls_key == "Barbarian" and ("storm" in sub or "风暴" in sub):
        subclass_effects["storm_herald"] = True
        aura_dmg = "1d6" if level < 10 else ("2d6" if level < 15 else "3d6")
        subclass_effects["storm_aura_damage"] = aura_dmg
    if cls_key == "Ranger" and ("swarm" in sub or "虫群" in sub):
        subclass_effects["swarmkeeper"] = True
        swarm_die = "1d6" if level < 11 else "1d8"
        subclass_effects["gathered_swarm_die"] = swarm_die
    if cls_key == "Sorcerer" and ("divine" in sub or "神圣" in sub):
        subclass_effects["divine_soul"] = True
        subclass_effects["favored_by_gods"] = True
        subclass_effects["cleric_spell_access"] = True

    if cls_key == "Fighter" and ("battle master" in sub or "战争大师" in sub):
        subclass_effects["battle_master"] = True
        sd_count = 4 if level < 7 else (5 if level < 15 else 6)
        sd_die = "d8" if level < 10 else ("d10" if level < 18 else "d12")
        subclass_effects["superiority_dice_max"] = sd_count
        subclass_effects["superiority_die"] = sd_die
        subclass_effects["maneuvers"] = list(BATTLE_MASTER_MANEUVERS.keys())

    if cls_key == "Bard":
        subclass_effects["bardic_inspiration"] = True
        bi_die = "d6" if level < 5 else ("d8" if level < 10 else ("d10" if level < 15 else "d12"))
        subclass_effects["inspiration_die"] = bi_die
    if cls_key == "Bard" and ("lore" in sub or "知识" in sub):
        subclass_effects["lore_bard"] = True
        subclass_effects["cutting_words"] = True
    if cls_key == "Bard" and ("valor" in sub or "英勇" in sub):
        subclass_effects["valor_bard"] = True
        subclass_effects["combat_inspiration"] = True
    if cls_key == "Bard" and ("swords" in sub or "剑术" in sub):
        subclass_effects["swords_bard"] = True
        subclass_effects["blade_flourish"] = True
    if cls_key == "Bard" and ("glamour" in sub or "魅惑" in sub):
        subclass_effects["glamour_bard"] = True
        subclass_effects["mantle_of_inspiration"] = True

    if cls_key == "Monk" and level >= 2:
        subclass_effects["ki_pool"] = True
        subclass_effects["ki_max"] = level
    if cls_key == "Monk" and ("open hand" in sub or "虚空" in sub):
        subclass_effects["open_hand"] = True
        subclass_effects["open_hand_technique"] = True
    if cls_key == "Monk" and ("shadow" in sub or "暗影" in sub):
        subclass_effects["shadow_monk"] = True
        subclass_effects["shadow_step"] = True
    if cls_key == "Monk" and ("drunken" in sub or "醉拳" in sub):
        subclass_effects["drunken_master"] = True
        subclass_effects["drunken_technique"] = True
    if cls_key == "Monk" and ("four elements" in sub or "四象" in sub):
        subclass_effects["four_elements"] = True
        subclass_effects["elemental_disciplines"] = True

    if cls_key == "Cleric" and ("war" in sub or "战争" in sub):
        subclass_effects["war_domain"] = True
        subclass_effects["war_priest"] = True
    if cls_key == "Cleric" and ("light" in sub or "光明" in sub):
        subclass_effects["light_domain"] = True
        subclass_effects["warding_flare"] = True
    if cls_key == "Cleric" and ("knowledge" in sub or "知识" in sub):
        subclass_effects["knowledge_domain"] = True
    if cls_key == "Cleric" and ("trickery" in sub or "诡计" in sub):
        subclass_effects["trickery_domain"] = True
        subclass_effects["blessing_of_trickster"] = True
    if cls_key == "Cleric" and ("nature" in sub or "自然" in sub):
        subclass_effects["nature_domain"] = True
    if cls_key == "Cleric" and ("tempest" in sub or "暴风" in sub):
        subclass_effects["tempest_domain"] = True
        subclass_effects["wrath_of_storm"] = True
        subclass_effects["destructive_wrath"] = True

    if cls_key == "Ranger" and ("hunter" in sub or "猎手" in sub):
        subclass_effects["hunter"] = True
        subclass_effects["colossus_slayer"] = True
    if cls_key == "Ranger" and ("gloom" in sub or "暗域" in sub):
        subclass_effects["gloom_stalker"] = True
        subclass_effects["dread_ambusher"] = True

    if cls_key == "Druid" and ("land" in sub or "大地" in sub):
        subclass_effects["circle_of_land"] = True
        subclass_effects["natural_recovery"] = True
    if cls_key == "Sorcerer" and ("wild" in sub or "野魔" in sub):
        subclass_effects["wild_magic"] = True
        subclass_effects["tides_of_chaos"] = True
    if cls_key == "Sorcerer" and ("storm" in sub or "风暴" in sub):
        subclass_effects["storm_sorcery"] = True
        subclass_effects["tempestuous_magic"] = True

    if cls_key == "Druid" and ("moon" in sub or "月亮" in sub):
        subclass_effects["circle_of_moon"] = True
        subclass_effects["combat_wild_shape"] = True
        subclass_effects["wild_shape_max_cr"] = 1 if level < 6 else level // 3
        if level >= 10:
            subclass_effects["elemental_wild_shape"] = True
    if cls_key == "Druid" and ("spores" in sub or "孢子" in sub):
        subclass_effects["circle_of_spores"] = True
        subclass_effects["halo_of_spores"] = True
        spore_die = "1d4" if level < 6 else ("1d6" if level < 10 else ("1d8" if level < 14 else "1d10"))
        subclass_effects["spore_damage_die"] = spore_die
        subclass_effects["symbiotic_entity"] = True
        subclass_effects["symbiotic_temp_hp"] = 4 * level
    if cls_key == "Fighter" and ("eldritch" in sub or "魔战" in sub):
        subclass_effects["eldritch_knight"] = True
        subclass_effects["weapon_bond"] = True
        if level >= 3:
            ek_caster_level = (level - 2) // 3 + 1
            subclass_effects["ek_spell_slots"] = get_spell_slots("Wizard", min(ek_caster_level, 7))
        if level >= 7:
            subclass_effects["war_magic"] = True
    if cls_key == "Rogue" and ("arcane trickster" in sub or "奥法" in sub):
        subclass_effects["arcane_trickster"] = True
        subclass_effects["mage_hand_legerdemain"] = True
        if level >= 3:
            at_caster_level = (level - 2) // 3 + 1
            subclass_effects["at_spell_slots"] = get_spell_slots("Wizard", min(at_caster_level, 7))
        if level >= 9:
            subclass_effects["magical_ambush"] = True
    if cls_key == "Wizard" and ("abjuration" in sub or "防护" in sub):
        subclass_effects["abjuration"] = True
        subclass_effects["arcane_ward"] = True
        subclass_effects["arcane_ward_hp_max"] = level * 2 + int_mod
    if cls_key == "Wizard" and ("illusion" in sub or "幻术" in sub):
        subclass_effects["illusion"] = True
        subclass_effects["improved_minor_illusion"] = True
    if cls_key == "Wizard" and ("necromancy" in sub or "死灵" in sub):
        subclass_effects["necromancy"] = True
        subclass_effects["grim_harvest"] = True
    if cls_key == "Wizard" and ("conjuration" in sub or "咒法" in sub):
        subclass_effects["conjuration"] = True
        subclass_effects["minor_conjuration"] = True
    if cls_key == "Wizard" and ("divination" in sub or "预言" in sub):
        subclass_effects["divination"] = True
        subclass_effects["portent"] = True
        subclass_effects["portent_count"] = 2 if level < 14 else 3
    if cls_key == "Wizard" and ("enchantment" in sub or "附魔" in sub):
        subclass_effects["enchantment"] = True
        subclass_effects["hypnotic_gaze"] = True
    if cls_key == "Wizard" and ("transmutation" in sub or "变化" in sub):
        subclass_effects["transmutation"] = True
        subclass_effects["transmuters_stone"] = True
    if cls_key == "Paladin" and ("ancients" in sub or "远古" in sub):
        subclass_effects["ancients"] = True
        subclass_effects["aura_of_warding"] = True
    if cls_key == "Paladin" and ("glory" in sub or "荣耀" in sub):
        subclass_effects["glory"] = True
        subclass_effects["inspiring_smite"] = True
    if cls_key == "Warlock" and ("archfey" in sub or "大精灵" in sub):
        subclass_effects["archfey"] = True
        subclass_effects["fey_presence"] = True
        subclass_effects["misty_escape"] = True
    if cls_key == "Warlock" and ("great old one" in sub or "旧日" in sub):
        subclass_effects["great_old_one"] = True
        subclass_effects["awakened_mind"] = True
        subclass_effects["thought_shield"] = True
    if cls_key == "Rogue" and ("thief" in sub or "窃贼" in sub):
        subclass_effects["thief"] = True
        subclass_effects["fast_hands"] = True
        subclass_effects["second_story_work"] = True
        if level >= 13:
            subclass_effects["use_magic_device"] = True

    return {
        "base_ac": base_ac,
        "hp_max": hp_max,
        "crit_threshold": crit_threshold,
        "bonus_healing": bonus_healing,
        "attack_bonus_override": attack_bonus_override,
        "subclass_effects": subclass_effects,
    }
