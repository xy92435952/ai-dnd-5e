from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite:
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        connect_args={"timeout": 30},
    )
else:
    # PostgreSQL — 连接池配置
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
    )

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if _is_sqlite:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA busy_timeout=30000"))
            await _ensure_sqlite_compat_columns(conn)


async def _ensure_sqlite_compat_columns(conn) -> None:
    """Patch local SQLite dev databases that predate recent Alembic columns.

    `create_all()` creates missing tables but does not alter existing tables.
    Local beta databases may therefore miss columns added by Alembic and fail
    at runtime before a developer has run `alembic upgrade head`.
    """
    await _ensure_sqlite_table_columns(
        conn,
        "game_logs",
        {
            "visibility": "JSON",
            "table_reason": "TEXT",
            "table_decision": "JSON",
        },
    )


async def _ensure_sqlite_table_columns(conn, table_name: str, columns: dict[str, str]) -> None:
    existing = await conn.execute(text(f"PRAGMA table_info({table_name})"))
    existing_names = {row[1] for row in existing.fetchall()}
    if not existing_names:
        return
    for column_name, column_type in columns.items():
        if column_name not in existing_names:
            await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
