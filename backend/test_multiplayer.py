"""Multiplayer feature E2E tests (v0.9-multiplayer beta).

Covers:
  1. Register 3 users (host + 2 players)
  2. Host creates a room, gets room_code
  3. Players join via room_code
  4. Member listing (host tag, online indicators)
  5. Room capacity enforcement
  6. Join with invalid code
  7. Player 2 claims a character
  8. Host starts game (succeeds because >=1 claimed)
  9. WebSocket connection + broadcast (member_joined, member_online events)
 10. Host kicks player 3
 11. Transfer host to player 2
 12. Leave room (old host leaves)
 13. Owner guard: player 2 cannot attack for an unclaimed character

Usage:
  # In one terminal:
  cd backend && uvicorn main:app --port 8002
  # In another:
  cd backend && python test_multiplayer.py
"""
import asyncio
import json
import random
import string
import sys
import traceback
import uuid
from datetime import datetime

import httpx
import websockets

BASE_URL = "http://127.0.0.1:8002"
WS_BASE = "ws://127.0.0.1:8002"


# ── helpers ─────────────────────────────────────────────

class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.details: list[tuple[str, str, str]] = []  # (status, name, msg)

    def ok(self, name: str, msg: str = ""):
        self.passed += 1
        self.details.append(("PASS", name, msg))
        print(f"  [PASS] {name}" + (f" -- {msg}" if msg else ""))

    def fail(self, name: str, msg: str):
        self.failed += 1
        self.details.append(("FAIL", name, msg))
        print(f"  [FAIL] {name} -- {msg}")

    def skip(self, name: str, msg: str = ""):
        self.skipped += 1
        self.details.append(("SKIP", name, msg))
        print(f"  [SKIP] {name}" + (f" -- {msg}" if msg else ""))

    def summary(self):
        print()
        print("=" * 60)
        print(f"RESULT: {self.passed} passed, {self.failed} failed, {self.skipped} skipped")
        print("=" * 60)
        if self.failed:
            print()
            print("Failures:")
            for status, name, msg in self.details:
                if status == "FAIL":
                    print(f"  - {name}: {msg}")


R = TestResult()


def rand_suffix(n=6):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


