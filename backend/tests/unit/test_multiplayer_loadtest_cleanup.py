import json
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.multiplayer_ws_loadtest import (
    LoadTestError,
    RoomRecord,
    UserRecord,
    build_hold_observer,
    cleanup_rooms,
    verify_cleanup_effects,
    verify_room_access_isolation,
    verify_session_snapshots,
)


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload) if payload is not None else ""

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.posts = []

    async def post(self, url, headers):
        self.posts.append({"url": url, "headers": headers})
        if not self.responses:
            raise AssertionError("Unexpected extra POST")
        return self.responses.pop(0)


class FakeAccessClient:
    def __init__(self, rooms, outsider, allow_outsider=False, module_id="module-1"):
        self.rooms = {room.session_id: room for room in rooms}
        self.users_by_token = {
            user.token: user
            for room in rooms
            for user in room.users
        }
        self.users_by_token[outsider.token] = outsider
        self.allow_outsider = allow_outsider
        self.module_id = module_id
        self.requests = []

    async def request(self, method, url, **kwargs):
        self.requests.append({
            "method": method,
            "url": url,
            "headers": kwargs.get("headers"),
        })
        token = (
            (kwargs.get("headers") or {})
            .get("Authorization", "")
            .removeprefix("Bearer ")
        )
        user = self.users_by_token.get(token)
        session_id = self._session_id_from_url(url)
        room = self.rooms[session_id]
        member_ids = {member.user_id for member in room.users}
        is_member = user is not None and user.user_id in member_ids
        if not is_member and not self.allow_outsider:
            return FakeResponse(403, {"detail": "not a room member"})

        members = [
            {
                "user_id": member.user_id,
                "username": member.username,
                "display_name": member.username,
                "role": "host" if member.user_id == room.host.user_id else "player",
            }
            for member in room.users
        ]
        if url.endswith("/members"):
            return FakeResponse(200, members)
        if "/game/sessions/" in url:
            return FakeResponse(200, {
                "session_id": room.session_id,
                "module_id": self.module_id,
                "game_state": {
                    "dm_style": room.dm_style,
                    "multiplayer": {
                        "party_groups": [{
                            "id": "main",
                            "member_user_ids": [member.user_id for member in room.users],
                        }],
                    },
                },
            })
        return FakeResponse(200, {"session_id": room.session_id, "members": members})

    def _session_id_from_url(self, url):
        if "/game/rooms/" in url:
            return url.split("/game/rooms/", 1)[1].split("/", 1)[0]
        return url.split("/game/sessions/", 1)[1].split("/", 1)[0]


class FakeCleanupClient:
    def __init__(self, *, join_status=404):
        self.join_status = join_status
        self.requests = []

    async def request(self, method, url, **kwargs):
        self.requests.append({
            "method": method,
            "url": url,
            "headers": kwargs.get("headers"),
            "json": kwargs.get("json"),
        })
        if method == "POST" and url.endswith("/game/rooms/join"):
            return FakeResponse(self.join_status, {"detail": "join result"})
        return FakeResponse(403, {"detail": "not a room member"})


def _user(name):
    return UserRecord(username=name, token=f"{name}-token", user_id=f"{name}-id")


def test_build_hold_observer_exposes_browser_login_context():
    host = _user("host")
    room = RoomRecord(
        session_id="session-1",
        room_code="ABCD12",
        host=host,
        users=[host],
        dm_style="classic",
    )

    observer = build_hold_observer("http://127.0.0.1:8002", room)

    assert observer == {
        "base_url": "http://127.0.0.1:8002",
        "frontend_url": "http://127.0.0.1:3000",
        "session_id": "session-1",
        "room_code": "ABCD12",
        "username": "host",
        "password": "password",
    }


@pytest.mark.asyncio
async def test_cleanup_rooms_leaves_all_members_and_dissolves_with_host_last():
    host = _user("host")
    player_two = _user("p2")
    player_three = _user("p3")
    room = RoomRecord(
        session_id="session-1",
        room_code="ABCD12",
        host=host,
        users=[host, player_two, player_three],
        dm_style="classic",
    )
    client = FakeClient([
        FakeResponse(200, {"room_dissolved": False}),
        FakeResponse(200, {"room_dissolved": False}),
        FakeResponse(200, {"room_dissolved": True}),
    ])

    results = await cleanup_rooms(client, "http://testserver", [room])

    assert results == [{
        "session_id": "session-1",
        "room_code": "ABCD12",
        "ok": True,
        "room_dissolved": True,
        "leaves": [
            {
                "user_id": "p2-id",
                "username": "p2",
                "status_code": 200,
                "ok": True,
                "room_dissolved": False,
            },
            {
                "user_id": "p3-id",
                "username": "p3",
                "status_code": 200,
                "ok": True,
                "room_dissolved": False,
            },
            {
                "user_id": "host-id",
                "username": "host",
                "status_code": 200,
                "ok": True,
                "room_dissolved": True,
            },
        ],
    }]
    assert [post["url"] for post in client.posts] == [
        "http://testserver/game/rooms/session-1/leave",
        "http://testserver/game/rooms/session-1/leave",
        "http://testserver/game/rooms/session-1/leave",
    ]
    assert [post["headers"]["Authorization"] for post in client.posts] == [
        "Bearer p2-token",
        "Bearer p3-token",
        "Bearer host-token",
    ]


