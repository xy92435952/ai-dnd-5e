from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

from database import get_db
from models import Character, Module, Session
from services.dnd_rules import (
    calc_derived, apply_racial_bonuses, _normalize_class,
    get_cantrips_count, get_spell_slots, ability_modifier,
    proficiency_bonus as calc_proficiency_bonus,
    RACES, CLASSES, BACKGROUNDS, ALIGNMENTS,
    RACIAL_ABILITY_BONUSES, CLASS_SAVE_PROFICIENCIES,
    CLASS_SKILL_CHOICES, ALL_SKILLS,
    STARTING_SPELLS_COUNT, SPELLCASTER_CLASSES,
    FIGHTING_STYLES, FIGHTING_STYLE_CLASSES,
    WEAPONS, ARMOR, STARTING_EQUIPMENT,
    BACKGROUND_FEATURES, RACIAL_LANGUAGES, ALL_LANGUAGES,
    SPELL_PREPARATION_TYPE, SUBCLASS_BONUS_SPELLS,
    FEATS, ASI_LEVELS, ASI_LEVELS_FIGHTER, ASI_LEVELS_ROGUE,
    CLASS_ARMOR_PROFICIENCY, CLASS_WEAPON_PROFICIENCY,
    RACIAL_DARKVISION, EXHAUSTION_EFFECTS,
    HIT_DICE, roll_dice,
    get_class_resource_defaults,
    SHOP_GEAR, get_item_zh,
)
from services.langgraph_client import langgraph_client as dify_client
from services.spell_service import spell_service
from schemas.game_responses import (
    CharacterDetail, CharacterOptionsResponse, GeneratePartyResponse,
)

router = APIRouter(prefix="/characters", tags=["characters"])


# ── Pydantic Schemas ──────────────────────────────────────

class AbilityScores(BaseModel):
    # str/int 是 Python 内置名，用 alias 避免 Pydantic v2 字段名冲突
    model_config = ConfigDict(populate_by_name=True)

    str_: int = Field(ge=3, le=30, alias="str")
    dex:  int = Field(ge=3, le=30)
    con:  int = Field(ge=3, le=30)
    int_: int = Field(ge=3, le=30, alias="int")
    wis:  int = Field(ge=3, le=30)
    cha:  int = Field(ge=3, le=30)


class CreateCharacterRequest(BaseModel):
    module_id:   str
    name:        str
    race:        str
    char_class:  str
    subclass:    Optional[str] = None
    level:       int = 1
    background:  Optional[str] = None
    alignment:   Optional[str] = None
    ability_scores: AbilityScores
    # 玩家选择的技能熟练（前端从 CLASS_SKILL_CHOICES 给出的选项中选）
    proficient_skills: list[str] = []
    # 可选：已知法术/戏法（施法职业在创建时选择）
    known_spells: list[str] = []
    cantrips:     list[str] = []
    # 可选：双职业信息
    multiclass_info: Optional[dict] = None
    # Phase 12 新增
    fighting_style: Optional[str] = None         # "Archery" / "Defense" / ...
    equipment_choice: Optional[int] = None       # 起始装备方案索引（0 or 1）
    bonus_languages: list[str] = []              # 种族/背景额外语言选择
    feats: list[dict] = []                       # [{"name":"Alert"}, {"name":"Tough","ability":"con"}]


class GeneratePartyRequest(BaseModel):
    module_id:           str
    player_character_id: str
    party_size:          int = 4


# ── Endpoints ─────────────────────────────────────────────

