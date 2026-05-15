"""多人联机房间业务逻辑兼容门面。

真实实现已按职责拆分到：
- room_lifecycle_service: 房间码、创建、加入、离开、开始状态判断
- room_member_service: 成员、角色认领、房主转让、心跳
- room_ai_companion_service: AI 队友查询与补位
- room_start_service: 开始游戏流程
- room_info_service: 房间信息聚合
- room_group_service: 探索分队与行动队列

这里继续保留旧导入路径，避免 API 层、测试和外部脚本感知拆分。
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from services import (
    room_ai_companion_service,
    room_group_service,
    room_info_service,
    room_lifecycle_service,
    room_member_service,
    room_start_service,
)


ROOM_CODE_CHARS = room_lifecycle_service.ROOM_CODE_CHARS
ROOM_CODE_LENGTH = room_lifecycle_service.ROOM_CODE_LENGTH
OFFLINE_THRESHOLD_SECONDS = room_member_service.OFFLINE_THRESHOLD_SECONDS
MAX_CODE_GEN_ATTEMPTS = room_lifecycle_service.MAX_CODE_GEN_ATTEMPTS
DEFAULT_GROUP_ID = room_group_service.DEFAULT_GROUP_ID
DEFAULT_GROUP_NAME = room_group_service.DEFAULT_GROUP_NAME
DEFAULT_GROUP_LOCATION = room_group_service.DEFAULT_GROUP_LOCATION
READINESS_STATUSES = room_group_service.READINESS_STATUSES


generate_unique_room_code = room_lifecycle_service.generate_unique_room_code
create_room = room_lifecycle_service.create_room
join_room = room_lifecycle_service.join_room
leave_room = room_lifecycle_service.leave_room

claim_character = room_member_service.claim_character
kick_member = room_member_service.kick_member
transfer_host = room_member_service.transfer_host
list_members = room_member_service.list_members
update_heartbeat = room_member_service.update_heartbeat
mark_offline = room_member_service.mark_offline

start_game = room_start_service.start_game
list_ai_companions = room_ai_companion_service.list_ai_companions
fill_with_ai_companions = room_ai_companion_service.fill_with_ai_companions
get_room_info = room_info_service.get_room_info


async def ensure_multiplayer_state(
    db: AsyncSession,
    session_id: str,
) -> dict:
    """归一化多人探索状态，并返回 multiplayer 子状态。"""
    return await room_group_service.ensure_multiplayer_state(db, session_id)


async def set_member_group(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    group_id: str,
    group_name: Optional[str] = None,
    location: Optional[str] = None,
) -> dict:
    """把当前用户移动到指定探索分队；分队不存在时创建。"""
    await room_group_service.set_member_group(
        db,
        session_id=session_id,
        user_id=user_id,
        group_id=group_id,
        group_name=group_name,
        location=location,
    )
    return await get_room_info(db, session_id)


async def submit_group_action(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    group_id: str,
    action_text: str,
) -> dict:
    """提交一条当前分队内的待处理探索行动意图。"""
    await room_group_service.submit_group_action(
        db,
        session_id=session_id,
        user_id=user_id,
        group_id=group_id,
        action_text=action_text,
    )
    return await get_room_info(db, session_id)


async def set_group_readiness(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    group_id: str,
    status: str,
) -> dict:
    """标记当前用户在分队内的桌面准备状态。"""
    await room_group_service.set_group_readiness(
        db,
        session_id=session_id,
        user_id=user_id,
        group_id=group_id,
        status=status,
    )
    return await get_room_info(db, session_id)


async def set_active_group(
    db: AsyncSession,
    session_id: str,
    group_id: str,
    actor_user_id: Optional[str] = None,
) -> dict:
    """切换当前探索焦点分队，不移动任何成员。"""
    await room_group_service.set_active_group(
        db,
        session_id=session_id,
        group_id=group_id,
        actor_user_id=actor_user_id,
    )
    return await get_room_info(db, session_id)


async def clear_group_actions(
    db: AsyncSession,
    session_id: str,
    group_id: str,
    actor_user_id: Optional[str] = None,
) -> dict:
    """清空某个探索分队的待处理行动。"""
    await room_group_service.clear_group_actions(
        db,
        session_id=session_id,
        group_id=group_id,
        actor_user_id=actor_user_id,
    )
    return await get_room_info(db, session_id)


def _is_game_started(session) -> bool:
    return room_lifecycle_service.is_game_started(session)


async def _get_member(db: AsyncSession, session_id: str, user_id: str):
    return await room_member_service.get_member(db, session_id, user_id)


async def _list_members_raw(db: AsyncSession, session_id: str):
    return await room_member_service.list_members_raw(db, session_id)


async def _count_members(db: AsyncSession, session_id: str) -> int:
    return await room_member_service.count_members(db, session_id)


def _clean_group_id(group_id: Optional[str]) -> str:
    return room_group_service.clean_group_id_value(group_id)


def _normalize_party_groups(raw_groups, member_ids: list[str]) -> list[dict]:
    return room_group_service._normalize_party_groups(raw_groups, member_ids)


def _normalize_group_actions(raw_pending, groups: list[dict]) -> dict:
    return room_group_service._normalize_group_actions(raw_pending, groups)


def _normalize_group_readiness(raw_readiness, groups: list[dict], member_id_set: set[str]) -> dict:
    return room_group_service._normalize_group_readiness(raw_readiness, groups, member_id_set)


def _drop_empty_non_default_groups(groups: list[dict]) -> list[dict]:
    return room_group_service._drop_empty_non_default_groups(groups)


def _unique_preserve_order(values) -> list:
    return room_group_service._unique_preserve_order(values)


__all__ = [
    "ROOM_CODE_CHARS",
    "ROOM_CODE_LENGTH",
    "OFFLINE_THRESHOLD_SECONDS",
    "MAX_CODE_GEN_ATTEMPTS",
    "DEFAULT_GROUP_ID",
    "DEFAULT_GROUP_NAME",
    "DEFAULT_GROUP_LOCATION",
    "READINESS_STATUSES",
    "generate_unique_room_code",
    "create_room",
    "join_room",
    "leave_room",
    "claim_character",
    "kick_member",
    "transfer_host",
    "start_game",
    "list_ai_companions",
    "fill_with_ai_companions",
    "list_members",
    "get_room_info",
    "ensure_multiplayer_state",
    "set_member_group",
    "submit_group_action",
    "set_group_readiness",
    "set_active_group",
    "clear_group_actions",
    "update_heartbeat",
    "mark_offline",
]
