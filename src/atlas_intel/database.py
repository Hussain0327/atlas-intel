"""Async SQLAlchemy engine and session management."""

import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from atlas_intel.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=settings.db_pool_recycle,
    connect_args={"command_timeout": settings.db_command_timeout},
)

async_session = async_sessionmaker(engine, expire_on_commit=False)


# Slow query logging on the sync engine (underlying pool)
@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _before_cursor_execute(
    conn: Any,
    cursor: Any,
    statement: Any,
    parameters: Any,
    context: Any,
    executemany: Any,
) -> None:
    conn.info["query_start_time"] = time.perf_counter()


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def _after_cursor_execute(
    conn: Any,
    cursor: Any,
    statement: Any,
    parameters: Any,
    context: Any,
    executemany: Any,
) -> None:
    start = conn.info.pop("query_start_time", None)
    if start is not None:
        elapsed = time.perf_counter() - start
        if elapsed > 1.0:
            logger.warning(
                "Slow query (%.1fs): %.200s",
                elapsed,
                statement,
            )


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