@router.get("/options", response_model=CharacterOptionsResponse)
async def get_character_options():
    """获取角色创建所有可选项，含种族加值/职业技能选择等元数据"""
    # 为每个施法职业构建可选戏法/法术列表
    class_cantrips = {
        cls: [s["name"] for s in spell_service.get_cantrips_for_class(cls)]
        for cls in SPELLCASTER_CLASSES
    }
    class_spells = {
        cls: [s["name"] for s in spell_service.get_for_class(cls) if s["level"] > 0]
        for cls in SPELLCASTER_CLASSES
    }
    starting_cantrips_count = {
        cls: get_cantrips_count(cls, 1)
        for cls in SPELLCASTER_CLASSES
    }

    return {
        "races":       RACES,
        "classes":     CLASSES,
        "backgrounds": BACKGROUNDS,
        "alignments":  ALIGNMENTS,
        # 前端用于展示种族加值预览
        "racial_bonuses":        RACIAL_ABILITY_BONUSES,
        # 前端用于展示技能选择界面
        "class_skill_choices":   CLASS_SKILL_CHOICES,
        # 前端用于展示豁免熟练说明
        "class_save_proficiencies": CLASS_SAVE_PROFICIENCIES,
        "all_skills":            ALL_SKILLS,
        # 法术选择元数据
        "class_cantrips":         class_cantrips,
        "class_spells":           class_spells,
        "starting_cantrips_count": starting_cantrips_count,
        "starting_spells_count":  STARTING_SPELLS_COUNT,
        "spellcaster_classes":    SPELLCASTER_CLASSES,
        # Phase 12: 战斗风格 / 装备 / 背景 / 语言 / 专长
        "fighting_styles":         FIGHTING_STYLES,
        "fighting_style_classes":  FIGHTING_STYLE_CLASSES,
        "weapons":                 WEAPONS,
        "armor":                   ARMOR,
        "starting_equipment":      STARTING_EQUIPMENT,
        "background_features":     BACKGROUND_FEATURES,
        "racial_languages":        RACIAL_LANGUAGES,
        "all_languages":           ALL_LANGUAGES,
        "spell_preparation_type":  SPELL_PREPARATION_TYPE,
        "subclass_bonus_spells":   SUBCLASS_BONUS_SPELLS,
        "feats":                   FEATS,
        "asi_levels":              ASI_LEVELS,
        "asi_levels_fighter":      ASI_LEVELS_FIGHTER,
        "asi_levels_rogue":        ASI_LEVELS_ROGUE,
        "class_armor_proficiency": CLASS_ARMOR_PROFICIENCY,
        "class_weapon_proficiency":CLASS_WEAPON_PROFICIENCY,
    }


@router.post("/create", response_model=CharacterDetail)
async def create_character(
    req: CreateCharacterRequest,
    db: AsyncSession = Depends(get_db),
):
    """创建玩家角色（含种族加值、熟练校验）"""
    # 校验模组
    result = await db.execute(select(Module).where(Module.id == req.module_id))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(404, "模组不存在")
    if module.parse_status != "done":
        raise HTTPException(400, "模组尚未解析完成，请稍后再试")
    # 等级为建议范围，允许玩家自由选择1-20（仅警告不阻止）
    if not (1 <= req.level <= 20):
        raise HTTPException(400, "角色等级须在 1-20 之间")

    # 1. 获取基础能力值（by_alias=True 确保键名为 str/int 而非 str_/int_）
    base_scores = req.ability_scores.model_dump(by_alias=True)

    # 2. 应用种族加值（正确的5e流程）
    final_scores = apply_racial_bonuses(base_scores, req.race)

    # 3. 确定职业标准名
    cls_key = _normalize_class(req.char_class)

    # 4. 验证战斗风格（如果提供）
    fighting_style = req.fighting_style
    if fighting_style:
        fs_config = FIGHTING_STYLE_CLASSES.get(cls_key)
        if not fs_config:
            fighting_style = None  # 该职业无战斗风格，忽略
        elif req.level < fs_config["level"]:
            fighting_style = None  # 等级不够
        elif fighting_style not in fs_config["styles"]:
            raise HTTPException(400, f"战斗风格【{fighting_style}】不在{req.char_class}可选范围内")

    # 5. 构建装备
    equipment_data = {}
    if req.equipment_choice is not None:
        eq_options = STARTING_EQUIPMENT.get(cls_key, [])
        if 0 <= req.equipment_choice < len(eq_options):
            chosen_eq = eq_options[req.equipment_choice]
            weapons, armor_list, shield, gear = [], [], None, []
            for item in chosen_eq["items"]:
                slot = item.get("slot", "gear")
                name = item.get("name", "")
                if slot == "weapon" or slot == "weapon2":
                    w = WEAPONS.get(name)
                    if w:
                        weapons.append({**w, "name": name, "equipped": slot == "weapon"})
                    else:
                        gear.append({"name": name, "zh": get_item_zh(name)})
                elif slot == "armor":
                    a = ARMOR.get(name)
                    if a:
                        armor_list.append({**a, "name": name, "equipped": True})
                elif slot == "offhand" and name == "Shield":
                    shield = {"name": "Shield", "zh": "盾牌", "ac": 2, "equipped": True}
                else:
                    gear.append({"name": name, "zh": get_item_zh(name)})
            equipment_data = {"weapons": weapons, "armor": armor_list, "shield": shield, "gear": gear, "gold": 10}

    # 6. 背景特性 → 技能/语言/工具
    bg_features = BACKGROUND_FEATURES.get(req.background or "", {})
    bg_skills = bg_features.get("skills", [])
    bg_tools = bg_features.get("tools", [])

    # 7. 语言（种族固定 + 背景/种族额外选择）
    race_lang = RACIAL_LANGUAGES.get(req.race, {"fixed": ["Common"], "bonus": 0})
    languages = list(race_lang["fixed"])
    # 背景额外语言数
    bg_lang_bonus = bg_features.get("languages", 0)
    total_bonus = race_lang["bonus"] + bg_lang_bonus
    for lang in req.bonus_languages[:total_bonus]:
        if lang in ALL_LANGUAGES and lang not in languages:
            languages.append(lang)

    # 8. 校验技能熟练选择数量
    skill_config  = CLASS_SKILL_CHOICES.get(cls_key, {"count": 2, "options": ALL_SKILLS})
    allowed_count = skill_config["count"]
    allowed_opts  = skill_config["options"]
    chosen_skills = list(req.proficient_skills)

    if len(chosen_skills) > allowed_count:
        raise HTTPException(
            400,
            f"{req.char_class} 只能选 {allowed_count} 个技能熟练，您选了 {len(chosen_skills)} 个"
        )
    for skill in chosen_skills:
        if allowed_opts != ALL_SKILLS and skill not in allowed_opts:
            raise HTTPException(400, f"技能【{skill}】不在该职业可选范围内")
    # 合并背景技能（不重复）
    for bs in bg_skills:
        if bs not in chosen_skills:
            chosen_skills.append(bs)

    # 9. 确定豁免熟练（由职业决定）
    save_profs = CLASS_SAVE_PROFICIENCIES.get(cls_key, [])

    # 10. 计算衍生属性（含战斗风格、装备、专长效果）
    derived = calc_derived(
        req.char_class, req.level, final_scores, req.subclass,
        fighting_style=fighting_style,
        feats=req.feats or None,
        equipment=equipment_data or None,
        race=req.race,
        proficient_skills=chosen_skills,
    )

    # 11. 子职业额外法术
    bonus_spells = []
    if req.subclass:
        sub_spells = SUBCLASS_BONUS_SPELLS.get(req.subclass, {})
        for spell_level, spells in sub_spells.items():
            if req.level >= int(spell_level):
                bonus_spells.extend(spells)

    prepared = list(req.known_spells)  # 初始准备 = 已知
    for sp in bonus_spells:
        if sp not in prepared:
            prepared.append(sp)

    # 12. 初始化法术位（当前剩余 = 满血）
    spell_slots = dict(derived.get("spell_slots_max", {}))

    # Initialize class resources (ki, superiority dice, portent, etc.)
    class_resources = get_class_resource_defaults(cls_key, req.level, subclass=req.subclass)

    character = Character(
        is_player         = True,
        name              = req.name,
        race              = req.race,
        char_class        = req.char_class,
        subclass          = req.subclass,
        level             = req.level,
        background        = req.background,
        alignment         = req.alignment,
        ability_scores    = final_scores,
        derived           = derived,
        hp_current        = derived["hp_max"],
        spell_slots       = spell_slots,
        known_spells      = req.known_spells,
        prepared_spells   = prepared,
        cantrips          = req.cantrips,
        proficient_skills = chosen_skills,
        proficient_saves  = save_profs,
        multiclass_info   = req.multiclass_info,
        class_resources   = class_resources,
        # Phase 12 新增
        fighting_style    = fighting_style,
        equipment         = equipment_data,
        languages         = languages,
        tool_proficiencies= bg_tools,
        feats             = req.feats,
    )
    db.add(character)
    await db.commit()
    await db.refresh(character)

    return _serialize_character(character)


