"""Async SQLAlchemy engine helpers."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def create_database_engine(database_url: str) -> AsyncEngine:
    """Create the shared async database engine."""

    return create_async_engine(database_url, pool_pre_ping=True)


async def check_database_connection(engine: AsyncEngine) -> None:
    """Fail process startup unless the configured database accepts a connection."""

    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
