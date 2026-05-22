import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from database import _ensure_sqlite_compat_columns


async def test_ensure_sqlite_compat_columns_adds_missing_game_log_fields():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE game_logs (
                    id VARCHAR PRIMARY KEY,
                    session_id VARCHAR NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    log_type VARCHAR(20),
                    dice_result JSON,
                    created_at DATETIME
                )
            """))

            await _ensure_sqlite_compat_columns(conn)

            result = await conn.execute(text("PRAGMA table_info(game_logs)"))
            column_names = {row[1] for row in result.fetchall()}

        assert {"visibility", "table_reason", "table_decision"}.issubset(column_names)
    finally:
        await engine.dispose()
