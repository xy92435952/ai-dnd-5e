from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models import Character
from schemas.character_requests import ExhaustionRequest, LevelUpRequest, PreparedSpellsRequest
from services.character_leveling_service import CharacterLevelingError, build_level_up_update
from services.character_serializer import serialize_character
from services.character_spell_service import CharacterSpellError, build_prepared_spells_update


async def update_character_prepared_spells(
    *,
    db: AsyncSession,
    character_id: str,
    req: PreparedSpellsRequest,
) -> dict:
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


async def level_up_character(
    *,
    db: AsyncSession,
    character_id: str,
    req: LevelUpRequest,
) -> dict:
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


async def update_character_exhaustion(
    *,
    db: AsyncSession,
    character_id: str,
    req: ExhaustionRequest,
) -> dict:
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404, "角色不存在")

    conditions = list(char.conditions or [])
    durations = dict(char.condition_durations or {})
    current_level = durations.get("exhaustion_level", 0)
    new_level = max(0, min(6, current_level + req.change))
    durations["exhaustion_level"] = new_level

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