@router.post("/generate-party", response_model=GeneratePartyResponse)
async def generate_party(
    req: GeneratePartyRequest,
    db: AsyncSession = Depends(get_db),
):
    """生成AI队友（调用 Dify WF2），自动应用种族加值和熟练"""
    result = await db.execute(select(Character).where(Character.id == req.player_character_id))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(404, "玩家角色不存在")

    mod_result = await db.execute(select(Module).where(Module.id == req.module_id))
    module = mod_result.scalar_one_or_none()
    if not module:
        raise HTTPException(404, "模组不存在")

    companions_data = await dify_client.generate_party(
        player_class  = player.char_class,
        player_race   = player.race,
        player_level  = player.level,
        party_size    = req.party_size,
        module_data   = module.parsed_content or {},
    )

    companions = []
    for c in companions_data:
        base_scores = c.get("ability_scores", {
            "str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10,
        })
        companion_race  = c.get("race", "人类")
        companion_class = c.get("class", "Fighter")
        companion_level = c.get("level", player.level)

        # 同样应用种族加值
        final_scores = apply_racial_bonuses(base_scores, companion_race)

        # 职业豁免熟练
        cls_key    = _normalize_class(companion_class)
        save_profs = CLASS_SAVE_PROFICIENCIES.get(cls_key, [])

        # 从 AI 返回数据取技能熟练，或用职业默认前N个
        ai_skills     = c.get("proficient_skills", [])
        skill_config  = CLASS_SKILL_CHOICES.get(cls_key, {"count": 2, "options": ALL_SKILLS})
        if not ai_skills:
            ai_skills = skill_config["options"][:skill_config["count"]]

        derived = calc_derived(companion_class, companion_level, final_scores, c.get("subclass"),
                               race=companion_race, proficient_skills=ai_skills)

        # 初始化法术位
        spell_slots = dict(derived.get("spell_slots_max", {}))

        companion = Character(
            is_player         = False,
            name              = c.get("name", "未知冒险者"),
            race              = companion_race,
            char_class        = companion_class,
            subclass          = c.get("subclass"),
            level             = companion_level,
            background        = c.get("background"),
            alignment         = c.get("alignment", "中立善良"),
            ability_scores    = final_scores,
            derived           = derived,
            hp_current        = derived["hp_max"],
            spell_slots       = spell_slots,
            known_spells      = c.get("known_spells", []),
            cantrips          = c.get("cantrips", []),
            proficient_skills = ai_skills,
            proficient_saves  = save_profs,
            personality       = c.get("personality_traits", ""),
            speech_style      = c.get("speech_style", ""),
            combat_preference = c.get("combat_preference", ""),
            backstory         = c.get("backstory", ""),
            catchphrase       = c.get("catchphrase", ""),
        )
        db.add(companion)
        await db.flush()
        companions.append(_serialize_character(companion))

    await db.commit()
    return {"companions": companions}


