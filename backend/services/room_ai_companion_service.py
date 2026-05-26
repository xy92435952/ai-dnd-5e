"""AI companion listing and fill logic for multiplayer rooms."""

from typing import List

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Character, Module, Session
from services.dnd_rules import get_effective_hp_base, get_effective_hp_max
from services.room_lifecycle_service import is_game_started
from services.room_member_service import list_members_raw


async def list_ai_companions(
    db: AsyncSession,
    session_id: str,
) -> List[dict]:
    """列出该房间的 AI 队友（session_id 匹配 + is_player=False）。"""
    result = await db.execute(
        select(Character)
        .where(Character.session_id == session_id, Character.is_player == False)
        .order_by(Character.id.asc())
    )
    out = []
    for c in result.scalars().all():
        out.append({
            "id": c.id,
            "name": c.name,
            "race": c.race,
            "char_class": c.char_class,
            "level": c.level,
            "hp_max": get_effective_hp_max(c),
            "base_hp_max": get_effective_hp_base(c),
        })
    return out


async def fill_with_ai_companions(
    db: AsyncSession,
    actor_user_id: str,
    session_id: str,
) -> dict:
    """房主触发：根据 max_players 与已认领人数差额，生成 AI 队友补位。"""
    from services.dnd_rules import (
        ALL_SKILLS,
        CLASS_SAVE_PROFICIENCIES,
        CLASS_SKILL_CHOICES,
        _normalize_class,
        apply_racial_bonuses,
        calc_derived,
    )
    from services.langgraph_client import langgraph_client

    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")
    if session.host_user_id != actor_user_id:
        raise HTTPException(403, "只有房主可以补 AI 队友")
    if is_game_started(session):
        raise HTTPException(409, "游戏已经开始，无法补位")

    members = await list_members_raw(db, session_id)
    claimed = [m for m in members if m.character_id]
    if not claimed:
        raise HTTPException(400, "至少需要一位玩家创建并认领角色作为参考")

    existing_ai = await list_ai_companions(db, session_id)
    target_total = session.max_players or 4
    need = target_total - len(members) - len(existing_ai)
    if need <= 0:
        return {"generated": 0, "companions": existing_ai, "already_full": True}

    ref_char = await db.get(Character, claimed[0].character_id)
    if not ref_char:
        raise HTTPException(500, "参考角色加载失败")

    module = await db.get(Module, session.module_id)
    if not module:
        raise HTTPException(404, "模组不存在")

    companions_data = await langgraph_client.generate_party(
        player_class=ref_char.char_class,
        player_race=ref_char.race,
        player_level=ref_char.level,
        party_size=need,
        module_data=module.parsed_content or {},
    )

    new_ids = []
    for c in companions_data[:need]:
        base_scores = c.get("ability_scores", {
            "str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10,
        })
        companion_race = c.get("race", "人类")
        companion_class = c.get("class", "Fighter")
        companion_level = c.get("level", ref_char.level)

        final_scores = apply_racial_bonuses(base_scores, companion_race)
        cls_key = _normalize_class(companion_class)
        save_profs = CLASS_SAVE_PROFICIENCIES.get(cls_key, [])
        ai_skills = c.get("proficient_skills", [])
        skill_config = CLASS_SKILL_CHOICES.get(cls_key, {"count": 2, "options": ALL_SKILLS})
        if not ai_skills:
            ai_skills = (skill_config["options"] or [])[:skill_config["count"]]

        derived = calc_derived(
            companion_class, companion_level, final_scores, c.get("subclass"),
            race=companion_race, proficient_skills=ai_skills,
        )
        spell_slots = dict(derived.get("spell_slots_max", {}))

        companion = Character(
            session_id=session_id,
            is_player=False,
            user_id=None,
            name=c.get("name", "未知冒险者"),
            race=companion_race,
            char_class=companion_class,
            subclass=c.get("subclass"),
            level=companion_level,
            background=c.get("background"),
            alignment=c.get("alignment", "中立善良"),
            ability_scores=final_scores,
            derived=derived,
            hp_current=derived["hp_max"],
            spell_slots=spell_slots,
            known_spells=c.get("known_spells", []),
            cantrips=c.get("cantrips", []),
            proficient_skills=ai_skills,
            proficient_saves=save_profs,
            personality=c.get("personality_traits", ""),
            speech_style=c.get("speech_style", ""),
            combat_preference=c.get("combat_preference", ""),
            backstory=c.get("backstory", ""),
            catchphrase=c.get("catchphrase", ""),
        )
        db.add(companion)
        await db.flush()
        new_ids.append(companion.id)

    await db.commit()
    companions = await list_ai_companions(db, session_id)
    return {"generated": len(new_ids), "companions": companions, "already_full": False}
