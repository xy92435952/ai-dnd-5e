#!/usr/bin/env python
"""Run a real local multiplayer WebSocket load smoke test.

This script talks to a running backend (default: http://127.0.0.1:8002) instead
of using pytest mocks. It creates 50 users across 13 four-player rooms, opens
50 WebSocket connections, verifies ping/pong and same-room typing isolation,
then deletes the test sessions it created.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
import websockets


DEFAULT_ROOM_SIZES = [4] * 12 + [2]
DEFAULT_DM_STYLES = ["classic", "dark_fantasy", "lighthearted", "epic_crpg", "hardcore"]
SMOKE_MODULE_TEXT = """Codex Load Test Module

Name: The Clockwork Crossing
Setting: A compact keep built around an ancient planar gate.
Tone: Practical heroic fantasy with clear tactical stakes.
Recommended party size: 4
Level range: 1-3

Scene 1: The party arrives at the gatehouse while brass sentries scan the road.
Scene 2: A negotiation with Keeper Mara can reveal that the gate is unstable.
Scene 3: If talks fail, two training constructs block the crossing.

NPCs:
- Keeper Mara, cautious gate warden, wants the crossing stabilized.

Monsters:
- Training Construct, CR 1/4, armor class 13, hit points 11, speed 30 ft,
  attack: slam +3 to hit for 1d6+1 bludgeoning damage.

