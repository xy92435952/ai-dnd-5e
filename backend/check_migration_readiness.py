"""CLI wrapper for the SQLite -> PostgreSQL migration readiness check."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from config import settings
from database import Base
import models  # noqa: F401  ensure all ORM models are registered
from services.migration_readiness import (
    check_sqlite_to_postgres_readiness,
    format_readiness_report,
)


BACKEND_DIR = Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check whether a local SQLite database is ready to migrate to PostgreSQL.",
    )
    parser.add_argument(
        "--sqlite-path",
        default=str(BACKEND_DIR / "ai_trpg.db"),
        help="Path to the source SQLite database.",
    )
    parser.add_argument(
        "--target-url",
        default=settings.database_url,
        help="Target PostgreSQL SQLAlchemy URL. Defaults to DATABASE_URL.",
    )
    parser.add_argument(
        "--alembic-versions-dir",
        default=str(BACKEND_DIR / "alembic" / "versions"),
        help="Path to Alembic version files.",
    )
    args = parser.parse_args(argv)

    report = check_sqlite_to_postgres_readiness(
        sqlite_path=args.sqlite_path,
        target_database_url=args.target_url,
        metadata=Base.metadata,
        alembic_versions_dir=args.alembic_versions_dir,
    )
    print(format_readiness_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