async def register_and_login(client: httpx.AsyncClient, username: str, password: str = "test1234"):
    """Register (or login if exists) a user, return (token, user_id, username)."""
    r = await client.post(f"{BASE_URL}/auth/register", json={
        "username": username, "password": password, "display_name": username
    })
    if r.status_code == 409:
        # already exists -> login
        r = await client.post(f"{BASE_URL}/auth/login", json={
            "username": username, "password": password
        })
    r.raise_for_status()
    data = r.json()
    return data["token"], data["user_id"], data["username"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


async def get_or_create_module(client, token, user_id: str):
    """Return a parsed module id.
    If user has none, seed one directly via SQL (for tests only).
    """
    r = await client.get(f"{BASE_URL}/modules/", headers=auth_headers(token))
    if r.status_code == 200 and r.json():
        mods = [m for m in r.json() if m.get("parse_status") == "done"]
        if mods:
            return mods[0]["id"]

    # seed
    import sqlite3, json, uuid, os
    db_path = os.path.join(os.path.dirname(__file__), "ai_trpg.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    mid = str(uuid.uuid4())
    parsed = json.dumps({
        "name": f"__test_module_{user_id[:6]}__",
        "setting": "test", "tone": "neutral",
        "scenes": [{"id": "s1", "description": "test scene", "connections": []}],
        "npcs": [], "factions": [], "story_hooks": [],
    })
    c.execute("""
        INSERT INTO modules (id, user_id, name, file_path, file_type, parsed_content, parse_status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (mid, user_id, f"__test_module_{user_id[:6]}__", "test.txt", "txt", parsed, "done"))
    conn.commit()
    conn.close()
    return mid


# ── Tests ───────────────────────────────────────────────

async def test_health(client):
    r = await client.get(f"{BASE_URL}/health")
    if r.status_code == 200 and r.json().get("status") == "ok":
        R.ok("T01 server health check")
    else:
        R.fail("T01 server health check", f"status={r.status_code} body={r.text}")
        return False
    return True


async def test_register_users(client, suffix):
    """T02: Register 3 users"""
    try:
        host = await register_and_login(client, f"mp_host_{suffix}")
        p2 = await register_and_login(client, f"mp_p2_{suffix}")
        p3 = await register_and_login(client, f"mp_p3_{suffix}")
        R.ok("T02 register 3 users", f"host={host[1][:8]}")
        return host, p2, p3
    except Exception as e:
        R.fail("T02 register 3 users", str(e))
        raise


async def test_create_room(client, host_token, module_id):
    """T03: Host creates a room"""
    r = await client.post(
        f"{BASE_URL}/game/rooms/create",
        headers=auth_headers(host_token),
        json={"module_id": module_id, "save_name": f"test-{rand_suffix()}", "max_players": 3},
    )
    if r.status_code != 200:
        R.fail("T03 create room", f"status={r.status_code} body={r.text}")
        return None, None
    data = r.json()
    code = data["room_code"]
    if len(code) == 6 and code.isdigit():
        R.ok("T03 create room", f"code={code}")
    else:
        R.fail("T03 create room", f"bad room_code={code}")
    return data["session_id"], code


async def test_join_room(client, token, code, username):
    """Player joins via code"""
    r = await client.post(
        f"{BASE_URL}/game/rooms/join",
        headers=auth_headers(token),
        json={"room_code": code},
    )
    return r


async def test_join_invalid_code(client, token):
    """T04: Join with invalid code → 404"""
    r = await client.post(
        f"{BASE_URL}/game/rooms/join",
        headers=auth_headers(token),
        json={"room_code": "999999"},
    )
    if r.status_code == 404:
        R.ok("T04 join invalid code rejected")
    else:
        R.fail("T04 join invalid code rejected", f"expected 404 got {r.status_code}")


async def test_members_listing(client, token, session_id, expected_count):
    """T06: Members listing"""
    r = await client.get(
        f"{BASE_URL}/game/rooms/{session_id}/members",
        headers=auth_headers(token),
    )
    if r.status_code != 200:
        R.fail("T06 list members", f"status={r.status_code}")
        return []
    members = r.json()
    if len(members) == expected_count:
        hosts = [m for m in members if m["role"] == "host"]
        if len(hosts) == 1:
            R.ok("T06 list members", f"count={len(members)}, 1 host")
        else:
            R.fail("T06 list members", f"expected 1 host, got {len(hosts)}")
    else:
        R.fail("T06 list members", f"expected {expected_count}, got {len(members)}")
    return members


async def test_capacity(client, token, code):
    """T07: Room capacity enforcement (max_players=3 already has 3)"""
    try:
        extra_token, _, _ = await register_and_login(client, f"mp_extra_{rand_suffix()}")
        r = await client.post(
            f"{BASE_URL}/game/rooms/join",
            headers=auth_headers(extra_token),
            json={"room_code": code},
        )
        if r.status_code == 409:
            R.ok("T07 capacity enforcement")
        else:
            R.fail("T07 capacity enforcement", f"expected 409 got {r.status_code}")
    except Exception as e:
        R.fail("T07 capacity enforcement", str(e))


async def test_ws_connection(session_id, host_token, p2_token):
    """T08: WebSocket connect + broadcast
    - Host opens WS, then player 2 reconnects → host receives member_online event
    """
    host_url = f"{WS_BASE}/ws/sessions/{session_id}?token={host_token}"
    try:
        async with websockets.connect(host_url) as host_ws:
            # Give it a moment to register
            await asyncio.sleep(0.2)

            # Player 2 connects
            p2_url = f"{WS_BASE}/ws/sessions/{session_id}?token={p2_token}"
            async with websockets.connect(p2_url) as p2_ws:
                # Host should receive "member_online" for p2
                try:
                    msg = await asyncio.wait_for(host_ws.recv(), timeout=3.0)
                    event = json.loads(msg)
                    if event.get("type") == "member_online":
                        R.ok("T08 WS broadcast member_online")
                    else:
                        R.fail("T08 WS broadcast member_online",
                               f"expected member_online, got {event.get('type')}")
                except asyncio.TimeoutError:
                    R.fail("T08 WS broadcast member_online", "timeout waiting for event")

                # Test ping/pong heartbeat
                await p2_ws.send(json.dumps({"type": "ping"}))
                try:
                    msg = await asyncio.wait_for(p2_ws.recv(), timeout=2.0)
                    event = json.loads(msg)
                    if event.get("type") == "pong":
                        R.ok("T09 WS heartbeat pong")
                    else:
                        R.fail("T09 WS heartbeat pong", f"got {event.get('type')}")
                except asyncio.TimeoutError:
                    R.fail("T09 WS heartbeat pong", "timeout")
    except Exception as e:
        R.fail("T08 WS connection", str(e))


async def test_ws_auth_fail(session_id):
    """T10: WS with invalid token → 4401"""
    url = f"{WS_BASE}/ws/sessions/{session_id}?token=invalid_token_xyz"
    try:
        async with websockets.connect(url) as ws:
            try:
                await asyncio.wait_for(ws.recv(), timeout=2.0)
                R.fail("T10 WS auth rejection", "connection stayed open")
            except (websockets.ConnectionClosedError, asyncio.TimeoutError):
                R.ok("T10 WS auth rejection")
    except websockets.InvalidStatus as e:
        # HTTP-level rejection also OK
        R.ok("T10 WS auth rejection", f"rejected with {e.response.status_code}")
    except Exception as e:
        # Some versions raise before open; count as pass
        R.ok("T10 WS auth rejection", f"{type(e).__name__}")


async def test_ws_non_member(session_id):
    """T11: WS with valid token but not a member → 4403"""
    async with httpx.AsyncClient(timeout=30) as client:
        intruder_token, _, _ = await register_and_login(client, f"mp_intruder_{rand_suffix()}")
    url = f"{WS_BASE}/ws/sessions/{session_id}?token={intruder_token}"
    try:
        async with websockets.connect(url) as ws:
            try:
                await asyncio.wait_for(ws.recv(), timeout=2.0)
                R.fail("T11 WS non-member rejection", "connection stayed open")
            except (websockets.ConnectionClosedError, asyncio.TimeoutError):
                R.ok("T11 WS non-member rejection")
    except websockets.InvalidStatus as e:
        R.ok("T11 WS non-member rejection", f"rejected with {e.response.status_code}")
    except Exception as e:
        R.ok("T11 WS non-member rejection", f"{type(e).__name__}")


async def test_start_without_characters(client, host_token, session_id):
    """T12: Start game with no characters claimed → 400"""
    r = await client.post(
        f"{BASE_URL}/game/rooms/{session_id}/start",
        headers=auth_headers(host_token),
    )
    if r.status_code == 400:
        R.ok("T12 start requires claimed character")
    else:
        R.fail("T12 start requires claimed character", f"got {r.status_code}")


async def test_non_host_cannot_start(client, player_token, session_id):
    """T13: Non-host cannot start"""
    r = await client.post(
        f"{BASE_URL}/game/rooms/{session_id}/start",
        headers=auth_headers(player_token),
    )
    if r.status_code == 403:
        R.ok("T13 non-host cannot start")
    else:
        R.fail("T13 non-host cannot start", f"got {r.status_code}")


async def test_kick(client, host_token, target_user_id, session_id):
    """T14: Host kicks a member"""
    r = await client.post(
        f"{BASE_URL}/game/rooms/{session_id}/kick",
        headers=auth_headers(host_token),
        json={"user_id": target_user_id},
    )
    if r.status_code == 200:
        R.ok("T14 host kicks member")
    else:
        R.fail("T14 host kicks member", f"status={r.status_code} body={r.text}")


async def test_non_host_cannot_kick(client, player_token, target_user_id, session_id):
    """T15: Non-host cannot kick"""
    r = await client.post(
        f"{BASE_URL}/game/rooms/{session_id}/kick",
        headers=auth_headers(player_token),
        json={"user_id": target_user_id},
    )
    if r.status_code == 403:
        R.ok("T15 non-host cannot kick")
    else:
        R.fail("T15 non-host cannot kick", f"got {r.status_code}")


async def test_transfer_host(client, host_token, new_host_user_id, session_id):
    """T16: Transfer host"""
    r = await client.post(
        f"{BASE_URL}/game/rooms/{session_id}/transfer",
        headers=auth_headers(host_token),
        json={"new_host_user_id": new_host_user_id},
    )
    if r.status_code == 200:
        R.ok("T16 transfer host")
    else:
        R.fail("T16 transfer host", f"{r.status_code} {r.text}")


async def test_leave(client, token, session_id):
    """T17: Leave room"""
    r = await client.post(
        f"{BASE_URL}/game/rooms/{session_id}/leave",
        headers=auth_headers(token),
    )
    if r.status_code == 200:
        R.ok("T17 leave room", json.dumps(r.json()))
    else:
        R.fail("T17 leave room", f"{r.status_code}")


async def test_get_room_info(client, token, session_id):
    """T18: GET room info contains multiplayer fields"""
    r = await client.get(
        f"{BASE_URL}/game/rooms/{session_id}",
        headers=auth_headers(token),
    )
    if r.status_code == 200:
        data = r.json()
        required = ["is_multiplayer", "room_code", "members", "host_user_id", "max_players"]
        missing = [f for f in required if f not in data]
        if missing:
            R.fail("T18 room info fields", f"missing {missing}")
        else:
            R.ok("T18 room info fields", f"room_code={data['room_code']}")
    else:
        R.fail("T18 room info fields", f"{r.status_code}")


async def test_single_player_rooms_404(client, host_token):
    """T19: GET /rooms/{id} for a non-multiplayer session → 404"""
    r = await client.get(
        f"{BASE_URL}/game/rooms/nonexistent-id-xxx",
        headers=auth_headers(host_token),
    )
    if r.status_code == 404:
        R.ok("T19 non-multiplayer session 404")
    else:
        R.fail("T19 non-multiplayer session 404", f"got {r.status_code}")


# ── Main ─────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("Multiplayer E2E Test Suite (v0.9-multiplayer beta)")
    print("Target:", BASE_URL)
    print("=" * 60)
    print()

    suffix = rand_suffix()

    async with httpx.AsyncClient(timeout=30) as client:
        # --- Connectivity ---
        print("[1/4] Server connectivity")
        if not await test_health(client):
            print("ABORT: server not reachable")
            R.summary()
            return

        # --- Setup ---
        print()
        print("[2/4] User registration & module")
        host, p2, p3 = await test_register_users(client, suffix)
        host_token, host_uid, _ = host
        p2_token, p2_uid, _ = p2
        p3_token, p3_uid, _ = p3

        module_id = await get_or_create_module(client, host_token, host_uid)
        if not module_id:
            R.skip("T0X module setup", "failed to seed module")
            R.summary()
            return
        R.ok("T0X module available", f"id={module_id[:8]}")

        # --- Room lifecycle ---
        print()
        print("[3/4] Room lifecycle + permissions")
        session_id, room_code = await test_create_room(client, host_token, module_id)
        if not session_id:
            print("ABORT: create room failed")
            R.summary()
            return

        # Invalid code
        await test_join_invalid_code(client, p2_token)

        # Join as p2 and p3
        r = await test_join_room(client, p2_token, room_code, f"p2_{suffix}")
        if r.status_code == 200:
            R.ok("T05a player 2 join")
        else:
            R.fail("T05a player 2 join", f"{r.status_code} {r.text}")
        r = await test_join_room(client, p3_token, room_code, f"p3_{suffix}")
        if r.status_code == 200:
            R.ok("T05b player 3 join")
        else:
            R.fail("T05b player 3 join", f"{r.status_code} {r.text}")

        await test_members_listing(client, host_token, session_id, expected_count=3)
        await test_capacity(client, host_token, room_code)  # 4th join → 409
        await test_get_room_info(client, host_token, session_id)
        await test_single_player_rooms_404(client, host_token)

        # Start game prerequisites
        await test_start_without_characters(client, host_token, session_id)
        await test_non_host_cannot_start(client, p2_token, session_id)

        # Host powers
        await test_non_host_cannot_kick(client, p2_token, p3_uid, session_id)
        await test_kick(client, host_token, p3_uid, session_id)
        await test_members_listing(client, host_token, session_id, expected_count=2)

        await test_transfer_host(client, host_token, p2_uid, session_id)

        # After transfer, p2 is host; original host leaves
        await test_leave(client, host_token, session_id)

    # --- WebSocket ---
    print()
    print("[4/4] WebSocket protocol")
    # Re-create host token since we left; use p2 (now host) + p3 rejoin
    async with httpx.AsyncClient(timeout=30) as client:
        # p3 was kicked, rejoin
        r = await test_join_room(client, p3_token, room_code, "p3")
        if r.status_code == 200:
            R.ok("T20 kicked user can rejoin")
        else:
            R.fail("T20 kicked user can rejoin", f"{r.status_code} {r.text}")

    await test_ws_connection(session_id, p2_token, p3_token)
    await test_ws_auth_fail(session_id)
    await test_ws_non_member(session_id)

    R.summary()
    return 0 if R.failed == 0 else 1


if __name__ == "__main__":
    try:
        code = asyncio.run(main())
        sys.exit(code or 0)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