Reward: A gate token worth 25 gp and safe passage through the keep.
"""


@dataclass
class UserRecord:
    username: str
    token: str
    user_id: str


@dataclass
class RoomRecord:
    session_id: str
    room_code: str
    host: UserRecord
    users: list[UserRecord]
    dm_style: str


@dataclass
class WSRecord:
    room: RoomRecord
    user: UserRecord
    websocket: Any
    received: list[dict[str, Any]] = field(default_factory=list)
    reader_task: asyncio.Task | None = None


class LoadTestError(RuntimeError):
    pass


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100) * (len(ordered) - 1)))))
    return ordered[index]


def api_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def ws_url(base_url: str, session_id: str, token: str) -> str:
    if base_url.startswith("https://"):
        ws_base = "wss://" + base_url[len("https://") :]
    elif base_url.startswith("http://"):
        ws_base = "ws://" + base_url[len("http://") :]
    else:
        raise LoadTestError(f"Unsupported base URL: {base_url}")
    return f"{ws_base.rstrip('/')}/ws/sessions/{session_id}?token={token}"


async def timed(label: str, timings: dict[str, list[float]], coro):
    start = time.perf_counter()
    result = await coro
    timings.setdefault(label, []).append((time.perf_counter() - start) * 1000)
    return result


async def request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    expected: set[int] | None = None,
    **kwargs,
) -> tuple[int, Any]:
    response = await client.request(method, url, **kwargs)
    expected = expected or {200}
    if response.status_code not in expected:
        raise LoadTestError(f"{method} {url} returned {response.status_code}: {response.text[:500]}")
    if response.text:
        return response.status_code, response.json()
    return response.status_code, None


async def request_json_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    timings: dict[str, list[float]],
    timing_label: str,
    retries: int,
    retry_delay: float,
    retry_statuses: set[int] | None = None,
    expected: set[int] | None = None,
    **kwargs,
) -> tuple[int, Any]:
    """Retry slow setup calls so auth throttling does not mask game capacity."""

    retry_statuses = retry_statuses or {429}
    expected = expected or {200}
    last_status = 0
    last_text = ""

    for attempt in range(retries + 1):
        start = time.perf_counter()
        response = await client.request(method, url, **kwargs)
        timings.setdefault(timing_label, []).append((time.perf_counter() - start) * 1000)

        if response.status_code in expected:
            if response.text:
                return response.status_code, response.json()
            return response.status_code, None

        last_status = response.status_code
        last_text = response.text[:500]
        if response.status_code not in retry_statuses or attempt >= retries:
            break

        retry_after = response.headers.get("Retry-After")
        try:
            server_delay = float(retry_after) if retry_after else 0
        except ValueError:
            server_delay = 0
        backoff = max(server_delay, retry_delay * (2**attempt))
        await asyncio.sleep(backoff)

    raise LoadTestError(f"{method} {url} returned {last_status}: {last_text}")


async def register_users(
    client: httpx.AsyncClient,
    base_url: str,
    count: int,
    prefix: str,
    timings: dict[str, list[float]],
    concurrency: int,
    delay: float,
    retries: int,
) -> list[UserRecord]:
    sem = asyncio.Semaphore(concurrency)
    pace_lock = asyncio.Lock()
    next_auth_at = 0.0

    async def wait_for_auth_slot() -> None:
        nonlocal next_auth_at
        if delay <= 0:
            return
        async with pace_lock:
            now = time.perf_counter()
            wait_seconds = max(0.0, next_auth_at - now)
            next_auth_at = max(now, next_auth_at) + delay
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

    async def one(index: int) -> UserRecord:
        async with sem:
            username = f"{prefix}_u{index:02d}"
            await wait_for_auth_slot()
            _, payload = await request_json_with_retry(
                client,
                "POST",
                api_url(base_url, "/auth/register"),
                timings=timings,
                timing_label="register_ms",
                retries=retries,
                retry_delay=max(delay, 0.5),
                json={
                    "username": username,
                    "password": "password",
                    "display_name": f"Load User {index:02d}",
                },
                expected={200, 409},
            )
            if payload and "token" in payload:
                return UserRecord(username=username, token=payload["token"], user_id=payload["user_id"])

            await wait_for_auth_slot()
            _, payload = await request_json_with_retry(
                client,
                "POST",
                api_url(base_url, "/auth/login"),
                timings=timings,
                timing_label="login_ms",
                retries=retries,
                retry_delay=max(delay, 0.5),
                json={"username": username, "password": "password"},
            )
            return UserRecord(username=username, token=payload["token"], user_id=payload["user_id"])

    return await asyncio.gather(*(one(index) for index in range(count)))


async def find_ready_module(
    client: httpx.AsyncClient,
    base_url: str,
    token: str,
    timings: dict[str, list[float]],
) -> str | None:
    _, modules = await timed(
        "list_modules_ms",
        timings,
        request_json(
            client,
            "GET",
            api_url(base_url, "/modules/"),
            headers={"Authorization": f"Bearer {token}"},
        ),
    )
    ready = [module for module in modules if module.get("parse_status") == "done"]
    if not ready:
        return None
    return ready[0]["id"]


async def wait_for_module_ready(
    client: httpx.AsyncClient,
    base_url: str,
    module_id: str,
    token: str,
    timings: dict[str, list[float]],
    timeout: float,
    interval: float,
) -> str:
    deadline = time.perf_counter() + timeout
    last_status = "unknown"
    last_error = ""

    while time.perf_counter() < deadline:
        _, detail = await timed(
            "get_module_ms",
            timings,
            request_json(
                client,
                "GET",
                api_url(base_url, f"/modules/{module_id}"),
                headers={"Authorization": f"Bearer {token}"},
            ),
        )
        last_status = detail.get("parse_status") or "unknown"
        last_error = detail.get("parse_error") or ""
        if last_status == "done":
            return module_id
        if last_status == "failed":
            raise LoadTestError(f"Module {module_id} parsing failed: {last_error}")
        await asyncio.sleep(interval)

    raise LoadTestError(
        f"Module {module_id} was not ready after {timeout}s "
        f"(last status={last_status}, error={last_error})"
    )


async def upload_smoke_module(
    client: httpx.AsyncClient,
    base_url: str,
    token: str,
    prefix: str,
    timings: dict[str, list[float]],
) -> str:
    filename = f"{prefix}_module.txt"
    _, uploaded = await timed(
        "upload_module_ms",
        timings,
        request_json(
            client,
            "POST",
            api_url(base_url, "/modules/upload"),
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (filename, SMOKE_MODULE_TEXT.encode("utf-8"), "text/plain")},
        ),
    )
    return uploaded["id"]


async def resolve_module(
    client: httpx.AsyncClient,
    base_url: str,
    token: str,
    prefix: str,
    timings: dict[str, list[float]],
    module_id: str,
    auto_module: bool,
    timeout: float,
    interval: float,
) -> tuple[str, str | None]:
    if module_id:
        return (
            await wait_for_module_ready(client, base_url, module_id, token, timings, timeout, interval),
            None,
        )

    ready_module_id = await find_ready_module(client, base_url, token, timings)
    if ready_module_id:
        return ready_module_id, None

    if not auto_module:
        raise LoadTestError(
            "No ready module found for this user. Provide --module-id or allow auto module upload."
        )

    created_module_id = await upload_smoke_module(client, base_url, token, prefix, timings)
    await wait_for_module_ready(client, base_url, created_module_id, token, timings, timeout, interval)
    return created_module_id, created_module_id


async def create_rooms(
    client: httpx.AsyncClient,
    base_url: str,
    module_id: str,
    users: list[UserRecord],
    prefix: str,
    timings: dict[str, list[float]],
    concurrency: int,
) -> list[RoomRecord]:
    cursor = 0
    rooms: list[RoomRecord] = []

    for room_idx, size in enumerate(DEFAULT_ROOM_SIZES):
        host = users[cursor]
        cursor += 1
        dm_style = DEFAULT_DM_STYLES[room_idx % len(DEFAULT_DM_STYLES)]
        _, created = await timed(
            "create_room_ms",
            timings,
            request_json(
                client,
                "POST",
                api_url(base_url, "/game/rooms/create"),
                headers={"Authorization": f"Bearer {host.token}"},
                json={
                    "module_id": module_id,
                    "save_name": f"{prefix} room {room_idx}",
                    "max_players": 4,
                    "dm_style": dm_style,
                },
            ),
        )
        rooms.append(
            RoomRecord(
                session_id=created["session_id"],
                room_code=created["room_code"],
                host=host,
                users=[host],
                dm_style=dm_style,
            )
        )

        joiners = users[cursor : cursor + size - 1]
        cursor += size - 1
        sem = asyncio.Semaphore(concurrency)

        async def join(user: UserRecord) -> UserRecord:
            async with sem:
                await timed(
                    "join_room_ms",
                    timings,
                    request_json(
                        client,
                        "POST",
                        api_url(base_url, "/game/rooms/join"),
                        headers={"Authorization": f"Bearer {user.token}"},
                        json={"room_code": created["room_code"]},
                    ),
                )
                return user

        rooms[-1].users.extend(await asyncio.gather(*(join(user) for user in joiners)))

    if cursor != len(users):
        raise LoadTestError(f"Expected to assign all users; assigned {cursor}, total {len(users)}")
    return rooms


async def assert_full_room_rejects_overflow(
    client: httpx.AsyncClient,
    base_url: str,
    room: RoomRecord,
    overflow_user: UserRecord,
    timings: dict[str, list[float]],
) -> None:
    status, payload = await timed(
        "overflow_join_ms",
        timings,
        request_json(
            client,
            "POST",
            api_url(base_url, "/game/rooms/join"),
            headers={"Authorization": f"Bearer {overflow_user.token}"},
            json={"room_code": room.room_code},
            expected={409},
        ),
    )
    if status != 409:
        raise LoadTestError(f"Expected full room rejection, got {status}: {payload}")


async def read_ws(record: WSRecord) -> None:
    try:
        async for message in record.websocket:
            record.received.append(json.loads(message))
    except websockets.ConnectionClosed:
        return


async def connect_websockets(
    base_url: str,
    rooms: list[RoomRecord],
    timings: dict[str, list[float]],
    concurrency: int,
) -> list[WSRecord]:
    sem = asyncio.Semaphore(concurrency)

    async def connect(room: RoomRecord, user: UserRecord) -> WSRecord:
        async with sem:
            start = time.perf_counter()
            ws = await websockets.connect(
                ws_url(base_url, room.session_id, user.token),
                open_timeout=10,
                ping_interval=None,
            )
            timings.setdefault("ws_connect_ms", []).append((time.perf_counter() - start) * 1000)
            record = WSRecord(room=room, user=user, websocket=ws)
            record.reader_task = asyncio.create_task(read_ws(record))
            return record

    return await asyncio.gather(*(connect(room, user) for room in rooms for user in room.users))


async def wait_for_event(
    record: WSRecord,
    event_type: str,
    *,
    start_index: int = 0,
    timeout: float = 5.0,
) -> dict[str, Any]:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        for event in record.received[start_index:]:
            if event.get("type") == event_type:
                return event
        await asyncio.sleep(0.01)
    raise LoadTestError(
        f"Timed out waiting for {event_type} for user={record.user.username} room={record.room.room_code}"
    )


async def verify_ping_pong(records: list[WSRecord], timings: dict[str, list[float]]) -> None:
    async def one(record: WSRecord) -> None:
        start_index = len(record.received)
        start = time.perf_counter()
        await record.websocket.send(json.dumps({"type": "ping"}))
        await wait_for_event(record, "pong", start_index=start_index, timeout=5)
        timings.setdefault("ws_ping_pong_ms", []).append((time.perf_counter() - start) * 1000)

    await asyncio.gather(*(one(record) for record in records))


async def verify_room_info(
    client: httpx.AsyncClient,
    base_url: str,
    rooms: list[RoomRecord],
    timings: dict[str, list[float]],
) -> None:
    async def one(room: RoomRecord) -> dict[str, Any]:
        _, info = await timed(
            "get_room_ms",
            timings,
            request_json(
                client,
                "GET",
                api_url(base_url, f"/game/rooms/{room.session_id}"),
                headers={"Authorization": f"Bearer {room.host.token}"},
            ),
        )
        member_ids = {member["user_id"] for member in info["members"]}
        expected_ids = {user.user_id for user in room.users}
        if member_ids != expected_ids:
            raise LoadTestError(f"Room {room.room_code} member mismatch")
        if info["max_players"] != 4:
            raise LoadTestError(f"Room {room.room_code} max_players drifted: {info['max_players']}")
        dm_style = info.get("dm_style")
        if not isinstance(dm_style, dict):
            raise LoadTestError(f"Room {room.room_code} response missing dm_style: {info}")
        if dm_style.get("key") != room.dm_style:
            raise LoadTestError(f"Room {room.room_code} dm_style mismatch: {dm_style}")
        groups = {group["id"]: group for group in info["party_groups"]}
        if set(groups["main"]["member_user_ids"]) != expected_ids:
            raise LoadTestError(f"Room {room.room_code} group membership mismatch")
        return info

    await asyncio.gather(*(one(room) for room in rooms))


async def verify_typing_isolation(records: list[WSRecord], timings: dict[str, list[float]]) -> None:
    first_room = records[0].room
    room_records = [record for record in records if record.room.session_id == first_room.session_id]
    sender = room_records[0]
    receivers = [record for record in room_records if record is not sender]
    outsiders = [record for record in records if record.room.session_id != first_room.session_id]
    before_counts = {id(record): len(record.received) for record in records}

    start = time.perf_counter()
    await sender.websocket.send(json.dumps({"type": "typing", "is_typing": True}))
    events = await asyncio.gather(*(
        wait_for_event(record, "typing", start_index=before_counts[id(record)], timeout=5)
        for record in receivers
    ))
    timings.setdefault("typing_broadcast_ms", []).append((time.perf_counter() - start) * 1000)

    if len(events) != len(receivers):
        raise LoadTestError("Not all same-room receivers got typing event")
    if any(event.get("user_id") != sender.user.user_id for event in events):
        raise LoadTestError("Typing event sender mismatch")
    if any(event.get("type") == "typing" for event in sender.received[before_counts[id(sender)] :]):
        raise LoadTestError("Sender received its own typing event")

    await asyncio.sleep(0.1)
    leaked = [
        record.user.username
        for record in outsiders
        if any(event.get("type") == "typing" for event in record.received[before_counts[id(record)] :])
    ]
    if leaked:
        raise LoadTestError(f"Typing event leaked to other rooms: {leaked[:5]}")


async def close_websockets(records: list[WSRecord]) -> None:
    for record in records:
        try:
            await record.websocket.close()
        except Exception:
            pass
    tasks = [record.reader_task for record in records if record.reader_task is not None]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def cleanup_rooms(
    client: httpx.AsyncClient,
    base_url: str,
    rooms: list[RoomRecord],
) -> list[dict[str, Any]]:
    results = []
    for room in rooms:
        try:
            response = await client.delete(
                api_url(base_url, f"/game/sessions/{room.session_id}"),
                headers={"Authorization": f"Bearer {room.host.token}"},
            )
            results.append({
                "session_id": room.session_id,
                "status_code": response.status_code,
                "ok": response.status_code == 200,
            })
        except Exception as exc:
            results.append({
                "session_id": room.session_id,
                "status_code": None,
                "ok": False,
                "error": str(exc),
            })
    return results


async def cleanup_module(
    client: httpx.AsyncClient,
    base_url: str,
    module_id: str | None,
    token: str | None,
) -> dict[str, Any] | None:
    if not module_id or not token:
        return None
    try:
        response = await client.delete(
            api_url(base_url, f"/modules/{module_id}"),
            headers={"Authorization": f"Bearer {token}"},
        )
        return {
            "module_id": module_id,
            "status_code": response.status_code,
            "ok": response.status_code == 200,
        }
    except Exception as exc:
        return {
            "module_id": module_id,
            "status_code": None,
            "ok": False,
            "error": str(exc),
        }


def summarize_timings(timings: dict[str, list[float]]) -> dict[str, dict[str, float]]:
    summary = {}
    for label, values in sorted(timings.items()):
        summary[label] = {
            "count": len(values),
            "avg_ms": round(statistics.fmean(values), 2) if values else 0,
            "p95_ms": round(percentile(values, 95), 2),
            "max_ms": round(max(values), 2) if values else 0,
        }
    return summary


async def run(args: argparse.Namespace) -> dict[str, Any]:
    prefix = args.prefix or f"lt_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    timings: dict[str, list[float]] = {}
    rooms: list[RoomRecord] = []
    ws_records: list[WSRecord] = []
    users: list[UserRecord] = []
    module_id: str | None = None
    created_module_id: str | None = None
    started = time.perf_counter()

    async with httpx.AsyncClient(timeout=args.http_timeout) as client:
        try:
            await request_json(client, "GET", api_url(args.base_url, "/health"))
            users = await register_users(
                client,
                args.base_url,
                args.users,
                prefix,
                timings,
                args.auth_concurrency,
                args.auth_delay,
                args.auth_retries,
            )
            overflow = await register_users(
                client,
                args.base_url,
                1,
                f"{prefix}_overflow",
                timings,
                args.auth_concurrency,
                args.auth_delay,
                args.auth_retries,
            )
            module_id, created_module_id = await resolve_module(
                client,
                args.base_url,
                users[0].token,
                prefix,
                timings,
                args.module_id,
                not args.no_auto_module,
                args.module_timeout,
                args.module_poll_interval,
            )
            rooms = await create_rooms(
                client,
                args.base_url,
                module_id,
                users,
                prefix,
                timings,
                args.http_concurrency,
            )
            await assert_full_room_rejects_overflow(client, args.base_url, rooms[0], overflow[0], timings)
            ws_records = await connect_websockets(args.base_url, rooms, timings, args.ws_concurrency)
            await verify_ping_pong(ws_records, timings)
            await verify_room_info(client, args.base_url, rooms, timings)
            await verify_typing_isolation(ws_records, timings)
            ok = True
            error = None
        except Exception as exc:
            ok = False
            error = f"{type(exc).__name__}: {exc}"
        finally:
            await close_websockets(ws_records)
            cleanup = await cleanup_rooms(client, args.base_url, rooms) if rooms else []
            module_cleanup = await cleanup_module(
                client,
                args.base_url,
                created_module_id,
                users[0].token if users else None,
            )

    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "ok": ok,
        "error": error,
        "base_url": args.base_url,
        "prefix": prefix,
        "module_id": module_id,
        "created_module_id": created_module_id,
        "users": args.users,
        "rooms": len(rooms),
        "websockets": len(ws_records),
        "room_sizes": [len(room.users) for room in rooms],
        "cleanup": cleanup,
        "module_cleanup": module_cleanup,
        "elapsed_ms": round(elapsed_ms, 2),
        "timings": summarize_timings(timings),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8002")
    parser.add_argument("--users", type=int, default=50)
    parser.add_argument("--prefix", default="")
    parser.add_argument("--http-concurrency", type=int, default=10)
    parser.add_argument("--auth-concurrency", type=int, default=1)
    parser.add_argument("--auth-delay", type=float, default=0.5)
    parser.add_argument("--auth-retries", type=int, default=5)
    parser.add_argument("--module-id", default="")
    parser.add_argument("--no-auto-module", action="store_true")
    parser.add_argument("--module-timeout", type=float, default=90)
    parser.add_argument("--module-poll-interval", type=float, default=1.0)
    parser.add_argument("--ws-concurrency", type=int, default=25)
    parser.add_argument("--http-timeout", type=float, default=30)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.users != sum(DEFAULT_ROOM_SIZES):
        raise SystemExit(
            f"This smoke test currently expects {sum(DEFAULT_ROOM_SIZES)} users "
            f"for room sizes {DEFAULT_ROOM_SIZES}; got {args.users}."
        )
    result = asyncio.run(run(args))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
