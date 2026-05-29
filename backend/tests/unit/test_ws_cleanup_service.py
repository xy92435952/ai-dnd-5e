from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from models import Character, GameLog, SessionMember, User
from services import room_service
from services.ws_cleanup_service import cleanup_abandoned_waiting_rooms
from services.ws_manager import ws_manager


@pytest.fixture(autouse=True)
def _clear_ws_manager():
    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()
    yield
    ws_manager.rooms.clear()
    ws_manager.user_ws.clear()
    ws_manager.ws_meta.clear()


class FakeWebSocket:
    def __init__(self):
        self.closed = []

    async def close(self, code=1000, reason=None):
        self.closed.append({"code": code, "reason": reason})


@pytest.mark.asyncio
async def test_cleanup_abandoned_waiting_room_dissolves_stale_empty_lobby(
    db_session,
    sample_module,
    sample_user,
):
    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="Abandoned waiting room",
        max_players=4,
    )
    guest = User(username="abandoned_guest", password_hash="x", display_name="Guest")
    db_session.add(guest)
    await db_session.flush()
    guest_member = SessionMember(session_id=session.id, user_id=guest.id, role="player")
    db_session.add(guest_member)
    await db_session.flush()

    character = Character(
        session_id=session.id,
        user_id=guest.id,
        is_player=True,
        name="Claimed Guest",
        race="Human",
        char_class="Fighter",
        level=1,
        ability_scores={"str": 14, "dex": 12, "con": 13, "int": 10, "wis": 10, "cha": 10},
        hp_current=10,
    )
    db_session.add(character)
    await db_session.flush()
    guest_member.character_id = character.id

    state = dict(session.game_state or {})
    multiplayer = dict(state.get("multiplayer") or {})
    multiplayer.update({
        "online_user_ids": [sample_user.id, guest.id],
        "start_ready_user_ids": [guest.id],
        "current_speaker_user_id": guest.id,
        "pending_actions": [{"user_id": guest.id, "text": "Wait here."}],
        "pending_actions_by_group": {
            "main": [{"user_id": guest.id, "text": "Search the lobby."}],
        },
        "group_readiness": {"main": {sample_user.id: "ready", guest.id: "waiting"}},
        "last_offline_at_by_user_id": {
            sample_user.id: (datetime.utcnow() - timedelta(seconds=300)).isoformat() + "Z",
            guest.id: (datetime.utcnow() - timedelta(seconds=300)).isoformat() + "Z",
        },
        "room_votes": [{"id": "kick:guest", "type": "kick"}],
        "dm_thinking": {"active": True, "by_user_id": guest.id},
    })
    state["multiplayer"] = multiplayer
    session.game_state = state

    stale_seen_at = datetime.utcnow() - timedelta(seconds=300)
    for member in await room_service._list_members_raw(db_session, session.id):
        member.last_seen_at = stale_seen_at
    await db_session.commit()

    dissolved = await cleanup_abandoned_waiting_rooms(
        db_session,
        abandoned_after_seconds=120,
    )

    assert dissolved == [session.id]
    await db_session.refresh(session)
    await db_session.refresh(character)
    assert session.room_code is None
    assert session.host_user_id is None
    assert character.user_id is None
    assert character.is_player is False

    members = (
        await db_session.execute(
            select(SessionMember).where(SessionMember.session_id == session.id)
        )
    ).scalars().all()
    assert members == []

    mp = (session.game_state or {})["multiplayer"]
    assert mp["online_user_ids"] == []
    assert mp["start_ready_user_ids"] == []
    assert mp["current_speaker_user_id"] is None
    assert mp["pending_actions"] == []
    assert mp["pending_actions_by_group"] == {"main": []}
    assert mp["group_readiness"] == {"main": {}}
    assert mp["party_groups"][0]["member_user_ids"] == []
    assert "last_offline_at_by_user_id" not in mp
    assert "room_votes" not in mp
    assert "dm_thinking" not in mp

    audit = (
        await db_session.execute(
            select(GameLog).where(GameLog.session_id == session.id)
        )
    ).scalars().one()
    payload = audit.table_decision["audit"]
    assert payload["event_type"] == "room_dissolved"
    assert payload["actor_user_id"] == "system"
    assert payload["details"] == {
        "reason": "abandoned_room_cleanup",
        "member_count": 2,
    }


@pytest.mark.asyncio
async def test_cleanup_abandoned_waiting_room_skips_started_campaign(
    db_session,
    sample_module,
    sample_user,
):
    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="Started room",
        max_players=4,
    )
    session.current_scene = "The adventure is already underway."
    session.game_state["multiplayer"]["last_offline_at_by_user_id"] = {
        sample_user.id: (datetime.utcnow() - timedelta(seconds=300)).isoformat() + "Z",
    }
    member = (await room_service._list_members_raw(db_session, session.id))[0]
    member.last_seen_at = datetime.utcnow() - timedelta(seconds=300)
    await db_session.commit()

    dissolved = await cleanup_abandoned_waiting_rooms(
        db_session,
        abandoned_after_seconds=120,
    )

    assert dissolved == []
    await db_session.refresh(session)
    assert session.room_code is not None
    assert session.host_user_id == sample_user.id
    assert len(await room_service._list_members_raw(db_session, session.id)) == 1


@pytest.mark.asyncio
async def test_cleanup_abandoned_waiting_room_skips_active_websocket(
    db_session,
    sample_module,
    sample_user,
):
    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="Active WS room",
        max_players=4,
    )
    session.game_state["multiplayer"]["last_offline_at_by_user_id"] = {
        sample_user.id: (datetime.utcnow() - timedelta(seconds=300)).isoformat() + "Z",
    }
    member = (await room_service._list_members_raw(db_session, session.id))[0]
    member.last_seen_at = datetime.utcnow() - timedelta(seconds=300)
    await db_session.commit()

    ws = FakeWebSocket()
    await ws_manager.connect(session.id, sample_user.id, ws)

    dissolved = await cleanup_abandoned_waiting_rooms(
        db_session,
        abandoned_after_seconds=120,
    )

    assert dissolved == []
    assert ws.closed == []
    await db_session.refresh(session)
    assert session.room_code is not None
    assert session.host_user_id == sample_user.id
    assert await ws_manager.online_users(session.id) == [sample_user.id]


@pytest.mark.asyncio
async def test_mark_offline_cooldown_prevents_immediate_waiting_room_cleanup(
    db_session,
    sample_module,
    sample_user,
):
    session = await room_service.create_room(
        db_session,
        user_id=sample_user.id,
        module_id=sample_module.id,
        save_name="Reconnect grace room",
        max_players=4,
    )

    await room_service.mark_offline(db_session, session.id, sample_user.id)

    dissolved = await cleanup_abandoned_waiting_rooms(
        db_session,
        abandoned_after_seconds=120,
    )

    assert dissolved == []
    await db_session.refresh(session)
    assert session.room_code is not None
    assert session.game_state["multiplayer"]["last_offline_at_by_user_id"][sample_user.id]

    await room_service.update_heartbeat(db_session, session.id, sample_user.id)
    await db_session.refresh(session)
    assert "last_offline_at_by_user_id" not in session.game_state["multiplayer"]
