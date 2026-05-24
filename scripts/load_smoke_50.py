"""Closed-beta 50-user online smoke test.

This script exercises low-risk authenticated HTTP paths concurrently. It does
not call the DM model by default, so it can be used before expensive gameplay
load tests. Run against a disposable or beta test environment.

The 50-user target means 50 simultaneous users across the server, typically
spread across independent sessions/rooms. It is not a single-game party size;
normal multiplayer game rooms remain capped by the room configuration, currently
4 players in the product test baseline.

Example:
    python scripts/load_smoke_50.py --base-url http://127.0.0.1:8000 --users 50
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import sqlite3
import statistics
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx


@dataclass
class Metric:
    name: str
    ok: bool
    elapsed_ms: float
    status_code: int | None = None
    error: str = ""
    body: str = ""


@dataclass
class RunResult:
    metrics: list[Metric] = field(default_factory=list)
    index: int = -1
    username: str = ""
    token: str = ""
    user_id: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def add(self, metric: Metric) -> None:
        self.metrics.append(metric)

    @property
    def failed(self) -> list[Metric]:
        return [metric for metric in self.metrics if not metric.ok]


async def timed_request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    name: str,
    **kwargs: Any,
) -> tuple[Metric, httpx.Response | None]:
    started = time.perf_counter()
    try:
        response = await client.request(method, path, **kwargs)
        elapsed_ms = (time.perf_counter() - started) * 1000
        ok = 200 <= response.status_code < 400
        body = response.text[:500] if not ok else ""
        return Metric(name=name, ok=ok, elapsed_ms=elapsed_ms, status_code=response.status_code, body=body), response
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return Metric(name=name, ok=False, elapsed_ms=elapsed_ms, error=str(exc)), None


async def register_or_login(
    client: httpx.AsyncClient,
    username: str,
    password: str,
    headers: dict[str, str],
) -> tuple[dict[str, Any], list[Metric]]:
    metrics: list[Metric] = []
    metric, response = await timed_request(
        client,
        "POST",
        "/auth/register",
        name="auth.register",
        headers=headers,
        json={"username": username, "password": password, "display_name": username},
    )
    if response and response.status_code == 409:
        metric.ok = True
        metric.name = "auth.register_existing"
    metrics.append(metric)
    if response and response.status_code == 409:
        metric, response = await timed_request(
            client,
            "POST",
            "/auth/login",
            name="auth.login",
            headers=headers,
            json={"username": username, "password": password},
        )
        metrics.append(metric)

    if not response or response.status_code >= 400:
        return {}, metrics
    return response.json(), metrics


async def user_flow(
    base_url: str,
    index: int,
    password: str,
    username_prefix: str,
    forwarded_for_prefix: str,
    trust_env: bool,
    sem: asyncio.Semaphore,
) -> RunResult:
    result = RunResult(index=index)
    timeout = httpx.Timeout(20.0, connect=5.0)
    async with sem:
        async with httpx.AsyncClient(base_url=base_url, timeout=timeout, trust_env=trust_env) as client:
            username = f"{username_prefix}_{index:03d}"
            base_headers = {}
            if forwarded_for_prefix:
                base_headers["X-Forwarded-For"] = f"{forwarded_for_prefix}{index + 1}"
            auth_payload, metrics = await register_or_login(client, username, password, base_headers)
            for metric in metrics:
                result.add(metric)
            token = auth_payload.get("token", "")
            if not token:
                return result

            headers = {"Authorization": f"Bearer {token}", **base_headers}
            result.username = username
            result.token = token
            result.user_id = auth_payload.get("user_id", "")
            result.headers = headers
            for name, method, path in (
                ("auth.me", "GET", "/auth/me"),
                ("game.sessions", "GET", "/game/sessions"),
                ("ready", "GET", "/ready"),
            ):
                metric, _ = await timed_request(client, method, path, name=name, headers=headers)
                result.add(metric)
    return result


def create_smoke_module(db_path: Path) -> str:
    """Insert a parsed smoke-test module without invoking upload/model parsing."""
    module_id = str(uuid.uuid4())
    parsed = {
        "setting": "Closed beta room isolation smoke",
        "tone": "operational test",
        "plot_summary": "Synthetic users are spread across independent rooms.",
        "scenes": [{
            "title": "Isolation Hall",
            "description": "A quiet staging area used only by automated smoke tests.",
        }],
        "npcs": [],
        "monsters": [],
        "magic_items": [],
        "level_min": 1,
        "level_max": 3,
        "recommended_party_size": 4,
    }
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO modules (
                id, user_id, name, file_path, file_type, parsed_content,
                level_min, level_max, recommended_party_size, parse_status, parse_error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                module_id,
                None,
                f"LoadSmoke-{module_id[:8]}",
                "",
                "md",
                json.dumps(parsed, ensure_ascii=False),
                1,
                3,
                4,
                "done",
                None,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return module_id


def validation_metric(name: str, ok: bool, detail: str = "") -> Metric:
    return Metric(name=name, ok=ok, elapsed_ms=0.0, error="" if ok else detail)


async def run_room_group(
    *,
    base_url: str,
    group_index: int,
    users: list[RunResult],
    module_id: str,
    room_size: int,
    trust_env: bool,
) -> RunResult:
    result = RunResult(index=group_index)
    if not users:
        return result

    timeout = httpx.Timeout(30.0, connect=5.0)
    host = users[0]
    expected_user_ids = {user.user_id for user in users}
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout, trust_env=trust_env) as client:
        create_metric, create_response = await timed_request(
            client,
            "POST",
            "/game/rooms/create",
            name="room.create",
            headers=host.headers,
            json={
                "module_id": module_id,
                "save_name": f"Load Smoke Room {group_index:02d}",
                "max_players": room_size,
            },
        )
        result.add(create_metric)
        if not create_response or create_response.status_code >= 400:
            return result

        room = create_response.json()
        session_id = room.get("session_id", "")
        room_code = room.get("room_code", "")
        result.meta.update({
            "session_id": session_id,
            "room_code": room_code,
            "expected_user_ids": sorted(expected_user_ids),
            "room_size": room_size,
        })
        result.add(validation_metric(
            "room.host",
            room.get("host_user_id") == host.user_id,
            f"group={group_index} expected host {host.user_id}, got {room.get('host_user_id')}",
        ))

        for user in users[1:]:
            join_metric, join_response = await timed_request(
                client,
                "POST",
                "/game/rooms/join",
                name="room.join",
                headers=user.headers,
                json={"room_code": room_code},
            )
            result.add(join_metric)
            if join_response and join_response.status_code < 400:
                join_data = join_response.json()
                joined_ids = {member.get("user_id") for member in join_data.get("members", [])}
                result.add(validation_metric(
                    "room.join_members",
                    expected_user_ids.issuperset(joined_ids) and user.user_id in joined_ids,
                    f"group={group_index} joined ids leaked or missing user: {sorted(joined_ids)}",
                ))

        for user in users:
            get_metric, get_response = await timed_request(
                client,
                "GET",
                f"/game/rooms/{session_id}",
                name="room.get",
                headers=user.headers,
            )
            result.add(get_metric)
            if not get_response or get_response.status_code >= 400:
                continue
            info = get_response.json()
            observed_user_ids = {member.get("user_id") for member in info.get("members", [])}
            result.add(validation_metric(
                "room.isolation",
                observed_user_ids == expected_user_ids,
                f"group={group_index} expected {sorted(expected_user_ids)}, got {sorted(observed_user_ids)}",
            ))
            result.add(validation_metric(
                "room.size_cap",
                len(observed_user_ids) <= room_size and info.get("max_players") == room_size,
                f"group={group_index} members={len(observed_user_ids)} max_players={info.get('max_players')}",
            ))

    return result


async def run_room_isolation(
    *,
    base_url: str,
    user_results: list[RunResult],
    db_path: Path,
    module_id: str,
    room_size: int,
    trust_env: bool,
) -> list[RunResult]:
    eligible = [result for result in user_results if result.token and result.user_id]
    if not eligible:
        return [RunResult(metrics=[validation_metric("room.isolation_setup", False, "no authenticated users")])]

    if not module_id:
        module_id = create_smoke_module(db_path)
    groups = [eligible[i:i + room_size] for i in range(0, len(eligible), room_size)]
    room_results = await asyncio.gather(*[
        run_room_group(
            base_url=base_url,
            group_index=index,
            users=group,
            module_id=module_id,
            room_size=room_size,
            trust_env=trust_env,
        )
        for index, group in enumerate(groups)
    ])

    full_room = next((group for group in groups if len(group) >= room_size), None)
    outsider = next((user for user in eligible if full_room and user.user_id not in {member.user_id for member in full_room}), None)
    if full_room and outsider:
        first_room_result = room_results[0]
        room_code = first_room_result.meta.get("room_code", "")
        session_id = first_room_result.meta.get("session_id", "")
        extra = RunResult(index=len(room_results))
        if room_code and session_id:
            async with httpx.AsyncClient(base_url=base_url, timeout=30.0, trust_env=trust_env) as client:
                full_metric, full_response = await timed_request(
                    client,
                    "POST",
                    "/game/rooms/join",
                    name="room.full_reject",
                    headers=outsider.headers,
                    json={"room_code": room_code},
                )
                full_metric.ok = bool(full_response and full_response.status_code == 409)
                full_metric.error = "" if full_metric.ok else f"expected 409, got {full_metric.status_code}"
                extra.add(full_metric)
                for metric_name, path in (
                    ("room.cross_read_reject", f"/game/rooms/{session_id}"),
                    ("room.cross_members_reject", f"/game/rooms/{session_id}/members"),
                    ("session.cross_read_reject", f"/game/sessions/{session_id}"),
                ):
                    cross_metric, cross_response = await timed_request(
                        client,
                        "GET",
                        path,
                        name=metric_name,
                        headers=outsider.headers,
                    )
                    cross_metric.ok = bool(cross_response and cross_response.status_code == 403)
                    cross_metric.error = "" if cross_metric.ok else f"expected 403, got {cross_metric.status_code}"
                    extra.add(cross_metric)
        else:
            extra.add(validation_metric("room.full_reject", False, "could not find full room code"))
        room_results.append(extra)

    expected_rooms = math.ceil(len(eligible) / room_size)
    summary = RunResult(index=len(room_results) + 1)
    summary.add(validation_metric(
        "room.expected_count",
        len(groups) == expected_rooms,
        f"expected {expected_rooms} rooms, got {len(groups)}",
    ))
    room_results.append(summary)
    return room_results


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))
    return ordered[index]


def print_summary(results: list[RunResult]) -> int:
    metrics = [metric for result in results for metric in result.metrics]
    failed = [metric for metric in metrics if not metric.ok]
    by_name: dict[str, list[Metric]] = {}
    for metric in metrics:
        by_name.setdefault(metric.name, []).append(metric)

    print(f"requests={len(metrics)} failures={len(failed)}")
    for name in sorted(by_name):
        group = by_name[name]
        latencies = [metric.elapsed_ms for metric in group]
        statuses = sorted({metric.status_code for metric in group if metric.status_code is not None})
        print(
            f"{name}: count={len(group)} ok={sum(1 for metric in group if metric.ok)} "
            f"p50={statistics.median(latencies):.1f}ms p95={percentile(latencies, 95):.1f}ms "
            f"max={max(latencies):.1f}ms statuses={statuses}"
        )

    if failed:
        print("failures:")
        for metric in failed[:20]:
            detail = metric.error or metric.body
            print(f"- {metric.name} status={metric.status_code} elapsed={metric.elapsed_ms:.1f}ms error={detail}")
        if len(failed) > 20:
            print(f"... {len(failed) - 20} more")
        return 1
    return 0


async def main_async(args: argparse.Namespace) -> int:
    sem = asyncio.Semaphore(args.concurrency)
    started = time.perf_counter()
    results = await asyncio.gather(*[
        user_flow(
            args.base_url.rstrip("/"),
            index,
            args.password,
            args.username_prefix,
            args.forwarded_for_prefix,
            args.trust_env,
            sem,
        )
        for index in range(args.users)
    ])
    if args.room_isolation:
        room_results = await run_room_isolation(
            base_url=args.base_url.rstrip("/"),
            user_results=results,
            db_path=Path(args.db_path),
            module_id=args.module_id,
            room_size=args.room_size,
            trust_env=args.trust_env,
        )
        results.extend(room_results)
    elapsed = time.perf_counter() - started
    room_note = f" room_isolation=true room_size={args.room_size}" if args.room_isolation else ""
    print(f"elapsed={elapsed:.2f}s users={args.users} concurrency={args.concurrency}{room_note}")
    return print_summary(results)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a 50-user closed-beta HTTP smoke test.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL.")
    parser.add_argument("--users", type=int, default=50, help="Number of synthetic users.")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent user flows.")
    parser.add_argument("--password", default="password", help="Password for synthetic users.")
    parser.add_argument("--username-prefix", default="load_smoke", help="Synthetic username prefix.")
    parser.add_argument(
        "--forwarded-for-prefix",
        default="",
        help="Optional IP prefix for local multi-user smoke, for example 10.250.0.",
    )
    parser.add_argument(
        "--trust-env",
        action="store_true",
        help="Let httpx use proxy settings from the environment. Disabled by default for localhost smoke.",
    )
    parser.add_argument(
        "--room-isolation",
        action="store_true",
        help="Also create independent multiplayer rooms of up to --room-size users and verify room-member isolation.",
    )
    parser.add_argument(
        "--room-size",
        type=int,
        default=4,
        choices=[2, 3, 4],
        help="Users per synthetic room for --room-isolation. Product baseline is 4.",
    )
    parser.add_argument(
        "--db-path",
        default="backend/ai_trpg.db",
        help="SQLite DB path used to seed a parsed smoke module when --room-isolation is enabled.",
    )
    parser.add_argument(
        "--module-id",
        default="",
        help="Existing module id to use for room creation. If omitted, a parsed smoke module is inserted into --db-path.",
    )
    return parser.parse_args()


def main() -> int:
    return asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
