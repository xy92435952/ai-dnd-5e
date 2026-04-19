"""多人联机房间路由 — /game/rooms/*

依赖：services/room_service.py 提供业务逻辑。
权限：所有端点需要 JWT 鉴权（Depends(get_user_id)）。
广播：状态变更后通过 ws_manager 推送给房间所有人（A3 阶段引入）。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from api.deps import get_user_id
from services import room_service
from services.ws_manager import ws_manager
from schemas.room_schemas import (
    CreateRoomRequest, JoinRoomRequest, ClaimCharacterRequest,
    KickMemberRequest, TransferHostRequest,
    CreateRoomResponse, JoinRoomResponse, RoomInfo, MemberInfo,
)


router = APIRouter(prefix="/game/rooms", tags=["rooms"])


# ── 创建/加入/离开 ───────────────────────────────────

@router.post("/create", response_model=CreateRoomResponse)
async def create_room(
    req: CreateRoomRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    session = await room_service.create_room(
        db, user_id=user_id,
        module_id=req.module_id,
        save_name=req.save_name,
        max_players=req.max_players,
    )
    return CreateRoomResponse(
        session_id=session.id,
        room_code=session.room_code,
        host_user_id=session.host_user_id,
    )


@router.post("/join", response_model=JoinRoomResponse)
async def join_room(
    req: JoinRoomRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    session, member = await room_service.join_room(
        db, user_id=user_id, room_code=req.room_code,
    )
    members = await room_service.list_members(db, session.id)
    # 广播：新成员加入
    await ws_manager.broadcast(session.id, {
        "type": "member_joined",
        "user_id": user_id,
        "members": members,
    })
    return JoinRoomResponse(
        session_id=session.id,
        room_code=session.room_code,
        your_member_id=member.id,
        members=[MemberInfo(**m) for m in members],
    )


@router.post("/{session_id}/leave")
async def leave_room(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    result = await room_service.leave_room(db, user_id=user_id, session_id=session_id)
    members = await room_service.list_members(db, session_id)
    # 广播：成员离开 / 房主转移 / 房间解散
    if result["room_dissolved"]:
        await ws_manager.broadcast(session_id, {
            "type": "room_dissolved", "by_user_id": user_id,
        })
    else:
        await ws_manager.broadcast(session_id, {
            "type": "member_left",
            "user_id": user_id,
            "host_transferred_to": result["host_transferred_to"],
            "members": members,
        })
    return result


# ── 房主操作 ─────────────────────────────────────────

@router.post("/{session_id}/start")
async def start_game(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    session = await room_service.start_game(db, actor_user_id=user_id, session_id=session_id)
    await ws_manager.broadcast(session_id, {
        "type": "game_started",
        "current_speaker_user_id": session.game_state.get("multiplayer", {}).get("current_speaker_user_id"),
    })
    return {"started": True, "session_id": session.id}


@router.post("/{session_id}/fill-ai")
async def fill_ai_companions(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """房主补满 AI 队友：按 max_players - 真人玩家数 - 已有 AI 数 生成缺口。"""
    result = await room_service.fill_with_ai_companions(
        db, actor_user_id=user_id, session_id=session_id,
    )
    # 广播：AI 队友已生成（客户端刷新房间信息）
    await ws_manager.broadcast(session_id, {
        "type": "ai_companions_filled",
        "generated": result["generated"],
        "ai_companions": result["companions"],
    })
    return result


@router.post("/{session_id}/kick")
async def kick_member(
    session_id: str,
    req: KickMemberRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    result = await room_service.kick_member(
        db, actor_user_id=user_id,
        session_id=session_id, target_user_id=req.user_id,
    )
    members = await room_service.list_members(db, session_id)
    await ws_manager.broadcast(session_id, {
        "type": "member_kicked",
        "user_id": req.user_id,
        "by_user_id": user_id,
        "members": members,
    })
    return result


@router.post("/{session_id}/transfer")
async def transfer_host(
    session_id: str,
    req: TransferHostRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    result = await room_service.transfer_host(
        db, actor_user_id=user_id,
        session_id=session_id, new_host_user_id=req.new_host_user_id,
    )
    await ws_manager.broadcast(session_id, {
        "type": "host_transferred",
        "new_host_user_id": req.new_host_user_id,
    })
    return result


# ── 角色认领 ─────────────────────────────────────────

@router.post("/{session_id}/claim-character")
async def claim_character(
    session_id: str,
    req: ClaimCharacterRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    member = await room_service.claim_character(
        db, user_id=user_id,
        session_id=session_id, character_id=req.character_id,
    )
    members = await room_service.list_members(db, session_id)
    await ws_manager.broadcast(session_id, {
        "type": "character_claimed",
        "user_id": user_id,
        "character_id": req.character_id,
        "members": members,
    })
    return {"claimed": True, "member_id": member.id, "character_id": req.character_id}


# ── 查询 ─────────────────────────────────────────────

@router.get("/{session_id}", response_model=RoomInfo)
async def get_room(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    info = await room_service.get_room_info(db, session_id)
    return RoomInfo(**info)


@router.get("/{session_id}/members", response_model=list[MemberInfo])
async def list_members(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    members = await room_service.list_members(db, session_id)
    return [MemberInfo(**m) for m in members]
