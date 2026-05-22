from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from models import GameLog, Session
from services.rest_service import apply_party_rest
from services.room_member_service import OFFLINE_THRESHOLD_SECONDS, get_member, list_members

REST_VOTE_TIMEOUT_SECONDS = 90
REST_VOTE_STATE_KEY = "rest_vote"


async def create_rest_vote(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    rest_type: str,
) -> dict:
    """Create or replace the active multiplayer rest vote."""
    if rest_type not in ("long", "short"):
        raise HTTPException(400, "rest_type 必须为 'long' 或 'short'")
    session = await _get_multiplayer_session(db, session_id)
    member = await _require_claimed_member(db, session_id, user_id)
    await _clear_expired_vote_if_needed(session)

    vote = _build_vote(
        session_id=session_id,
        proposer_user_id=user_id,
        proposer_name=member.get("display_name") or member.get("username") or user_id,
        rest_type=rest_type,
    )
    vote["votes"][user_id] = "yes"
    _set_vote(session, vote)
    db.add(GameLog(
        session_id=session_id,
        role="system",
        content=f"{vote['proposer_name']} 发起了{'长休' if rest_type == 'long' else '短休'}投票。",
        log_type="system",
    ))
    await db.commit()
    return await _room_info(db, session_id)


async def cast_rest_vote(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    vote_value: str,
) -> tuple[dict, Optional[dict]]:
    """Cast a yes/no vote. Returns the updated room and optional applied rest result."""
    clean_vote = (vote_value or "").strip().lower()
    if clean_vote not in {"yes", "no"}:
        raise HTTPException(400, "投票只能是 yes 或 no")

    session = await _get_multiplayer_session(db, session_id)
    await _require_claimed_member(db, session_id, user_id)
    vote = await _get_active_vote(session)
    eligible = await eligible_rest_voters(db, session_id)
    eligible_ids = {member["user_id"] for member in eligible}
    if user_id not in eligible_ids:
        raise HTTPException(403, "只有在线且已认领角色的玩家可以参与休息投票")

    vote["votes"][user_id] = clean_vote
    vote["updated_at"] = datetime.utcnow().isoformat()
    snapshot = serialize_rest_vote_for_state(vote, eligible)
    result = None

    if snapshot["yes_count"] >= snapshot["required_yes"]:
        result = await apply_party_rest(db, session, vote["rest_type"])
        _set_vote(session, None)
        db.add(GameLog(
            session_id=session_id,
            role="system",
            content=f"休息投票通过，队伍完成了{'长休' if vote['rest_type'] == 'long' else '短休'}。",
            log_type="system",
        ))
    else:
        _set_vote(session, vote)

    await db.commit()
    return await _room_info(db, session_id), result


