"""Derived character stat calculation for DnD 5e characters."""

from services.dnd_character_rules import (
    _normalize_class, ability_modifier, calc_passive_perception,
    get_cantrips_count, get_spell_slots, proficiency_bonus,
)
from services.dnd_data import (
    ARMOR, BASE_AC, CASTER_TYPE, CLASS_ARMOR_PROFICIENCY,
    CLASS_SAVE_PROFICIENCIES, CLASS_WEAPON_PROFICIENCY, FEATS,
    FIGHTING_STYLES, HIT_DICE, RACIAL_DARKVISION, SPELLCASTING_ABILITY,
)


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

    prof = proficiency_bonus(level)
    hit_die = HIT_DICE.get(cls_key, 8)
    base_ac = BASE_AC.get(cls_key, 13)

    # 野蛮人无甲AC = 10 + DEX + CON
    if cls_key == "Barbarian":
        base_ac = max(base_ac, 10 + dex_mod + con_mod)
    # 武僧无甲AC = 10 + DEX + WIS
    if cls_key == "Monk":
        base_ac = max(base_ac, 10 + dex_mod + wis_mod)

    # HP：首级 = 最大骰+CON，后续 = (hit_die/2+1)+CON
    hp_max = hit_die + con_mod + max(0, level - 1) * (hit_die // 2 + 1 + con_mod)

    # 施法属性
    spell_ability_key = SPELLCASTING_ABILITY.get(cls_key)
    spell_mod = {"str": str_mod, "dex": dex_mod, "con": con_mod,
                 "int": int_mod, "wis": wis_mod, "cha": cha_mod}.get(spell_ability_key or "", 0)
    spell_save_dc      = 8 + prof + spell_mod if spell_ability_key else 0
    spell_attack_bonus = prof + spell_mod if spell_ability_key else 0

    # 法术位（全/半/契约）
    spell_slots_max = get_spell_slots(cls_key, level)

    # ── 子职业机械效果 ─────────────────────────────────────
    crit_threshold   = 20          # 暴击阈值（默认自然20）
    bonus_healing    = False       # 生命域：治疗加成
    attack_bonus_override = None   # Hexblade: CHA-based attack bonus
    subclass_effects = {}
    if subclass:
        sub = subclass.lower()
        # 冠军武士：3级起19暴击（Improved Critical），15级起18暴击（Superior Critical）
        if cls_key == "Fighter" and ("champion" in sub or "冠军" in sub):
            if level >= 15:
                crit_threshold = 18
            elif level >= 3:
                crit_threshold = 19
            subclass_effects["improved_critical"] = True
        # 生命域牧师：治疗加值 = 2 + 法术环级
        if cls_key == "Cleric" and ("life" in sub or "生命" in sub):
            bonus_healing = True
            subclass_effects["bonus_healing"] = True
        # 狂战士野蛮人：激怒时有额外攻击次数（简化：标记 flag）
        if cls_key == "Barbarian" and ("berserker" in sub or "狂战士" in sub):
            subclass_effects["frenzy"] = True
        # 图腾战士（熊图腾）：狂暴时所有伤害类型（除心灵）减半
        if cls_key == "Barbarian" and ("totem" in sub or "图腾" in sub):
            subclass_effects["totem_warrior"] = True
            subclass_effects["bear_totem"] = True  # Default to bear (most popular)
        # 狂热者野蛮人：狂暴时每回合首次命中+1d6+半等级辐射伤害
        if cls_key == "Barbarian" and ("zealot" in sub or "狂热" in sub):
            subclass_effects["zealot"] = True
            subclass_effects["divine_fury"] = True  # +1d6+half_level radiant on first hit per turn
        # 龙族血脉术士：+1HP/级，无甲时AC=13+DEX
        if cls_key == "Sorcerer" and ("draconic" in sub or "龙族" in sub):
            subclass_effects["draconic_resilience"] = True
            hp_max += level  # +1 HP per level
            if not equipment or not equipment.get("armor"):
                base_ac = max(base_ac, 13 + dex_mod)  # Natural armor 13+DEX
        # 魔剑契约锁链术师：用CHA代替STR/DEX进行武器攻击
        if cls_key == "Warlock" and ("hexblade" in sub or "魔剑" in sub):
            subclass_effects["hexblade"] = True
            subclass_effects["hex_warrior"] = True
            if cha_mod > str_mod and cha_mod > dex_mod:
                attack_bonus_override = prof + cha_mod
        # 剑客游荡者：先攻+CHA，独对时可偷袭
        if cls_key == "Rogue" and ("swashbuckler" in sub or "剑客" in sub):
            subclass_effects["swashbuckler"] = True
            subclass_effects["rakish_audacity"] = True
            # initiative_val += cha_mod applied after initiative_val is initialized
        # 刺客游荡者：首轮对未行动目标有优势且自动暴击
        if cls_key == "Rogue" and ("assassin" in sub or "刺客" in sub):
            subclass_effects["assassin"] = True
            subclass_effects["assassinate"] = True
        # 武士战士：战意精神（优势+临时HP）
        if cls_key == "Fighter" and ("samurai" in sub or "武士" in sub):
            subclass_effects["samurai"] = True
            subclass_effects["fighting_spirit"] = True
            subclass_effects["fighting_spirit_uses"] = max(1, wis_mod)
        # 虔诚圣武士：魅惑免疫光环
        if cls_key == "Paladin" and ("devotion" in sub or "虔诚" in sub):
            subclass_effects["devotion"] = True
            subclass_effects["aura_of_devotion"] = True
        # 复仇圣武士：仇敌誓约（对标记目标优势）
        if cls_key == "Paladin" and ("vengeance" in sub or "复仇" in sub):
            subclass_effects["vengeance"] = True
            subclass_effects["vow_of_enmity"] = True
        # 恶魔契约锁链术师：击杀时获得临时HP
        if cls_key == "Warlock" and ("fiend" in sub or "恶魔" in sub):
            subclass_effects["fiend_patron"] = True
            subclass_effects["dark_ones_blessing"] = True
        # 塑能系法师：可保护友军免受 AoE（标记 flag，法术端点读取）
        if cls_key == "Wizard" and ("evocation" in sub or "塑能" in sub):
            subclass_effects["sculpt_spells"] = True
        # 风暴先驱野蛮人：狂暴时10尺光环造成元素伤害
        if cls_key == "Barbarian" and ("storm" in sub or "风暴" in sub):
            subclass_effects["storm_herald"] = True
            aura_dmg = "1d6" if level < 10 else ("2d6" if level < 15 else "3d6")
            subclass_effects["storm_aura_damage"] = aura_dmg  # 沙漠=火焰, 海洋=闪电, 苔原=临时HP
        # 虫群之主游侠：攻击时虫群附加效果
        if cls_key == "Ranger" and ("swarm" in sub or "虫群" in sub):
            subclass_effects["swarmkeeper"] = True
            swarm_die = "1d6" if level < 11 else "1d8"
            subclass_effects["gathered_swarm_die"] = swarm_die  # 额外伤害或推动/拉扯
        # 神圣灵魂术士：获取牧师法术列表+神恩（失败时+2d4）
        if cls_key == "Sorcerer" and ("divine" in sub or "神圣" in sub):
            subclass_effects["divine_soul"] = True
            subclass_effects["favored_by_gods"] = True  # 1次/短休：攻击/检定/豁免+2d4
            subclass_effects["cleric_spell_access"] = True

        # ── Batch 2: 资源追踪子职业机械效果 ──────────────────────

        # ── 战争大师（Battle Master）：优势骰系统 ──
        if cls_key == "Fighter" and ("battle master" in sub or "战争大师" in sub):
            subclass_effects["battle_master"] = True
            sd_count = 4 if level < 7 else (5 if level < 15 else 6)
            sd_die = "d8" if level < 10 else ("d10" if level < 18 else "d12")
            subclass_effects["superiority_dice_max"] = sd_count
            subclass_effects["superiority_die"] = sd_die
            subclass_effects["maneuvers"] = ["precision", "trip", "disarm", "riposte", "menacing", "pushing", "goading"]

        # ── 吟游诗人（Bard）：鼓舞骰系统 ──
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

        # ── 武僧（Monk）：气系统 ──
        if cls_key == "Monk":
            if level >= 2:
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

        # ── 牧师领域（Cleric Domains）──
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

        # ── 游侠（Ranger）子职业 ──
        if cls_key == "Ranger" and ("hunter" in sub or "猎手" in sub):
            subclass_effects["hunter"] = True
            subclass_effects["colossus_slayer"] = True

        if cls_key == "Ranger" and ("gloom" in sub or "暗域" in sub):
            subclass_effects["gloom_stalker"] = True
            subclass_effects["dread_ambusher"] = True

        # ── 德鲁伊（Druid）大地之环 ──
        if cls_key == "Druid" and ("land" in sub or "大地" in sub):
            subclass_effects["circle_of_land"] = True
            subclass_effects["natural_recovery"] = True

        # ── 术士（Sorcerer）起源 ──
        if cls_key == "Sorcerer" and ("wild" in sub or "野魔" in sub):
            subclass_effects["wild_magic"] = True
            subclass_effects["tides_of_chaos"] = True

        if cls_key == "Sorcerer" and ("storm" in sub or "风暴" in sub):
            subclass_effects["storm_sorcery"] = True
            subclass_effects["tempestuous_magic"] = True

        # ── Batch 3: 复杂子职业机械效果 ──────────────────────

        # 月亮德鲁伊：增强野兽形态
        if cls_key == "Druid" and ("moon" in sub or "月亮" in sub):
            subclass_effects["circle_of_moon"] = True
            subclass_effects["combat_wild_shape"] = True  # Bonus action to transform
            # CR limit: Lv2=CR1, Lv6=CR level/3
            max_cr = 1 if level < 6 else level // 3
            subclass_effects["wild_shape_max_cr"] = max_cr
            if level >= 10:
                subclass_effects["elemental_wild_shape"] = True

        # 孢子德鲁伊：孢子光环 + 共生体
        if cls_key == "Druid" and ("spores" in sub or "孢子" in sub):
            subclass_effects["circle_of_spores"] = True
            subclass_effects["halo_of_spores"] = True  # Reaction: 1d4 poison (1d6 at 6, 1d8 at 10, 1d10 at 14)
            spore_die = "1d4" if level < 6 else ("1d6" if level < 10 else ("1d8" if level < 14 else "1d10"))
            subclass_effects["spore_damage_die"] = spore_die
            subclass_effects["symbiotic_entity"] = True  # Use wild shape for temp HP = 4 * druid level
            subclass_effects["symbiotic_temp_hp"] = 4 * level

        # 魔战士（战士）：1/3 施法者
        if cls_key == "Fighter" and ("eldritch" in sub or "魔战" in sub):
            subclass_effects["eldritch_knight"] = True
            subclass_effects["weapon_bond"] = True
            # 1/3 caster: spell slots at Lv3
            if level >= 3:
                ek_caster_level = (level - 2) // 3 + 1  # Approximate
                ek_slots = get_spell_slots("Wizard", min(ek_caster_level, 7))
                subclass_effects["ek_spell_slots"] = ek_slots
            if level >= 7:
                subclass_effects["war_magic"] = True  # Cast cantrip + bonus action attack

        # 奥法诡术师（游荡者）：1/3 施法者
        if cls_key == "Rogue" and ("arcane trickster" in sub or "奥法" in sub):
            subclass_effects["arcane_trickster"] = True
            subclass_effects["mage_hand_legerdemain"] = True
            if level >= 3:
                at_caster_level = (level - 2) // 3 + 1
                at_slots = get_spell_slots("Wizard", min(at_caster_level, 7))
                subclass_effects["at_spell_slots"] = at_slots
            if level >= 9:
                subclass_effects["magical_ambush"] = True  # Disadvantage on save if hidden

        # 防护系法师：奥术结界
        if cls_key == "Wizard" and ("abjuration" in sub or "防护" in sub):
            subclass_effects["abjuration"] = True
            subclass_effects["arcane_ward"] = True
            subclass_effects["arcane_ward_hp_max"] = level * 2 + int_mod  # Ward HP pool

        # 幻术系法师：增强微型幻象
        if cls_key == "Wizard" and ("illusion" in sub or "幻术" in sub):
            subclass_effects["illusion"] = True
            subclass_effects["improved_minor_illusion"] = True

        # 死灵系法师：死亡收割
        if cls_key == "Wizard" and ("necromancy" in sub or "死灵" in sub):
            subclass_effects["necromancy"] = True
            subclass_effects["grim_harvest"] = True  # Heal 2x spell level on kill (3x for necromancy spells)

        # 咒法系法师：次级咒法
        if cls_key == "Wizard" and ("conjuration" in sub or "咒法" in sub):
            subclass_effects["conjuration"] = True
            subclass_effects["minor_conjuration"] = True

        # 预言系法师：先兆
        if cls_key == "Wizard" and ("divination" in sub or "预言" in sub):
            subclass_effects["divination"] = True
            subclass_effects["portent"] = True  # 2 pre-rolled d20s per long rest (3 at Lv14)
            subclass_effects["portent_count"] = 2 if level < 14 else 3

        # 附魔系法师：催眠凝视
        if cls_key == "Wizard" and ("enchantment" in sub or "附魔" in sub):
            subclass_effects["enchantment"] = True
            subclass_effects["hypnotic_gaze"] = True

        # 变化系法师：变化石
        if cls_key == "Wizard" and ("transmutation" in sub or "变化" in sub):
            subclass_effects["transmutation"] = True
            subclass_effects["transmuters_stone"] = True

        # 远古誓约圣武士：守护光环（法术伤害抗性）
        if cls_key == "Paladin" and ("ancients" in sub or "远古" in sub):
            subclass_effects["ancients"] = True
            subclass_effects["aura_of_warding"] = True  # Spell damage resistance 10ft

        # 荣耀誓约圣武士：鼓舞神击
        if cls_key == "Paladin" and ("glory" in sub or "荣耀" in sub):
            subclass_effects["glory"] = True
            subclass_effects["inspiring_smite"] = True  # Distribute temp HP after smite

        # 大精灵契约邪术师：妖精现身 + 迷雾逃遁
        if cls_key == "Warlock" and ("archfey" in sub or "大精灵" in sub):
            subclass_effects["archfey"] = True
            subclass_effects["fey_presence"] = True  # Charm/frighten in cube
            subclass_effects["misty_escape"] = True  # Reaction: invisible + teleport when damaged

        # 旧日支配者契约邪术师：觉醒心灵 + 思维护盾
        if cls_key == "Warlock" and ("great old one" in sub or "旧日" in sub):
            subclass_effects["great_old_one"] = True
            subclass_effects["awakened_mind"] = True  # Telepathy 30ft
            subclass_effects["thought_shield"] = True  # Psychic damage resistance + reflect

        # 窃贼游荡者：快手 + 攀墙术
        if cls_key == "Rogue" and ("thief" in sub or "窃贼" in sub):
            subclass_effects["thief"] = True
            subclass_effects["fast_hands"] = True  # Use Object as bonus action
            subclass_effects["second_story_work"] = True  # Climbing speed = walking speed
            if level >= 13:
                subclass_effects["use_magic_device"] = True

    # 豁免调整值（含熟练）
    save_profs = CLASS_SAVE_PROFICIENCIES.get(cls_key, [])
    saving_throws = {}
    for key, mod in [("str",str_mod),("dex",dex_mod),("con",con_mod),
                     ("int",int_mod),("wis",wis_mod),("cha",cha_mod)]:
        saving_throws[key] = mod + (prof if key in save_profs else 0)

    # ── 战斗风格效果 ──────────────────────────────────────
    melee_damage_bonus = 0
    two_weapon_fighting = False
    style_effects = {}
    if fighting_style and fighting_style in FIGHTING_STYLES:
        fs = FIGHTING_STYLES[fighting_style]
        style_effects = dict(fs)
        if fs.get("ac_bonus"):
            base_ac += fs["ac_bonus"]
        if fs.get("ranged_attack_bonus"):
            pass  # 在下方 return 中直接加
        if fs.get("melee_damage_bonus"):
            melee_damage_bonus = fs["melee_damage_bonus"]
        if fs.get("two_weapon_fighting"):
            two_weapon_fighting = True

    ranged_atk_bonus = prof + dex_mod + (FIGHTING_STYLES.get(fighting_style or "", {}).get("ranged_attack_bonus", 0))

    # ── 装备效果（如果提供了装备信息）───────────────────────
    equipped_weapon_damage = None
    equipped_weapon_type = None
    armor_proficiencies = CLASS_ARMOR_PROFICIENCY.get(cls_key, [])
    weapon_proficiencies = CLASS_WEAPON_PROFICIENCY.get(cls_key, [])

    if equipment and isinstance(equipment, dict):
        # 护甲 AC
        equipped_armor = equipment.get("armor", [])
        if equipped_armor:
            armor_item = equipped_armor[0] if isinstance(equipped_armor, list) else equipped_armor
            armor_name = armor_item.get("name", "") if isinstance(armor_item, dict) else str(armor_item)
            if armor_name in ARMOR:
                a = ARMOR[armor_name]
                armor_ac = a["ac"]
                if a["dex_bonus"] == "full":
                    armor_ac += dex_mod
                elif a["dex_bonus"] == "max2":
                    armor_ac += min(2, dex_mod)
                base_ac = armor_ac
                # 重新应用战斗风格 Defense bonus（如果有护甲）
                if fighting_style == "Defense":
                    base_ac += 1
        # 盾牌
        shield_item = equipment.get("shield")
        if shield_item and (not isinstance(shield_item, dict) or shield_item.get("equipped")):
            base_ac += 2
        # 武器
        weapons = equipment.get("weapons", [])
        if weapons:
            w = weapons[0] if isinstance(weapons, list) else weapons
            if isinstance(w, dict):
                equipped_weapon_damage = w.get("damage", "1d8")
                equipped_weapon_type = w.get("type", "")

    # ── 专长效果 ──────────────────────────────────────────
    feat_effects = {}
    if feats:
        for feat_entry in feats:
            fname = feat_entry.get("name", "") if isinstance(feat_entry, dict) else str(feat_entry)
            if fname in FEATS:
                effects = FEATS[fname]["effects"]
                feat_effects[fname] = effects
                if effects.get("initiative_bonus"):
                    pass  # 在 return 中加
                if effects.get("hp_per_level"):
                    hp_max += effects["hp_per_level"] * level
                if effects.get("concentration_advantage"):
                    subclass_effects["concentration_advantage"] = True
                if effects.get("speed_bonus"):
                    pass  # movement_max 在 combat 中处理

    initiative_val = dex_mod
    for fe in feat_effects.values():
        initiative_val += fe.get("initiative_bonus", 0)
    # Swashbuckler: add CHA to initiative
    if subclass_effects.get("rakish_audacity"):
        initiative_val += cha_mod
    # Gloom Stalker: add WIS to initiative
    if subclass_effects.get("dread_ambusher"):
        initiative_val += wis_mod

    # ── 暗视 ────────────────────────────────────────────
    darkvision = RACIAL_DARKVISION.get(race or "", 0)

    # ── 被动感知 ────────────────────────────────────────
    passive_perception = calc_passive_perception(
        {"ability_modifiers": {"wis": wis_mod}, "proficiency_bonus": prof},
        proficient_skills or [],
        feats,
    )

    return {
        "hp_max":              max(1, hp_max),
        "ac":                  base_ac,
        "initiative":          initiative_val,
        "proficiency_bonus":   prof,
        "attack_bonus":        attack_bonus_override if attack_bonus_override is not None else (prof + str_mod),
        "attack_bonus_override": attack_bonus_override,
        "ranged_attack_bonus": ranged_atk_bonus,
        "melee_damage_bonus":  melee_damage_bonus,
        "spell_save_dc":       spell_save_dc,
        "spell_attack_bonus":  spell_attack_bonus,
        "spell_ability":       spell_ability_key,
        "ability_modifiers":   {
            "str": str_mod, "dex": dex_mod, "con": con_mod,
            "int": int_mod, "wis": wis_mod, "cha": cha_mod,
        },
        "saving_throws":       saving_throws,
        "spell_slots_max":     spell_slots_max,
        "hit_die":             hit_die,
        "caster_type":         CASTER_TYPE.get(cls_key),
        "cantrips_count":      get_cantrips_count(cls_key, level),
        # 子职业效果
        "crit_threshold":      crit_threshold,
        "bonus_healing":       bonus_healing,
        "subclass_effects":    subclass_effects,
        # 战斗风格
        "fighting_style":      fighting_style,
        "two_weapon_fighting": two_weapon_fighting,
        "style_effects":       style_effects,
        # 装备
        "equipped_weapon_damage": equipped_weapon_damage,
        "equipped_weapon_type":   equipped_weapon_type,
        "armor_proficiencies":    armor_proficiencies,
        "weapon_proficiencies":   weapon_proficiencies,
        # 专长
        "feat_effects":        feat_effects,
        # 感知与视觉
        "passive_perception":  passive_perception,
        "darkvision":          darkvision,
    }
