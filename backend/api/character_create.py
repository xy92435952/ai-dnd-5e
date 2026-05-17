from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Character, Module
from schemas.character_requests import CreateCharacterRequest
from services.character_creation_service import (
    CharacterCreationError,
    build_character_languages,
    build_proficient_skills,
    build_starting_equipment,
    normalize_fighting_style,
)
from services.character_serializer import serialize_character
from services.dnd_rules import (
    BACKGROUND_FEATURES,
    CLASS_SAVE_PROFICIENCIES,
    SUBCLASS_BONUS_SPELLS,
    _normalize_class,
    apply_racial_bonuses,
    calc_derived,
    get_class_resource_defaults,
)


async def create_player_character(
    *,
    db: AsyncSession,
    req: CreateCharacterRequest,
) -> dict:
    result = await db.execute(select(Module).where(Module.id == req.module_id))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(404, "模组不存在")
    if module.parse_status != "done":
        raise HTTPException(400, "模组尚未解析完成，请稍后再试")
    if not (1 <= req.level <= 20):
        raise HTTPException(400, "角色等级须在 1-20 之间")

    base_scores = req.ability_scores.model_dump(by_alias=True)
    final_scores = apply_racial_bonuses(base_scores, req.race)
    cls_key = _normalize_class(req.char_class)

    try:
        fighting_style = normalize_fighting_style(
            cls_key=cls_key,
            class_label=req.char_class,
            level=req.level,
            fighting_style=req.fighting_style,
        )
    except CharacterCreationError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    equipment_data = build_starting_equipment(cls_key, req.equipment_choice)
    bg_features = BACKGROUND_FEATURES.get(req.background or "", {})
    bg_skills = bg_features.get("skills", [])
    bg_tools = bg_features.get("tools", [])
    languages = build_character_languages(
        race=req.race,
        background_features=bg_features,
        bonus_languages=req.bonus_languages,
    )

    try:
        chosen_skills = build_proficient_skills(
            cls_key=cls_key,
            class_label=req.char_class,
            selected_skills=req.proficient_skills,
            background_skills=bg_skills,
        )
    except CharacterCreationError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    save_profs = CLASS_SAVE_PROFICIENCIES.get(cls_key, [])
    derived = calc_derived(
        req.char_class,
        req.level,
        final_scores,
        req.subclass,
        fighting_style=fighting_style,
        feats=req.feats or None,
        equipment=equipment_data or None,
        race=req.race,
        proficient_skills=chosen_skills,
    )

    bonus_spells = []
    if req.subclass:
        sub_spells = SUBCLASS_BONUS_SPELLS.get(req.subclass, {})
        for spell_level, spells in sub_spells.items():
            if req.level >= int(spell_level):
                bonus_spells.extend(spells)

    prepared = list(req.known_spells)
    for spell in bonus_spells:
        if spell not in prepared:
            prepared.append(spell)

    spell_slots = dict(derived.get("spell_slots_max", {}))
    class_resources = get_class_resource_defaults(cls_key, req.level, subclass=req.subclass)

    character = Character(
        is_player=True,
        name=req.name,
        race=req.race,
        char_class=req.char_class,
        subclass=req.subclass,
        level=req.level,
        background=req.background,
        alignment=req.alignment,
        ability_scores=final_scores,
        derived=derived,
        hp_current=derived["hp_max"],
        spell_slots=spell_slots,
        known_spells=req.known_spells,
        prepared_spells=prepared,
        cantrips=req.cantrips,
        proficient_skills=chosen_skills,
        proficient_saves=save_profs,
        multiclass_info=req.multiclass_info,
        class_resources=class_resources,
        fighting_style=fighting_style,
        equipment=equipment_data,
        languages=languages,
        tool_proficiencies=bg_tools,
        feats=req.feats,
        personality=req.personality,
        backstory=req.backstory,
        speech_style=req.speech_style,
        combat_preference=req.combat_preference,
        catchphrase=req.catchphrase,
    )
    db.add(character)
    await db.commit()
    await db.refresh(character)
    return serialize_character(character)
