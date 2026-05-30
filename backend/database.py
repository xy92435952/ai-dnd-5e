import logging

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import inspect, text
from config import settings

logger = logging.getLogger(__name__)

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
        await _ensure_compat_schema(conn)
        if _is_sqlite:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA busy_timeout=30000"))


async def _ensure_compat_schema(conn) -> None:
    """Apply tiny idempotent schema patches for older deployed databases."""
    game_log_columns = await conn.run_sync(_table_columns, "game_logs")
    missing_game_log_columns = {
        "visibility": "JSON",
        "table_reason": "TEXT",
        "table_decision": "JSON",
    }
    for column_name, column_type in missing_game_log_columns.items():
        if column_name in game_log_columns:
            continue
        await _add_column_if_missing(conn, "game_logs", column_name, column_type)


def _table_columns(sync_conn, table_name: str) -> set[str]:
    inspector = inspect(sync_conn)
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


async def _add_column_if_missing(conn, table_name: str, column_name: str, column_type: str) -> None:
    dialect = conn.dialect.name
    if dialect == "postgresql":
        stmt = f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_name} {column_type}"
    else:
        stmt = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
    try:
        await conn.execute(text(stmt))
        logger.info("Schema compatibility patch applied: %s.%s", table_name, column_name)
    except Exception as exc:
        # Multiple workers may race during startup; a duplicate-column failure is harmless
        # after another worker has already applied the same compatibility patch.
        logger.warning(
            "Schema compatibility patch skipped for %s.%s: %s",
            table_name,
            column_name,
            exc,
        )
