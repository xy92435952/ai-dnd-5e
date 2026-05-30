from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import assert_character_access, assert_module_access, assert_session_access, can_user_see_log, char_brief, get_session_or_404, get_user_id, serialize_log
from database import get_db
from models import Character, CombatState, GameLog, Module, Session
from schemas.game_requests import CreateSessionRequest
from schemas.game_responses import CreateSessionResponse, SessionDetail, SessionListItem
from services.character_roster import CharacterRoster
from services.dm_styles import normalize_dm_style
from services.game_opening_service import generate_opening
from services.location_graph_service import build_location_graph_from_module, ensure_location_graph_state
from services.loot_service import build_loot_pool_from_module, ensure_loot_state
from services.room_group_service import ensure_multiplayer_state

router = APIRouter(prefix="/game", tags=["game"])


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(
    req: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """创建游戏会话（开始新冒险）"""
    mod_result = await db.execute(select(Module).where(Module.id == req.module_id))
    module = mod_result.scalar_one_or_none()
    if not module:
        raise HTTPException(404, "模组不存在")

    assert_module_access(module, user_id)
    await _assert_session_roster_access(db, req, user_id)

    parsed = module.parsed_content or {}
    scenes = parsed.get("scenes", [])
    raw_scene = scenes[0]["description"] if scenes else ""
    dm_style = normalize_dm_style(req.dm_style)
    first_scene = await _generate_opening_with_legacy_patch(parsed, raw_scene, dm_style)

    location_graph = build_location_graph_from_module(parsed)
    loot_pool = build_loot_pool_from_module(parsed)
    session = Session(
        user_id=user_id,
        module_id=req.module_id,
        player_character_id=req.player_character_id,
        current_scene=first_scene,
        session_history="",
        game_state={
            "companion_ids": req.companion_ids,
            "scene_index": 0,
            "flags": {},
            "dm_style": dm_style,
            "location_graph": location_graph,
            "loot_pool": loot_pool,
        },
        save_name=req.save_name or f"冒险-{module.name}",
    )
    db.add(session)
    await db.flush()

    roster = CharacterRoster(db, session)
    await roster.bind_companions(req.companion_ids)
    player = await db.get(Character, req.player_character_id)
    if player:
        player.session_id = session.id

    db.add(GameLog(
        session_id=session.id,
        role="dm",
        content=f"[开场] {first_scene}",
        log_type="narrative",
    ))
    await db.commit()
    await db.refresh(session)
    return {"session_id": session.id, "opening_scene": first_scene}


@router.get("/sessions", response_model=list[SessionListItem])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """获取当前用户的存档"""
    result = await db.execute(select(Session).where(Session.user_id == user_id).order_by(Session.updated_at.desc()))
    sessions = result.scalars().all()
    out = []
    for session in sessions:
        module = await db.get(Module, session.module_id)
        player = await db.get(Character, session.player_character_id) if session.player_character_id else None
        out.append({
            "id": session.id,
            "save_name": session.save_name,
            "module_name": module.name if module else "未知模组",
            "combat_active": session.combat_active,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            "player_name": player.name if player else None,
            "player_class": player.char_class if player else None,
            "player_level": player.level if player else None,
            "player_race": player.race if player else None,
            "is_multiplayer": session.is_multiplayer,
            "room_code": session.room_code,
            "host_user_id": session.host_user_id,
        })
    return out


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """获取会话完整状态（用于恢复游戏）"""
    session = await get_session_or_404(session_id, db)
    member = await assert_session_access(session, user_id, db)
    if session.is_multiplayer:
        await ensure_multiplayer_state(db, session.id)
    roster = CharacterRoster(db, session)
    player = await roster.player()
    controlled_player = player
    if session.is_multiplayer:
        if member and member.character_id:
            controlled_player = await db.get(Character, member.character_id) or player
    module = await db.get(Module, session.module_id) if session.module_id else None
    companions = [char_brief(character) for character in await roster.companions()]

    log_result = await db.execute(
        select(GameLog)
        .where(GameLog.session_id == session_id)
        .order_by(GameLog.created_at.desc())
        .limit(50)
    )
    logs = list(reversed(log_result.scalars().all()))
    game_state = ensure_location_graph_state(
        session.game_state or {},
        module.parsed_content if module else {},
    )
    game_state = ensure_loot_state(
        game_state,
        module.parsed_content if module else {},
    )
    return {
        "session_id": session.id,
        "save_name": session.save_name,
        "module_id": session.module_id,
        "module_name": module.name if module else None,
        "current_scene": session.current_scene,
        "combat_active": session.combat_active,
        "game_state": game_state,
        "player": char_brief(controlled_player) if controlled_player else None,
        "companions": companions,
        "logs": [serialize_log(log) for log in logs if can_user_see_log(log, user_id)],
        "campaign_state": session.campaign_state or {},
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """删除游戏存档及关联数据"""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "存档不存在")
    if session.is_multiplayer:
        raise HTTPException(400, "Use the room leave endpoint for multiplayer sessions")
    if session.user_id and session.user_id != user_id:
        raise HTTPException(403, "无权删除他人的存档")

    from sqlalchemy import delete as sql_delete
    from sqlalchemy import update as sql_update

    await db.execute(sql_update(Character).where(Character.session_id == session_id).values(session_id=None))
    await db.execute(sql_delete(CombatState).where(CombatState.session_id == session_id))
    await db.execute(sql_delete(GameLog).where(GameLog.session_id == session_id))

    roster = CharacterRoster(db, session)
    await roster.delete_ai_companions()
    await db.delete(session)
    await db.commit()
    return {"ok": True}


async def _generate_opening_with_legacy_patch(parsed: dict, raw_scene: str, dm_style: str | None = None) -> str:
    """Honor historical tests/tools that monkeypatch api.game._generate_opening."""
    try:
        import api.game as game_module
        patched = getattr(game_module, "_generate_opening", None)
        if patched and patched is not generate_opening:
            try:
                return await patched(parsed, raw_scene, dm_style)
            except TypeError:
                return await patched(parsed, raw_scene)
    except Exception:
        pass
    return await generate_opening(parsed, raw_scene, dm_style)


async def _assert_session_roster_access(
    db: AsyncSession,
    req: CreateSessionRequest,
    user_id: str,
) -> None:
    player = await db.get(Character, req.player_character_id)
    if not player:
        raise HTTPException(404, "Player character not found")
    await assert_character_access(player, user_id, db, allow_room_ai=False)

    for companion_id in req.companion_ids or []:
        companion = await db.get(Character, companion_id)
        if not companion:
            raise HTTPException(404, "Companion character not found")
        if companion.user_id and companion.user_id != user_id:
            raise HTTPException(403, "Cannot bind another user's character")
        if companion.is_player and companion.user_id != user_id:
            raise HTTPException(403, "Cannot bind player character as companion")
        if companion.session_id:
            owner_session = await get_session_or_404(companion.session_id, db)
            await assert_session_access(owner_session, user_id, db)
