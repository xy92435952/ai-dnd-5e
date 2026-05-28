import sqlite3
from pathlib import Path

from sqlalchemy import create_engine

from database import Base
import models  # noqa: F401  ensure all ORM models are registered
from services.migration_readiness import (
    check_sqlite_to_postgres_readiness,
    format_readiness_report,
)


POSTGRES_URL = "postgresql+asyncpg://user:secret@localhost:5432/ai_trpg"
BACKEND_DIR = Path(__file__).resolve().parents[2]


def _create_model_sqlite(path: Path) -> None:
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()


def test_complete_sqlite_schema_is_ready_for_postgres(tmp_path):
    sqlite_path = tmp_path / "ready.db"
    _create_model_sqlite(sqlite_path)

    report = check_sqlite_to_postgres_readiness(
        sqlite_path=sqlite_path,
        target_database_url=POSTGRES_URL,
        metadata=Base.metadata,
        alembic_versions_dir=BACKEND_DIR / "alembic" / "versions",
    )

    assert report.ok is True
    assert report.issues == ()
    assert "secret" not in report.target_url


def test_sqlite_target_url_is_not_ready(tmp_path):
    sqlite_path = tmp_path / "ready.db"
    _create_model_sqlite(sqlite_path)

    report = check_sqlite_to_postgres_readiness(
        sqlite_path=sqlite_path,
        target_database_url="sqlite+aiosqlite:///./ai_trpg.db",
        metadata=Base.metadata,
    )

    assert report.ok is False
    assert {issue.code for issue in report.issues} == {"target_not_postgres"}


def test_missing_tables_and_columns_are_reported(tmp_path):
    sqlite_path = tmp_path / "old.db"
    conn = sqlite3.connect(sqlite_path)
    conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, module_id TEXT NOT NULL)")
    conn.commit()
    conn.close()

    report = check_sqlite_to_postgres_readiness(
        sqlite_path=sqlite_path,
        target_database_url=POSTGRES_URL,
        metadata=Base.metadata,
    )

    codes = {issue.code for issue in report.issues}
    assert report.ok is False
    assert "missing_table" in codes
    assert "missing_column" in codes
    assert any("sessions.game_state" in issue.message for issue in report.issues)


def test_invalid_sqlite_json_is_reported(tmp_path):
    sqlite_path = tmp_path / "bad-json.db"
    _create_model_sqlite(sqlite_path)
    conn = sqlite3.connect(sqlite_path)
    conn.execute(
        (
            "INSERT INTO sessions "
            "(id, module_id, is_multiplayer, max_players, game_state) "
            "VALUES (?, ?, ?, ?, ?)"
        ),
        ("session-1", "module-1", 0, 4, "{bad json"),
    )
    conn.commit()
    conn.close()

    report = check_sqlite_to_postgres_readiness(
        sqlite_path=sqlite_path,
        target_database_url=POSTGRES_URL,
        metadata=Base.metadata,
    )

    assert report.ok is False
    assert any(issue.code == "invalid_json" for issue in report.issues)


def test_alembic_multiple_heads_are_reported(tmp_path):
    versions_dir = tmp_path / "versions"
    versions_dir.mkdir()
    (versions_dir / "a.py").write_text(
        'revision = "a"\ndown_revision = None\n',
        encoding="utf-8",
    )
    (versions_dir / "b.py").write_text(
        'revision = "b"\ndown_revision = "a"\n',
        encoding="utf-8",
    )
    (versions_dir / "c.py").write_text(
        'revision = "c"\ndown_revision = "a"\n',
        encoding="utf-8",
    )
    sqlite_path = tmp_path / "ready.db"
    _create_model_sqlite(sqlite_path)

    report = check_sqlite_to_postgres_readiness(
        sqlite_path=sqlite_path,
        target_database_url=POSTGRES_URL,
        metadata=Base.metadata,
        alembic_versions_dir=versions_dir,
    )

    assert report.ok is False
    assert any(issue.code == "alembic_head_count" for issue in report.issues)


def test_format_readiness_report_lists_errors(tmp_path):
    report = check_sqlite_to_postgres_readiness(
        sqlite_path=tmp_path / "missing.db",
        target_database_url="sqlite:///local.db",
        metadata=Base.metadata,
    )

    text = format_readiness_report(report)

    assert "NOT READY" in text
    assert "target_not_postgres" in text
    assert "sqlite_missing" in text
