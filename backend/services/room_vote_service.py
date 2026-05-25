"""Room governance votes stored in the multiplayer session state."""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from models import Session
from services.room_member_service import list_members_raw


VOTE_TYPES = {"kick"}


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _clean_room_votes(raw_votes, member_ids: set[str]) -> list[dict]:
    cleaned: list[dict] = []
    for raw in raw_votes or []:
        if not isinstance(raw, dict):
            continue
        vote_type = raw.get("type")
        target_user_id = raw.get("target_user_id")
        created_by_user_id = raw.get("created_by_user_id")
        if vote_type not in VOTE_TYPES:
            continue
        if target_user_id not in member_ids or created_by_user_id not in member_ids:
            continue

        eligible_voters = [
            user_id
            for user_id in (raw.get("eligible_voter_user_ids") or [])
            if user_id in member_ids and user_id != target_user_id
        ]
        if len(eligible_voters) < 2:
            continue

        yes_votes = [
            user_id
            for user_id in (raw.get("yes_user_ids") or [])
            if user_id in eligible_voters
        ]
        unique_yes_votes = list(dict.fromkeys(yes_votes))
        threshold = max(2, (len(eligible_voters) // 2) + 1)
        proposal_id = raw.get("id") or f"{vote_type}:{target_user_id}"
        cleaned.append({
            "id": proposal_id,
            "type": vote_type,
            "target_user_id": target_user_id,
            "created_by_user_id": created_by_user_id,
            "eligible_voter_user_ids": list(dict.fromkeys(eligible_voters)),
            "yes_user_ids": unique_yes_votes,
            "threshold": threshold,
            "status": raw.get("status") if raw.get("status") in {"open", "passed"} else "open",
            "created_at": raw.get("created_at") or _now_iso(),
            "updated_at": raw.get("updated_at") or raw.get("created_at") or _now_iso(),
        })
    return cleaned


async def ensure_room_votes(db: AsyncSession, session_id: str) -> list[dict]:
    """Normalize open governance votes and return them."""
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")

    members = await list_members_raw(db, session_id)
    member_ids = {member.user_id for member in members}

    state = dict(session.game_state or {})
    mp = dict(state.get("multiplayer") or {})
    votes = _clean_room_votes(mp.get("room_votes"), member_ids)
    mp["room_votes"] = votes
    state["multiplayer"] = mp
    session.game_state = state
    flag_modified(session, "game_state")
    await db.commit()
    return votes


async def vote_to_kick_member(
    db: AsyncSession,
    actor_user_id: str,
    session_id: str,
    target_user_id: str,
) -> dict:
    """
    Record a kick vote. The caller may be any non-target room member.

    Returns a result with ``passed=True`` once a majority of eligible voters has
    approved the proposal. Two-player rooms intentionally cannot start a kick
    vote because only one non-target voter would exist. The actual removal
    remains owned by the room member service so all character demotion behavior
    stays in one place.
    """
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        raise HTTPException(404, "房间不存在")
    if target_user_id == actor_user_id:
        raise HTTPException(400, "不能投票踢出自己，请使用离开房间")

    members = await list_members_raw(db, session_id)
    member_ids = {member.user_id for member in members}
    if actor_user_id not in member_ids:
        raise HTTPException(403, "你不在该房间中")
    if target_user_id not in member_ids:
        raise HTTPException(404, "目标成员不在房间中")

    eligible_voters = [member.user_id for member in members if member.user_id != target_user_id]
    if len(eligible_voters) < 2:
        raise HTTPException(409, "至少需要 3 名成员才可发起移出投票")
    threshold = max(2, (len(eligible_voters) // 2) + 1)

    await ensure_room_votes(db, session_id)
    session = await db.get(Session, session_id)
    state = dict(session.game_state or {})
    mp = dict(state.get("multiplayer") or {})
    votes = list(mp.get("room_votes") or [])

    proposal_id = f"kick:{target_user_id}"
    vote = next(
        (
            item for item in votes
            if item.get("id") == proposal_id and item.get("status") == "open"
        ),
        None,
    )
    if vote is None:
        now = _now_iso()
        vote = {
            "id": proposal_id,
            "type": "kick",
            "target_user_id": target_user_id,
            "created_by_user_id": actor_user_id,
            "eligible_voter_user_ids": eligible_voters,
            "yes_user_ids": [],
            "threshold": threshold,
            "status": "open",
            "created_at": now,
            "updated_at": now,
        }
        votes.append(vote)

    vote["eligible_voter_user_ids"] = eligible_voters
    vote["threshold"] = threshold
    yes_votes = list(dict.fromkeys([
        user_id
        for user_id in vote.get("yes_user_ids", [])
        if user_id in eligible_voters
    ]))
    if actor_user_id not in yes_votes:
        yes_votes.append(actor_user_id)
    vote["yes_user_ids"] = yes_votes
    vote["updated_at"] = _now_iso()

    passed = len(yes_votes) >= threshold
    if passed:
        vote["status"] = "passed"
        votes = [item for item in votes if item.get("id") != proposal_id]

    mp["room_votes"] = votes
    state["multiplayer"] = mp
    session.game_state = state
    flag_modified(session, "game_state")
    await db.commit()

    return {
        "passed": passed,
        "vote": vote,
        "votes": votes,
        "yes_count": len(yes_votes),
        "threshold": threshold,
    }


async def clear_votes_for_user(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> None:
    """Remove stale governance votes that involve a user who just left."""
    session = await db.get(Session, session_id)
    if not session or not session.is_multiplayer:
        return

    state = dict(session.game_state or {})
    mp = dict(state.get("multiplayer") or {})
    votes = [
        vote for vote in (mp.get("room_votes") or [])
        if vote.get("target_user_id") != user_id
        and vote.get("created_by_user_id") != user_id
        and user_id not in (vote.get("eligible_voter_user_ids") or [])
    ]
    mp["room_votes"] = votes
    state["multiplayer"] = mp
    session.game_state = state
    flag_modified(session, "game_state")
    await db.commit()
