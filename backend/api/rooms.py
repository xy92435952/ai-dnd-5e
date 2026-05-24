"""多人联机房间路由 — /game/rooms/*

依赖：services/room_service.py 提供业务逻辑。
权限：所有端点需要 JWT 鉴权（Depends(get_user_id)）。
广播：状态变更后通过 ws_manager 推送给房间所有人（A3 阶段引入）。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from api.deps import get_user_id
from models import Session
from services import room_service
from services import room_rest_vote_service
from services.session_action_lock import session_action_lock
from services.ws_manager import ws_manager
from schemas.room_schemas import (
    CreateRoomRequest, JoinRoomRequest, ClaimCharacterRequest,
    KickMemberRequest, TransferHostRequest,
    SetGroupRequest, SubmitGroupActionRequest, ClearGroupActionsRequest,
    FocusGroupRequest, SetGroupReadinessRequest,
    CreateRestVoteRequest, CastRestVoteRequest,
    CreateRoomResponse, JoinRoomResponse, RoomInfo, MemberInfo,
)
from schemas.ws_events import (
    MemberJoined, MemberLeft, RoomDissolved, GameStarted,
    AiCompanionsFilled, MemberKicked, HostTransferred, CharacterClaimed,
    RoomStateUpdated,
)


router = APIRouter(prefix="/game/rooms", tags=["rooms"])


async def _find_room_session_id(db: AsyncSession, room_code: str) -> str | None:
    result = await db.execute(select(Session.id).where(Session.room_code == room_code))
    return result.scalar_one_or_none()


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
    session_id = await _find_room_session_id(db, req.room_code)
    if session_id:
        async with session_action_lock(session_id):
            session, member = await room_service.join_room(
                db, user_id=user_id, room_code=req.room_code,
            )
            members = await room_service.list_members(db, session.id)
            # 广播：新成员加入
            await ws_manager.broadcast(session.id, MemberJoined(
                user_id=user_id, members=members,
            ))
            return JoinRoomResponse(
                session_id=session.id,
                room_code=session.room_code,
                your_member_id=member.id,
                members=[MemberInfo(**m) for m in members],
            )

    session, member = await room_service.join_room(
        db, user_id=user_id, room_code=req.room_code,
    )
    members = await room_service.list_members(db, session.id)
    await ws_manager.broadcast(session.id, MemberJoined(
        user_id=user_id, members=members,
    ))
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
    async with session_action_lock(session_id):
        result = await room_service.leave_room(db, user_id=user_id, session_id=session_id)
        members = await room_service.list_members(db, session_id)
        # 广播：成员离开 / 房主转移 / 房间解散
        if result["room_dissolved"]:
            await ws_manager.broadcast(session_id, RoomDissolved(by_user_id=user_id))
        else:
            await ws_manager.broadcast(session_id, MemberLeft(
                user_id=user_id,
                host_transferred_to=result["host_transferred_to"],
                members=members,
            ))
        return result


# ── 房主操作 ─────────────────────────────────────────

@router.post("/{session_id}/start")
async def start_game(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    async with session_action_lock(session_id):
        session = await room_service.start_game(db, actor_user_id=user_id, session_id=session_id)
        await ws_manager.broadcast(session_id, GameStarted(
            current_speaker_user_id=session.game_state.get("multiplayer", {}).get("current_speaker_user_id"),
        ))
        return {"started": True, "session_id": session.id}


@router.post("/{session_id}/fill-ai")
async def fill_ai_companions(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """房主补满 AI 队友：按 max_players - 真人玩家数 - 已有 AI 数 生成缺口。"""
    async with session_action_lock(session_id):
        result = await room_service.fill_with_ai_companions(
            db, actor_user_id=user_id, session_id=session_id,
        )
        # 广播：AI 队友已生成（客户端刷新房间信息）
        await ws_manager.broadcast(session_id, AiCompanionsFilled(
            generated=result["generated"],
            ai_companions=result["companions"],
        ))
        return result


@router.post("/{session_id}/kick")
async def kick_member(
    session_id: str,
    req: KickMemberRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    async with session_action_lock(session_id):
        result = await room_service.kick_member(
            db, actor_user_id=user_id,
            session_id=session_id, target_user_id=req.user_id,
        )
        members = await room_service.list_members(db, session_id)
        await ws_manager.broadcast(session_id, MemberKicked(
            user_id=req.user_id,
            by_user_id=user_id,
            members=members,
        ))
        return result


@router.post("/{session_id}/transfer")
async def transfer_host(
    session_id: str,
    req: TransferHostRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    async with session_action_lock(session_id):
        result = await room_service.transfer_host(
            db, actor_user_id=user_id,
            session_id=session_id, new_host_user_id=req.new_host_user_id,
        )
        await ws_manager.broadcast(session_id, HostTransferred(
            new_host_user_id=req.new_host_user_id,
        ))
        return result


# ── 角色认领 ─────────────────────────────────────────

@router.post("/{session_id}/claim-character")
async def claim_character(
    session_id: str,
    req: ClaimCharacterRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    async with session_action_lock(session_id):
        member = await room_service.claim_character(
            db, user_id=user_id,
            session_id=session_id, character_id=req.character_id,
        )
        members = await room_service.list_members(db, session_id)
        await ws_manager.broadcast(session_id, CharacterClaimed(
            user_id=user_id,
            character_id=req.character_id,
            members=members,
        ))
        return {"claimed": True, "member_id": member.id, "character_id": req.character_id}


# ── 探索分队 / 行动队列 ─────────────────────────────────

@router.post("/{session_id}/groups/join", response_model=RoomInfo)
async def join_group(
    session_id: str,
    req: SetGroupRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    async with session_action_lock(session_id):
        room = await room_service.set_member_group(
            db,
            session_id=session_id,
            user_id=user_id,
            group_id=req.group_id,
            group_name=req.group_name,
            location=req.location,
        )
        await ws_manager.broadcast(session_id, RoomStateUpdated(room=room))
        return RoomInfo(**room)


@router.post("/{session_id}/groups/actions", response_model=RoomInfo)
async def submit_group_action(
    session_id: str,
    req: SubmitGroupActionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    async with session_action_lock(session_id):
        room = await room_service.submit_group_action(
            db,
            session_id=session_id,
            user_id=user_id,
            group_id=req.group_id,
            action_text=req.action_text,
        )
        await ws_manager.broadcast(session_id, RoomStateUpdated(room=room))
        return RoomInfo(**room)


@router.post("/{session_id}/groups/actions/clear", response_model=RoomInfo)
async def clear_group_actions(
    session_id: str,
    req: ClearGroupActionsRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    async with session_action_lock(session_id):
        room = await room_service.clear_group_actions(
            db,
            session_id=session_id,
            group_id=req.group_id,
            actor_user_id=user_id,
        )
        await ws_manager.broadcast(session_id, RoomStateUpdated(room=room))
        return RoomInfo(**room)


@router.post("/{session_id}/groups/readiness", response_model=RoomInfo)
async def set_group_readiness(
    session_id: str,
    req: SetGroupReadinessRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    async with session_action_lock(session_id):
        room = await room_service.set_group_readiness(
            db,
            session_id=session_id,
            user_id=user_id,
            group_id=req.group_id,
            status=req.status,
        )
        await ws_manager.broadcast(session_id, RoomStateUpdated(room=room))
        return RoomInfo(**room)


@router.post("/{session_id}/groups/focus", response_model=RoomInfo)
async def focus_group(
    session_id: str,
    req: FocusGroupRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    async with session_action_lock(session_id):
        room = await room_service.set_active_group(
            db,
            session_id=session_id,
            group_id=req.group_id,
            actor_user_id=user_id,
        )
        await ws_manager.broadcast(session_id, RoomStateUpdated(room=room))
        return RoomInfo(**room)


# 鈹€鈹€ 浼戞伅鎶曠エ 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

@router.post("/{session_id}/rest-vote", response_model=RoomInfo)
async def create_rest_vote(
    session_id: str,
    req: CreateRestVoteRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    async with session_action_lock(session_id):
        room = await room_rest_vote_service.create_rest_vote(
            db,
            session_id=session_id,
            user_id=user_id,
            rest_type=req.rest_type,
        )
        await ws_manager.broadcast(session_id, RoomStateUpdated(room=room))
        return RoomInfo(**room)


@router.post("/{session_id}/rest-vote/vote")
async def cast_rest_vote(
    session_id: str,
    req: CastRestVoteRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    async with session_action_lock(session_id):
        room, rest_result = await room_rest_vote_service.cast_rest_vote(
            db,
            session_id=session_id,
            user_id=user_id,
            vote_value=req.vote,
        )
        await ws_manager.broadcast(session_id, RoomStateUpdated(room=room))
        if rest_result:
            await ws_manager.broadcast(session_id, {
                "type": "rest_vote_resolved",
                "rest_type": rest_result.get("rest_type"),
                "rest_result": rest_result,
            })
        return {"room": room, "rest_result": rest_result}


@router.post("/{session_id}/rest-vote/cancel", response_model=RoomInfo)
async def cancel_rest_vote(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    async with session_action_lock(session_id):
        room = await room_rest_vote_service.cancel_rest_vote(
            db,
            session_id=session_id,
            user_id=user_id,
        )
        await ws_manager.broadcast(session_id, RoomStateUpdated(room=room))
        return RoomInfo(**room)


# ── 查询 ─────────────────────────────────────────────

@router.get("/{session_id}", response_model=RoomInfo)
async def get_room(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    async with session_action_lock(session_id):
        await room_service.require_room_member(db, session_id, user_id)
        info = await room_service.get_room_info(db, session_id)
        return RoomInfo(**info)


@router.get("/{session_id}/members", response_model=list[MemberInfo])
async def list_members(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    await room_service.require_room_member(db, session_id, user_id)
    members = await room_service.list_members(db, session_id)
    return [MemberInfo(**m) for m in members]
