"""Closed-beta 50-user smoke test.

This script exercises low-risk authenticated HTTP paths concurrently. It does
not call the DM model by default, so it can be used before expensive gameplay
load tests. Run against a disposable or beta test environment.

Example:
    python scripts/load_smoke_50.py --base-url http://127.0.0.1:8000 --users 50
"""
from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass, field
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
) -> tuple[str, list[Metric]]:
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
        return "", metrics
    return response.json().get("token", ""), metrics


async def user_flow(
    base_url: str,
    index: int,
    password: str,
    username_prefix: str,
    forwarded_for_prefix: str,
    trust_env: bool,
    sem: asyncio.Semaphore,
) -> RunResult:
    result = RunResult()
    timeout = httpx.Timeout(20.0, connect=5.0)
    async with sem:
        async with httpx.AsyncClient(base_url=base_url, timeout=timeout, trust_env=trust_env) as client:
            username = f"{username_prefix}_{index:03d}"
            base_headers = {}
            if forwarded_for_prefix:
                base_headers["X-Forwarded-For"] = f"{forwarded_for_prefix}{index + 1}"
            token, metrics = await register_or_login(client, username, password, base_headers)
            for metric in metrics:
                result.add(metric)
            if not token:
                return result

            headers = {"Authorization": f"Bearer {token}", **base_headers}
            for name, method, path in (
                ("auth.me", "GET", "/auth/me"),
                ("game.sessions", "GET", "/game/sessions"),
                ("ready", "GET", "/ready"),
            ):
                metric, _ = await timed_request(client, method, path, name=name, headers=headers)
                result.add(metric)
    return result


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
    elapsed = time.perf_counter() - started
    print(f"elapsed={elapsed:.2f}s users={args.users} concurrency={args.concurrency}")
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
    return parser.parse_args()


def main() -> int:
    return asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
