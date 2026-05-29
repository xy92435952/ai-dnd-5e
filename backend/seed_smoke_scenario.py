"""Seed a repeatable production-like scenario for local smoke tests."""

from __future__ import annotations

import argparse
import asyncio
import json

from database import AsyncSessionLocal, init_db
import models  # noqa: F401  ensure metadata is registered before init_db
from services.smoke_scenario_seed import seed_smoke_scenario


async def _run(slug: str, password: str) -> dict:
    await init_db()
    async with AsyncSessionLocal() as db:
        result = await seed_smoke_scenario(db, slug=slug, password=password)
        return result.as_dict()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed a deterministic module, party, session and combat for smoke tests.",
    )
    parser.add_argument("--slug", default="codex_smoke", help="Stable seed namespace.")
    parser.add_argument(
        "--password",
        default="smoke-password",
        help="Password for the seeded login user.",
    )
    args = parser.parse_args()

    result = asyncio.run(_run(args.slug, args.password))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
