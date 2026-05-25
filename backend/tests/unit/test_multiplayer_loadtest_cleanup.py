import json
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.multiplayer_ws_loadtest import RoomRecord, UserRecord, cleanup_rooms


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


def _user(name):
    return UserRecord(username=name, token=f"{name}-token", user_id=f"{name}-id")


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
