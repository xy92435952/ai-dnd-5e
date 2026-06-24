"""Seed a repeatable production-like scenario for local smoke tests."""

from __future__ import annotations

import argparse
import asyncio
import json

from database import AsyncSessionLocal, init_db
import models  # noqa: F401  ensure metadata is registered before init_db
from services.smoke_scenario_seed import seed_smoke_scenario


async def _run(slug: str, password: str, variant: str, username: str | None = None) -> dict:
    await init_db()
    async with AsyncSessionLocal() as db:
        result = await seed_smoke_scenario(
            db,
            slug=slug,
            password=password,
            variant=variant,
            username=username,
        )
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
    parser.add_argument(
        "--variant",
        default="standard",
        choices=["standard", "death-save", "reaction", "feather-fall", "stage7-5"],
        help="Optional combat state variant for focused manual QA.",
    )
    parser.add_argument(
        "--username",
        default=None,
        help=(
            "Optional existing or new username to own the seeded smoke session. "
            "When set, the password is reset to --password for that user."
        ),
    )
    args = parser.parse_args()

    result = asyncio.run(_run(args.slug, args.password, args.variant, args.username))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