@pytest.mark.asyncio
async def test_cleanup_rooms_fails_when_final_leave_does_not_dissolve_room():
    host = _user("host")
    room = RoomRecord(
        session_id="session-1",
        room_code="ABCD12",
        host=host,
        users=[host],
        dm_style="classic",
    )
    client = FakeClient([FakeResponse(200, {"room_dissolved": False})])

    results = await cleanup_rooms(client, "http://testserver", [room])

    assert results[0]["ok"] is False
    assert results[0]["room_dissolved"] is False


@pytest.mark.asyncio
async def test_verify_cleanup_effects_blocks_former_members_and_old_room_code():
    host = _user("host")
    room = RoomRecord(
        session_id="session-1",
        room_code="ABCD12",
        host=host,
        users=[host],
        dm_style="classic",
    )
    client = FakeCleanupClient()
    timings = {}

    results = await verify_cleanup_effects(client, "http://testserver", [room], timings)

    assert results == [{
        "session_id": "session-1",
        "room_code": "ABCD12",
        "ok": True,
        "checks": [
            {"name": "former_get_room_forbidden", "status_code": 403, "ok": True},
            {"name": "former_list_members_forbidden", "status_code": 403, "ok": True},
            {"name": "former_get_session_forbidden", "status_code": 403, "ok": True},
            {"name": "old_room_code_rejected", "status_code": 404, "ok": True},
        ],
    }]
    assert [request["method"] for request in client.requests] == ["GET", "GET", "GET", "POST"]
    assert [request["url"] for request in client.requests] == [
        "http://testserver/game/rooms/session-1",
        "http://testserver/game/rooms/session-1/members",
        "http://testserver/game/sessions/session-1",
        "http://testserver/game/rooms/join",
    ]
    assert client.requests[-1]["json"] == {"room_code": "ABCD12"}
    assert {request["headers"]["Authorization"] for request in client.requests} == {
        "Bearer host-token",
    }
    assert timings["cleanup_former_get_room_forbidden_ms"]
    assert timings["cleanup_former_list_members_forbidden_ms"]
    assert timings["cleanup_former_get_session_forbidden_ms"]
    assert timings["cleanup_old_room_code_join_rejected_ms"]


@pytest.mark.asyncio
async def test_verify_cleanup_effects_fails_when_old_room_code_can_still_join():
    host = _user("host")
    room = RoomRecord(
        session_id="session-1",
        room_code="ABCD12",
        host=host,
        users=[host],
        dm_style="classic",
    )
    client = FakeCleanupClient(join_status=200)

    results = await verify_cleanup_effects(client, "http://testserver", [room], {})

    assert results[0]["ok"] is False
    failed = results[0]["checks"][-1]
    assert failed["name"] == "old_room_code_rejected"
    assert failed["status_code"] is None
    assert failed["ok"] is False
    assert "returned 200" in failed["error"]


@pytest.mark.asyncio
async def test_verify_room_access_isolation_checks_members_and_blocks_outsiders():
    host = _user("host")
    player_two = _user("p2")
    other_host = _user("other-host")
    outsider = _user("outsider")
    rooms = [
        RoomRecord(
            session_id="session-1",
            room_code="ABCD12",
            host=host,
            users=[host, player_two],
            dm_style="classic",
        ),
        RoomRecord(
            session_id="session-2",
            room_code="WXYZ99",
            host=other_host,
            users=[other_host],
            dm_style="epic_crpg",
        ),
    ]
    client = FakeAccessClient(rooms, outsider)
    timings = {}

    await verify_room_access_isolation(client, "http://testserver", rooms, outsider, timings)
    await verify_session_snapshots(
        client,
        "http://testserver",
        "module-1",
        rooms,
        outsider,
        timings,
    )

    assert len(timings["member_get_room_ms"]) == 3
    assert len(timings["member_list_members_ms"]) == 3
    assert len(timings["outsider_get_room_forbidden_ms"]) == 2
    assert len(timings["outsider_list_members_forbidden_ms"]) == 2
    assert len(timings["member_get_session_ms"]) == 3
    assert len(timings["outsider_get_session_forbidden_ms"]) == 2
    assert {request["headers"]["Authorization"] for request in client.requests} == {
        "Bearer host-token",
        "Bearer p2-token",
        "Bearer other-host-token",
        "Bearer outsider-token",
    }


@pytest.mark.asyncio
async def test_verify_room_access_isolation_fails_when_outsider_can_read_room():
    host = _user("host")
    outsider = _user("outsider")
    room = RoomRecord(
        session_id="session-1",
        room_code="ABCD12",
        host=host,
        users=[host],
        dm_style="classic",
    )
    client = FakeAccessClient([room], outsider, allow_outsider=True)

    with pytest.raises(LoadTestError, match="returned 200"):
        await verify_room_access_isolation(client, "http://testserver", [room], outsider, {})


@pytest.mark.asyncio
async def test_verify_session_snapshots_fails_when_outsider_can_read_session():
    host = _user("host")
    outsider = _user("outsider")
    room = RoomRecord(
        session_id="session-1",
        room_code="ABCD12",
        host=host,
        users=[host],
        dm_style="classic",
    )
    client = FakeAccessClient([room], outsider, allow_outsider=True)

    with pytest.raises(LoadTestError, match="returned 200"):
        await verify_session_snapshots(
            client,
            "http://testserver",
            "module-1",
            [room],
            outsider,
            {},
        )
