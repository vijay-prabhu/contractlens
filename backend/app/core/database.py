from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.models.base import Base

settings = get_settings()

# Convert postgresql:// to postgresql+psycopg:// for async support with psycopg3
# psycopg3 handles pgbouncer/transaction pooling better than asyncpg
DATABASE_URL = settings.database_url.replace(
    "postgresql://", "postgresql+psycopg://"
)

# Create async engine
# Using NullPool for serverless environments (Supabase)
engine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
    poolclass=NullPool,
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
