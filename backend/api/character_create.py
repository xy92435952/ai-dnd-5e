from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import assert_module_access
from models import Character, Module
from schemas.character_requests import CreateCharacterRequest
from services.character_creation_service import (
    CharacterCreationError,
    build_character_languages,
    build_proficient_skills,
    build_starting_equipment,
    normalize_fighting_style,
)
from services.character_feat_service import (
    CharacterFeatError,
    normalize_starting_feats,
    validate_feat_prerequisites,
)
from services.character_serializer import serialize_character
from services.character_starting_spell_service import (
    CharacterStartingSpellError,
    validate_starting_spell_choices,
)
from services.dnd_rules import (
    BACKGROUND_FEATURES,
    CLASS_SAVE_PROFICIENCIES,
    _normalize_class,
    apply_racial_bonuses,
    calc_derived,
    get_class_resource_defaults,
)
from services.spell_service import spell_service
from services.subclass_spell_service import resolved_subclass_bonus_spell_details


async def create_player_character(
    *,
    db: AsyncSession,
    req: CreateCharacterRequest,
    user_id: str | None = None,
) -> dict:
    result = await db.execute(select(Module).where(Module.id == req.module_id))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(404, "模组不存在")
    if user_id is not None:
        assert_module_access(module, user_id)
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

    equipment_data = build_starting_equipment(
        cls_key,
        req.equipment_choice,
        background=req.background,
    )
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

    try:
        feats = normalize_starting_feats(req.feats)
    except CharacterFeatError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    save_profs = CLASS_SAVE_PROFICIENCIES.get(cls_key, [])
    derived = calc_derived(
        req.char_class,
        req.level,
        final_scores,
        req.subclass,
        fighting_style=fighting_style,
        feats=feats or None,
        equipment=equipment_data or None,
        race=req.race,
        proficient_skills=chosen_skills,
    )

    try:
        spell_choices = validate_starting_spell_choices(
            spell_service=spell_service,
            char_class=cls_key,
            subclass=req.subclass,
            level=req.level,
            derived=derived,
            cantrips=req.cantrips,
            known_spells=req.known_spells,
        )
    except CharacterStartingSpellError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    bonus_spells = [
        spell["name"]
        for spell in resolved_subclass_bonus_spell_details(
            spell_service,
            req.subclass,
            level=req.level,
        )
    ]

    prepared = list(spell_choices["known_spells"])
    for spell in bonus_spells:
        if spell not in prepared:
            prepared.append(spell)

    spell_slots = dict(derived.get("spell_slots_max", {}))
    try:
        validate_feat_prerequisites(
            feats,
            derived=derived,
            known_spells=spell_choices["known_spells"],
            cantrips=spell_choices["cantrips"],
            spell_slots=spell_slots,
        )
    except CharacterFeatError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc

    class_resources = get_class_resource_defaults(cls_key, req.level, subclass=req.subclass)

    character = Character(
        user_id=user_id,
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
        known_spells=spell_choices["known_spells"],
        prepared_spells=prepared,
        cantrips=spell_choices["cantrips"],
        proficient_skills=chosen_skills,
        proficient_saves=save_profs,
        multiclass_info=req.multiclass_info,
        class_resources=class_resources,
        fighting_style=fighting_style,
        equipment=equipment_data,
        languages=languages,
        tool_proficiencies=bg_tools,
        feats=feats,
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
