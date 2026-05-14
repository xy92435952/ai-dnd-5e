from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import Character, Module
from services.dnd_rules import (
    calc_derived, apply_racial_bonuses, _normalize_class,
    proficiency_bonus as calc_proficiency_bonus,
    CLASS_SAVE_PROFICIENCIES,
    BACKGROUND_FEATURES,
    SUBCLASS_BONUS_SPELLS,
    RACIAL_DARKVISION, EXHAUSTION_EFFECTS,
    get_class_resource_defaults,
)
from services.langgraph_client import langgraph_client as dify_client
from services.character_creation_service import (
    CharacterCreationError,
    build_character_languages,
    build_proficient_skills,
    build_starting_equipment,
    normalize_fighting_style,
)
from services.character_companion_service import build_companion_character
from services.character_leveling_service import CharacterLevelingError, build_level_up_update
from services.character_options_service import build_character_options
from services.character_serializer import serialize_character
from services.character_spell_service import CharacterSpellError, build_prepared_spells_update
from services.spell_service import spell_service
from schemas.game_responses import (
    CharacterDetail, CharacterOptionsResponse, GeneratePartyResponse,
    PreparedSpellsResult, ExhaustionUpdateResult, LevelUpResult,
)
from schemas.character_requests import (
    CreateCharacterRequest,
    ExhaustionRequest,
    GeneratePartyRequest,
    LevelUpRequest,
    PreparedSpellsRequest,
)

router = APIRouter(prefix="/characters", tags=["characters"])


# ── Endpoints ─────────────────────────────────────────────

@router.get("/options", response_model=CharacterOptionsResponse)
async def get_character_options():
    """获取角色创建所有可选项，含种族加值/职业技能选择等元数据"""
    return build_character_options(spell_service)


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
    try:
        fighting_style = normalize_fighting_style(
            cls_key=cls_key,
            class_label=req.char_class,
            level=req.level,
            fighting_style=req.fighting_style,
        )
    except CharacterCreationError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    # 5. 构建装备
    equipment_data = build_starting_equipment(cls_key, req.equipment_choice)

    # 6. 背景特性 → 技能/语言/工具
    bg_features = BACKGROUND_FEATURES.get(req.background or "", {})
    bg_skills = bg_features.get("skills", [])
    bg_tools = bg_features.get("tools", [])

    # 7. 语言（种族固定 + 背景/种族额外选择）
    languages = build_character_languages(
        race=req.race,
        background_features=bg_features,
        bonus_languages=req.bonus_languages,
    )

    # 8. 校验并合并技能熟练（职业选择 + 背景固定）
    try:
        chosen_skills = build_proficient_skills(
            cls_key=cls_key,
            class_label=req.char_class,
            selected_skills=req.proficient_skills,
            background_skills=bg_skills,
        )
    except CharacterCreationError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

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
        # 角色叙事（玩家可选填，DM 据此代演）
        personality       = req.personality,
        backstory         = req.backstory,
        speech_style      = req.speech_style,
        combat_preference = req.combat_preference,
        catchphrase       = req.catchphrase,
    )
    db.add(character)
    await db.commit()
    await db.refresh(character)

    return serialize_character(character)


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
        companion = build_companion_character(c, fallback_level=player.level)
        db.add(companion)
        await db.flush()
        companions.append(serialize_character(companion))

    await db.commit()
    return {"companions": companions}


@router.get("/{character_id}", response_model=CharacterDetail)
async def get_character(character_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Character).where(Character.id == character_id))
    char = result.scalar_one_or_none()
    if not char:
        raise HTTPException(404, "角色不存在")
    return serialize_character(char)


@router.patch("/{character_id}/prepared-spells", response_model=PreparedSpellsResult)
async def update_prepared_spells(
    character_id: str,
    req: PreparedSpellsRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新已准备法术（法师/牧师/德鲁伊专用，上限 = 等级 + 施法调整值）"""
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")

    try:
        result = build_prepared_spells_update(
            known_spells=char.known_spells,
            requested_spells=req.prepared_spells,
            level=char.level,
            derived=char.derived,
        )
    except CharacterSpellError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    char.prepared_spells = result["prepared_spells"]
    await db.commit()
    return result


@router.post("/{character_id}/level-up", response_model=LevelUpResult)
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

    try:
        update = build_level_up_update(
            char_class=char.char_class,
            level=char.level,
            ability_scores=char.ability_scores,
            derived=char.derived,
            hp_current=char.hp_current,
            spell_slots=char.spell_slots,
            use_average_hp=req.use_average_hp,
            subclass=char.subclass,
            fighting_style=char.fighting_style,
            feats=char.feats,
            equipment=char.equipment,
            race=char.race,
            proficient_skills=char.proficient_skills,
            ability_score_increases=req.ability_score_increases,
            feat_choice=req.feat_choice,
        )
    except CharacterLevelingError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    char.level = update["new_level"]
    char.ability_scores = update["ability_scores"]
    char.feats = update["feats"]
    char.derived = update["derived"]
    char.hp_current = update["hp_current"]
    char.spell_slots = update["spell_slots"]

    await db.commit()
    await db.refresh(char)

    return {
        "character": serialize_character(char),
        "level_up_details": {
            "old_level": update["old_level"],
            "new_level": update["new_level"],
            "hp_gain": update["hp_gain"],
            "is_asi_level": update["is_asi_level"],
            "new_spell_slots": update["new_spell_slots"],
        },
    }


@router.patch("/{character_id}/exhaustion", response_model=ExhaustionUpdateResult)
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
