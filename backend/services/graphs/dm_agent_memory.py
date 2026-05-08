"""
DM Agent LangGraph checkpoint storage.

This module owns persistent graph memory initialization so dm_agent.py can stay
focused on graph orchestration and node behavior.
"""

from __future__ import annotations

import logging

from config import settings

logger = logging.getLogger(__name__)

_memory_saver = None
_pg_pool = None


async def get_memory_saver():
    """根据配置自动选择 PostgreSQL 或 SQLite 作为 LangGraph 记忆存储。"""
    global _memory_saver, _pg_pool
    if _memory_saver is None:
        if settings.langgraph_db_url:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg_pool import AsyncConnectionPool

            _pg_pool = AsyncConnectionPool(
                conninfo=settings.langgraph_db_url,
                min_size=2,
                max_size=10,
                kwargs={"autocommit": True},
            )
            await _pg_pool.open()
            _memory_saver = AsyncPostgresSaver(conn=_pg_pool)
            await _memory_saver.setup()
            logger.info("LangGraph memory: PostgreSQL (connection pool)")
        else:
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
            import aiosqlite

            conn = await aiosqlite.connect(settings.langgraph_db_path)
            _memory_saver = AsyncSqliteSaver(conn)
            await _memory_saver.setup()
            logger.info("LangGraph memory: SQLite")
    return _memory_saver


async def initialize_memory():
    """Called from main.py lifespan to pre-init the saver."""
    await get_memory_saver()