# ── Shop System (V2) — inventory must be before /{character_id} to avoid route conflict ──

@router.get("/shop/inventory")
async def get_shop_inventory():
    """Return all available items for purchase (weapons, armor, gear)."""
    return {
        "weapons": {name: {**data, "category": "weapon"} for name, data in WEAPONS.items()},
        "armor": {name: {**data, "category": "armor"} for name, data in ARMOR.items()},
        "gear": {name: {**data, "category": "gear"} for name, data in SHOP_GEAR.items()},
    }


@router.get("/{character_id}", response_model=CharacterDetail)
async def get_character(character_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Character).where(Character.id == character_id))
    char = result.scalar_one_or_none()
    if not char:
        raise HTTPException(404, "角色不存在")
    return _serialize_character(char)


class PreparedSpellsRequest(BaseModel):
    prepared_spells: list[str]


@router.patch("/{character_id}/prepared-spells")
async def update_prepared_spells(
    character_id: str,
    req: PreparedSpellsRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新已准备法术（法师/牧师/德鲁伊专用，上限 = 等级 + 施法调整值）"""
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")

    known = set(char.known_spells or [])
    for sp in req.prepared_spells:
        if sp not in known:
            raise HTTPException(400, f"法术【{sp}】不在已知法术列表中")

    # 计算准备上限
    derived     = char.derived or {}
    mods        = derived.get("ability_modifiers", {})
    spell_ab    = derived.get("spell_ability")
    spell_mod   = mods.get(spell_ab, 0) if spell_ab else 0
    max_prepared = max(1, char.level + spell_mod)

    if len(req.prepared_spells) > max_prepared:
        raise HTTPException(400, f"已备法术上限为 {max_prepared}（等级{char.level}+修正{spell_mod}），"
                                 f"你选了 {len(req.prepared_spells)} 个")

    char.prepared_spells = req.prepared_spells
    await db.commit()
    return {
        "prepared_spells": char.prepared_spells,
        "max_prepared":    max_prepared,
    }


# ── Level Up (P0-9) ──────────────────────────────────────────

class LevelUpRequest(BaseModel):
    use_average_hp: bool = True           # True=取平均，False=掷骰
    ability_score_increases: Optional[dict] = None  # {"str": 2} 或 {"str": 1, "dex": 1}（ASI等级可用）
    feat_choice: Optional[dict] = None    # {"name": "Alert"} 替代 ASI


@router.post("/{character_id}/level-up")
async def level_up(
    character_id: str,
    req: LevelUpRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    角色升级：递增等级，重算衍生属性，增加HP，更新法术位。
    ASI 等级（4,8,12,16,19; Fighter额外6,14; Rogue额外10）可增加属性或选择专长。
    """
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")

    old_level = char.level
    new_level = old_level + 1
    if new_level > 20:
        raise HTTPException(400, "角色已达最高等级20")

    cls_key = _normalize_class(char.char_class)
    hit_die = HIT_DICE.get(cls_key, 8)
    con_mod = ability_modifier(char.ability_scores.get("con", 10))

    # HP increase
    if req.use_average_hp:
        hp_gain = hit_die // 2 + 1 + con_mod
    else:
        hp_roll = roll_dice(f"1d{hit_die}")
        hp_gain = max(1, hp_roll["total"] + con_mod)

    # ASI check
    asi_levels = ASI_LEVELS
    if cls_key == "Fighter":
        asi_levels = ASI_LEVELS_FIGHTER
    elif cls_key == "Rogue":
        asi_levels = ASI_LEVELS_ROGUE

    ability_scores = dict(char.ability_scores)
    current_feats = list(char.feats or [])

    if new_level in asi_levels:
        if req.feat_choice:
            # Choose feat instead of ASI
            fname = req.feat_choice.get("name", "")
            if fname not in FEATS:
                raise HTTPException(400, f"未知专长：{fname}")
            current_feats.append(req.feat_choice)
        elif req.ability_score_increases:
            # Apply ASI (max +2 total, no ability above 20)
            total_increase = sum(req.ability_score_increases.values())
            if total_increase > 2:
                raise HTTPException(400, "ASI每次最多增加2点属性值")
            for ab, inc in req.ability_score_increases.items():
                if ab in ability_scores:
                    ability_scores[ab] = min(20, ability_scores[ab] + inc)

    char.level = new_level
    char.ability_scores = ability_scores
    char.feats = current_feats

    # Recalculate derived stats
    derived = calc_derived(
        char.char_class, new_level, ability_scores, char.subclass,
        fighting_style=char.fighting_style,
        feats=current_feats or None,
        equipment=char.equipment or None,
        race=char.race,
        proficient_skills=char.proficient_skills or [],
    )
    char.derived = derived

    # Update HP (add gain, adjust for new max)
    old_max = (char.derived or {}).get("hp_max", char.hp_current)
    new_max = derived["hp_max"]
    char.hp_current = min(char.hp_current + hp_gain, new_max)

    # Update spell slots to new max
    new_slots_max = derived.get("spell_slots_max", {})
    old_slots = dict(char.spell_slots or {})
    # Add any new slots gained, keep existing spent slots
    for slot_key, max_val in new_slots_max.items():
        old_val = old_slots.get(slot_key, 0)
        old_max_val = (char.derived or {}).get("spell_slots_max", {}).get(slot_key, 0)
        # Add the difference between new max and old max
        gained = max(0, max_val - old_max_val)
        old_slots[slot_key] = min(max_val, old_val + gained)
    char.spell_slots = old_slots

    await db.commit()
    await db.refresh(char)

    return {
        "character": _serialize_character(char),
        "level_up_details": {
            "old_level": old_level,
            "new_level": new_level,
            "hp_gain": hp_gain,
            "is_asi_level": new_level in asi_levels,
            "new_spell_slots": new_slots_max,
        },
    }


# ── Gold / Currency (P2-1) ──────────────────────────────────

class GoldRequest(BaseModel):
    amount: int           # positive=gain, negative=spend
    reason: str = ""


@router.patch("/{character_id}/gold")
async def update_gold(
    character_id: str,
    req: GoldRequest,
    db: AsyncSession = Depends(get_db),
):
    """Add or spend gold. Equipment.gold tracks the character's gold."""
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")

    equipment = dict(char.equipment or {})
    current_gold = equipment.get("gold", 0)
    new_gold = current_gold + req.amount
    if new_gold < 0:
        raise HTTPException(400, f"金币不足：当前 {current_gold}，需要 {abs(req.amount)}")

    equipment["gold"] = new_gold
    char.equipment = equipment
    await db.commit()

    return {"gold": new_gold, "change": req.amount, "reason": req.reason}


# ── Exhaustion (P2-2) ───────────────────────────────────────

class ExhaustionRequest(BaseModel):
    change: int = 1  # positive=gain exhaustion, negative=remove


@router.patch("/{character_id}/exhaustion")
async def update_exhaustion(
    character_id: str,
    req: ExhaustionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Increase or decrease exhaustion level (0-6). Level 6 = death."""
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")

    conditions = list(char.conditions or [])
    # Track exhaustion level in condition_durations with special key
    durations = dict(char.condition_durations or {})
    current_level = durations.get("exhaustion_level", 0)
    new_level = max(0, min(6, current_level + req.change))
    durations["exhaustion_level"] = new_level

    # Update condition list
    if new_level > 0 and "exhaustion" not in conditions:
        conditions.append("exhaustion")
    elif new_level == 0 and "exhaustion" in conditions:
        conditions = [c for c in conditions if c != "exhaustion"]

    char.conditions = conditions
    char.condition_durations = durations
    await db.commit()

    from services.dnd_rules import get_exhaustion_effects
    effects = get_exhaustion_effects(new_level)

    return {
        "exhaustion_level": new_level,
        "effects": effects,
        "is_dead": new_level >= 6,
    }


# ── Ammunition Tracking (P2-4) ──────────────────────────────

class AmmoRequest(BaseModel):
    weapon_name: str
    change: int = -1  # negative=use, positive=recover


@router.patch("/{character_id}/ammo")
async def update_ammo(
    character_id: str,
    req: AmmoRequest,
    db: AsyncSession = Depends(get_db),
):
    """Track ammunition for ranged weapons."""
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")

    equipment = dict(char.equipment or {})
    weapons = list(equipment.get("weapons", []))

    found = False
    for w in weapons:
        if w.get("name") == req.weapon_name:
            current_ammo = w.get("ammo", 20)
            new_ammo = max(0, current_ammo + req.change)
            w["ammo"] = new_ammo
            found = True
            break

    if not found:
        raise HTTPException(404, f"未找到武器：{req.weapon_name}")

    equipment["weapons"] = weapons
    char.equipment = equipment
    await db.commit()

    return {"weapon": req.weapon_name, "ammo": new_ammo, "change": req.change}


# ── Equipment Management (V2) ──────────────────────────────

class EquipmentUpdateRequest(BaseModel):
    """Equip or unequip a weapon/armor item."""
    item_name: str
    item_category: str       # "weapon" | "armor" | "shield"
    equip: bool = True       # True=equip, False=unequip


@router.patch("/{character_id}/equipment")
async def update_equipment(
    character_id: str,
    req: EquipmentUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update character equipment (equip/unequip weapons/armor).
    Recalculates derived stats when AC-affecting items change."""
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")

    equipment = dict(char.equipment or {})

    if req.item_category == "weapon":
        weapons = list(equipment.get("weapons", []))
        found = False
        for w in weapons:
            if w.get("name") == req.item_name:
                w["equipped"] = req.equip
                found = True
                break
        if not found:
            raise HTTPException(404, f"背包中未找到武器：{req.item_name}")
        equipment["weapons"] = weapons

    elif req.item_category == "armor":
        armor_list = list(equipment.get("armor", []))
        found = False
        for a in armor_list:
            if a.get("name") == req.item_name:
                # Unequip other armor first (can only wear one)
                if req.equip:
                    for other in armor_list:
                        other["equipped"] = False
                a["equipped"] = req.equip
                found = True
                break
        if not found:
            raise HTTPException(404, f"背包中未找到护甲：{req.item_name}")
        equipment["armor"] = armor_list

    elif req.item_category == "shield":
        shield = equipment.get("shield")
        if not shield:
            raise HTTPException(404, "背包中没有盾牌")
        shield["equipped"] = req.equip
        equipment["shield"] = shield

    else:
        raise HTTPException(400, f"无效的物品类别：{req.item_category}")

    char.equipment = equipment

    # Recalculate derived stats (AC changes with armor/shield)
    derived = calc_derived(
        char.char_class, char.level, char.ability_scores, char.subclass,
        fighting_style=char.fighting_style,
        feats=char.feats or None,
        equipment=equipment,
        race=char.race,
        proficient_skills=char.proficient_skills or [],
    )
    char.derived = derived

    await db.commit()
    await db.refresh(char)

    return {
        "equipment": char.equipment,
        "derived": derived,
        "ac": derived.get("ac", 10),
    }


class EquipmentBulkUpdateRequest(BaseModel):
    """Accept the full equipment dict from CharacterSheet (equip/unequip toggles)."""
    equipment: dict


@router.patch("/{character_id}/equipment-bulk")
async def update_equipment_bulk(
    character_id: str,
    req: EquipmentBulkUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Replace full equipment dict and recalculate derived stats."""
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")

    char.equipment = req.equipment

    derived = calc_derived(
        char.char_class, char.level, char.ability_scores, char.subclass,
        fighting_style=char.fighting_style,
        feats=char.feats or None,
        equipment=req.equipment,
        race=char.race,
        proficient_skills=char.proficient_skills or [],
    )
    char.derived = derived

    await db.commit()
    await db.refresh(char)

    return {
        "ok": True,
        "equipment": char.equipment,
        "derived": derived,
    }


class BuyItemRequest(BaseModel):
    item_name: str
    item_category: str       # "weapon" | "armor" | "gear"
    quantity: int = 1


@router.post("/{character_id}/shop/buy")
async def buy_item(
    character_id: str,
    req: BuyItemRequest,
    db: AsyncSession = Depends(get_db),
):
    """Buy an item from the shop. Deducts gold and adds to equipment."""
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")

    # Look up item and cost
    if req.item_category == "weapon":
        item_data = WEAPONS.get(req.item_name)
    elif req.item_category == "armor":
        item_data = ARMOR.get(req.item_name)
    elif req.item_category == "gear":
        item_data = SHOP_GEAR.get(req.item_name)
    else:
        raise HTTPException(400, f"无效的物品类别：{req.item_category}")

    if not item_data:
        raise HTTPException(404, f"商店中未找到物品：{req.item_name}")

    cost = item_data.get("cost", 0) * req.quantity
    equipment = dict(char.equipment or {})
    current_gold = equipment.get("gold", 0)

    if current_gold < cost:
        raise HTTPException(400, f"金币不足：当前 {current_gold} gp，需要 {cost} gp")

    # Deduct gold
    equipment["gold"] = current_gold - cost

    # Add item to appropriate slot
    if req.item_category == "weapon":
        weapons = list(equipment.get("weapons", []))
        for _ in range(req.quantity):
            weapons.append({**item_data, "name": req.item_name, "equipped": False})
        equipment["weapons"] = weapons

    elif req.item_category == "armor":
        if req.item_name == "Shield":
            equipment["shield"] = {"name": "Shield", "ac": 2, "equipped": False}
        else:
            armor_list = list(equipment.get("armor", []))
            armor_list.append({**item_data, "name": req.item_name, "equipped": False})
            equipment["armor"] = armor_list

    elif req.item_category == "gear":
        gear = list(equipment.get("gear", []))
        for _ in range(req.quantity):
            gear.append({"name": req.item_name, **item_data})
        equipment["gear"] = gear

    char.equipment = equipment
    await db.commit()

    return {
        "bought": req.item_name,
        "quantity": req.quantity,
        "cost": cost,
        "gold_remaining": equipment["gold"],
        "equipment": equipment,
    }


class SellItemRequest(BaseModel):
    item_name: str
    item_category: str       # "weapon" | "armor" | "gear"
    item_index: int = 0      # index in the list (for duplicates)


@router.post("/{character_id}/shop/sell")
async def sell_item(
    character_id: str,
    req: SellItemRequest,
    db: AsyncSession = Depends(get_db),
):
    """Sell an item for half its purchase price. Removes from equipment."""
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")

    equipment = dict(char.equipment or {})

    # Find the item and its sell price
    sell_price = 0
    removed_name = req.item_name

    if req.item_category == "weapon":
        weapons = list(equipment.get("weapons", []))
        # Find item by name, using index to disambiguate duplicates
        matches = [(i, w) for i, w in enumerate(weapons) if w.get("name") == req.item_name]
        if not matches:
            raise HTTPException(404, f"背包中未找到武器：{req.item_name}")
        if req.item_index >= len(matches):
            req.item_index = 0
        actual_idx = matches[req.item_index][0]
        item = matches[req.item_index][1]
        if item.get("equipped"):
            raise HTTPException(400, "不能出售装备中的武器，请先卸下")
        sell_price = item.get("cost", WEAPONS.get(req.item_name, {}).get("cost", 0)) / 2
        weapons.pop(actual_idx)
        equipment["weapons"] = weapons

    elif req.item_category == "armor":
        if req.item_name == "Shield":
            shield = equipment.get("shield")
            if not shield:
                raise HTTPException(404, "背包中没有盾牌")
            if shield.get("equipped"):
                raise HTTPException(400, "不能出售装备中的盾牌，请先卸下")
            sell_price = ARMOR.get("Shield", {}).get("cost", 10) / 2
            equipment["shield"] = None
        else:
            armor_list = list(equipment.get("armor", []))
            matches = [(i, a) for i, a in enumerate(armor_list) if a.get("name") == req.item_name]
            if not matches:
                raise HTTPException(404, f"背包中未找到护甲：{req.item_name}")
            if req.item_index >= len(matches):
                req.item_index = 0
            actual_idx = matches[req.item_index][0]
            item = matches[req.item_index][1]
            if item.get("equipped"):
                raise HTTPException(400, "不能出售装备中的护甲，请先卸下")
            sell_price = item.get("cost", ARMOR.get(req.item_name, {}).get("cost", 0)) / 2
            armor_list.pop(actual_idx)
            equipment["armor"] = armor_list

    elif req.item_category == "gear":
        gear = list(equipment.get("gear", []))
        matches = [(i, g) for i, g in enumerate(gear)
                   if (g.get("name") == req.item_name if isinstance(g, dict) else g == req.item_name)]
        if not matches:
            raise HTTPException(404, f"背包中未找到物品：{req.item_name}")
        if req.item_index >= len(matches):
            req.item_index = 0
        actual_idx = matches[req.item_index][0]
        item = matches[req.item_index][1]
        item_cost = (item.get("cost", 0) if isinstance(item, dict)
                     else SHOP_GEAR.get(req.item_name, {}).get("cost", 0))
        sell_price = item_cost / 2
        gear.pop(actual_idx)
        equipment["gear"] = gear

    else:
        raise HTTPException(400, f"无效的物品类别：{req.item_category}")

    # Add gold (sell at half price, floor to avoid fractional)
    import math
    equipment["gold"] = equipment.get("gold", 0) + math.floor(sell_price)
    char.equipment = equipment

    # Recalculate derived if armor was sold
    if req.item_category == "armor":
        derived = calc_derived(
            char.char_class, char.level, char.ability_scores, char.subclass,
            fighting_style=char.fighting_style,
            feats=char.feats or None,
            equipment=equipment,
            race=char.race,
            proficient_skills=char.proficient_skills or [],
        )
        char.derived = derived

    await db.commit()

    return {
        "sold": removed_name,
        "sell_price": math.floor(sell_price),
        "gold_remaining": equipment["gold"],
        "equipment": equipment,
    }


# ── Use Item / Potion (V2) ────────────────────────────────

class UseItemRequest(BaseModel):
    item_name: str


@router.post("/{character_id}/use-item")
async def use_item(
    character_id: str,
    req: UseItemRequest,
    db: AsyncSession = Depends(get_db),
):
    """Use a consumable item (potion, antitoxin, etc.).
    Healing potions roll dice and restore HP."""
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")

    equipment = dict(char.equipment or {})
    gear = list(equipment.get("gear", []))

    # Find the item in gear
    found_idx = None
    found_item = None
    for i, g in enumerate(gear):
        name = g.get("name") if isinstance(g, dict) else g
        if name == req.item_name:
            found_idx = i
            found_item = g
            break

    if found_idx is None:
        raise HTTPException(404, f"背包中未找到物品：{req.item_name}")

    # Get item data (from inventory or SHOP_GEAR)
    if isinstance(found_item, dict):
        item_data = found_item
    else:
        item_data = SHOP_GEAR.get(req.item_name, {})

    if not item_data.get("consumable", False):
        raise HTTPException(400, f"【{req.item_name}】不是消耗品，无法使用")

    result = {"item": req.item_name, "effect": item_data.get("effect", "none")}

    # Apply effect
    effect = item_data.get("effect", "")
    if effect == "heal":
        heal_dice = item_data.get("heal_dice", "2d4+2")
        roll = roll_dice(heal_dice)
        heal_amount = roll["total"]
        derived = char.derived or {}
        hp_max = derived.get("hp_max", char.hp_current)
        old_hp = char.hp_current
        char.hp_current = min(hp_max, char.hp_current + heal_amount)
        result["heal_roll"] = roll
        result["heal_amount"] = heal_amount
        result["hp_before"] = old_hp
        result["hp_after"] = char.hp_current

    elif effect == "antitoxin":
        # Remove poisoned condition if present
        conditions = list(char.conditions or [])
        if "poisoned" in conditions:
            conditions = [c for c in conditions if c != "poisoned"]
            char.conditions = conditions
            result["removed_condition"] = "poisoned"
        result["description"] = "对毒素的豁免检定获得优势，持续1小时"

    elif effect == "fire_resistance":
        result["description"] = "获得火焰伤害抗性，持续1小时"

    # Handle items with uses (e.g., Healer's Kit)
    uses = item_data.get("uses")
    if uses is not None and uses > 1:
        # Decrement uses instead of removing
        if isinstance(gear[found_idx], dict):
            gear[found_idx]["uses"] = uses - 1
            result["uses_remaining"] = uses - 1
        else:
            gear.pop(found_idx)
    else:
        # Remove consumed item
        gear.pop(found_idx)

    equipment["gear"] = gear
    char.equipment = equipment
    await db.commit()

    return result


# ── Helpers ───────────────────────────────────────────────

def _serialize_character(char: Character) -> dict:
    derived = char.derived or {}
    return {
        "id":              char.id,
        "is_player":       char.is_player,
        "name":            char.name,
        "race":            char.race,
        "char_class":      char.char_class,
        "subclass":        char.subclass,
        "level":           char.level,
        "background":      char.background,
        "alignment":       char.alignment,
        "ability_scores":  char.ability_scores,
        "derived":         derived,
        "hp_current":      char.hp_current,
        "hp_max":          derived.get("hp_max", char.hp_current),
        "ac":              derived.get("ac", 10),
        # 法术系统
        "spell_slots":     char.spell_slots or {},
        "spell_slots_max": derived.get("spell_slots_max", {}),
        "known_spells":    char.known_spells or [],
        "prepared_spells": char.prepared_spells or [],
        "cantrips":        char.cantrips or [],
        "concentration":   char.concentration,
        "caster_type":     derived.get("caster_type"),
        "cantrips_count":  derived.get("cantrips_count", 0),
        # 熟练
        "proficient_skills": char.proficient_skills or [],
        "proficient_saves":  char.proficient_saves or [],
        # 状态与装备
        "equipment":          char.equipment or {},
        "fighting_style":     char.fighting_style,
        "languages":          char.languages or [],
        "tool_proficiencies": char.tool_proficiencies or [],
        "feats":              char.feats or [],
        "conditions":  char.conditions or [],
        "death_saves": char.death_saves,
        # AI队友专属
        "personality":       char.personality,
        "speech_style":      char.speech_style,
        "combat_preference": char.combat_preference,
        "backstory":         char.backstory,
        "catchphrase":       char.catchphrase,
        # 双职业
        "multiclass_info":      char.multiclass_info,
        # 子职业效果（前端可读取 crit_threshold / bonus_healing 等）
        "subclass_effects":     (char.derived or {}).get("subclass_effects", {}),
        "condition_durations":  char.condition_durations or {},
    }