async def cancel_rest_vote(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> dict:
    """Cancel the active rest vote. Host or proposer may cancel."""
    session = await _get_multiplayer_session(db, session_id)
    vote = await _get_active_vote(session)
    if session.host_user_id != user_id and vote.get("proposer_user_id") != user_id:
        raise HTTPException(403, "只有房主或发起者可以取消休息投票")

    _set_vote(session, None)
    db.add(GameLog(
        session_id=session_id,
        role="system",
        content="休息投票已取消。",
        log_type="system",
    ))
    await db.commit()
    return await _room_info(db, session_id)


async def get_rest_vote_snapshot(
    db: AsyncSession,
    session_id: str,
    _visited: set[str] | None = None,
) -> Optional[dict]:
    """Return the active rest vote with live eligibility counts, or None."""
    _visited = _visited or set()
    if session_id in _visited:
        session = await _get_multiplayer_session(db, session_id)
        vote = await _get_active_vote_or_none(session)
        if not vote:
            return None
        members = await list_members(db, session_id)
        eligible = [
            member for member in members
            if member.get("is_online") and member.get("character_id")
        ]
        return serialize_rest_vote_for_state(vote, eligible)

    session = await _get_multiplayer_session(db, session_id)
    vote = await _get_active_vote_or_none(session)
    if not vote:
        return None
    eligible = await eligible_rest_voters(db, session_id, _visited={* _visited, session_id})
    snapshot = serialize_rest_vote_for_state(vote, eligible)
    if snapshot["eligible_count"] <= 0:
        _set_vote(session, None)
        await db.commit()
        return None
    return snapshot


async def eligible_rest_voters(
    db: AsyncSession,
    session_id: str,
    _visited: set[str] | None = None,
) -> list[dict]:
    """Online room members with claimed characters are eligible to vote."""
    members = await list_members(db, session_id)
    return [
        member for member in members
        if member.get("is_online") and member.get("character_id")
    ]


async def _get_multiplayer_session(db: AsyncSession, session_id: str) -> Session:
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")
    return session


async def _require_claimed_member(db: AsyncSession, session_id: str, user_id: str) -> dict:
    member = await get_member(db, session_id, user_id)
    if not member:
        raise HTTPException(403, "你不在该房间中")
    if not member.character_id:
        raise HTTPException(403, "认领角色后才能发起或参与休息投票")
    members = await list_members(db, session_id)
    for item in members:
        if item["user_id"] == user_id:
            return item
    raise HTTPException(403, "你不在该房间中")


def _build_vote(
    *,
    session_id: str,
    proposer_user_id: str,
    proposer_name: str,
    rest_type: str,
) -> dict:
    now = datetime.utcnow()
    expires_at = now + timedelta(seconds=REST_VOTE_TIMEOUT_SECONDS)
    return {
        "id": f"{session_id}:{int(now.timestamp())}",
        "kind": "rest",
        "rest_type": rest_type,
        "proposer_user_id": proposer_user_id,
        "proposer_name": proposer_name,
        "votes": {},
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "timeout_seconds": REST_VOTE_TIMEOUT_SECONDS,
    }


async def _clear_expired_vote_if_needed(session: Session) -> bool:
    vote = _raw_vote(session)
    if not vote:
        return False
    if not _is_expired(vote):
        return False
    _set_vote(session, None)
    return True


async def _get_active_vote(session: Session) -> dict:
    vote = await _get_active_vote_or_none(session)
    if not vote:
        raise HTTPException(404, "当前没有进行中的休息投票")
    return vote


async def _get_active_vote_or_none(session: Session) -> Optional[dict]:
    vote = _raw_vote(session)
    if not vote:
        return None
    if _is_expired(vote):
        _set_vote(session, None)
        return None
    return dict(vote)


def _raw_vote(session: Session) -> Optional[dict]:
    mp = (session.game_state or {}).get("multiplayer") or {}
    vote = mp.get(REST_VOTE_STATE_KEY)
    return dict(vote) if isinstance(vote, dict) else None


def _set_vote(session: Session, vote: Optional[dict]) -> None:
    state = dict(session.game_state or {})
    mp = dict(state.get("multiplayer") or {})
    if vote:
        mp[REST_VOTE_STATE_KEY] = vote
    else:
        mp.pop(REST_VOTE_STATE_KEY, None)
    state["multiplayer"] = mp
    session.game_state = state
    flag_modified(session, "game_state")


def _is_expired(vote: dict) -> bool:
    expires_at = vote.get("expires_at")
    if not expires_at:
        return False
    try:
        return datetime.utcnow() >= datetime.fromisoformat(expires_at)
    except ValueError:
        return False


def _rest_vote_snapshot(vote: dict, eligible: list[dict]) -> dict:
    eligible_ids = [member["user_id"] for member in eligible]
    eligible_set = set(eligible_ids)
    votes = {
        user_id: value
        for user_id, value in dict(vote.get("votes") or {}).items()
        if user_id in eligible_set and value in {"yes", "no"}
    }
    eligible_count = len(eligible_ids)
    required_yes = eligible_count // 2 + 1 if eligible_count else 1
    yes_count = sum(1 for value in votes.values() if value == "yes")
    no_count = sum(1 for value in votes.values() if value == "no")
    return {
        **vote,
        "votes": votes,
        "eligible_user_ids": eligible_ids,
        "eligible_count": eligible_count,
        "required_yes": required_yes,
        "yes_count": yes_count,
        "no_count": no_count,
        "remaining_seconds": _remaining_seconds(vote),
    }


def serialize_rest_vote_for_state(vote: Optional[dict], eligible: list[dict]) -> Optional[dict]:
    if not vote:
        return None
    return _rest_vote_snapshot(dict(vote), eligible)


def _remaining_seconds(vote: dict) -> int:
    expires_at = vote.get("expires_at")
    if not expires_at:
        return REST_VOTE_TIMEOUT_SECONDS
    try:
        delta = datetime.fromisoformat(expires_at) - datetime.utcnow()
    except ValueError:
        return REST_VOTE_TIMEOUT_SECONDS
    return max(0, int(delta.total_seconds()))


async def _room_info(db: AsyncSession, session_id: str) -> dict:
    from services.room_info_service import get_room_info

    return await get_room_info(db, session_id)
