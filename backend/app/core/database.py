from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool

from app.core.config import get_settings
from app.models.base import Base

settings = get_settings()

# Convert postgresql:// to postgresql+psycopg:// for async support with psycopg3
# psycopg3 handles pgbouncer/transaction pooling better than asyncpg
DATABASE_URL = settings.database_url.replace(
    "postgresql://", "postgresql+psycopg://"
)

# Create async engine with proper pool configuration
# - pool_size: Number of connections to keep in pool
# - max_overflow: Max additional connections beyond pool_size
# - pool_timeout: Seconds to wait for connection before timeout
# - pool_recycle: Recycle connections after N seconds (Supabase idle timeout)
# - pool_pre_ping: Test connections before use (handles stale connections)
# - prepare_threshold=None: Disable prepared statements for pgbouncer compatibility
engine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
    poolclass=AsyncAdaptedQueuePool,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=300,  # 5 minutes - before Supabase 60s idle timeout
    pool_pre_ping=True,
    connect_args={
        "prepare_threshold": None,
        "connect_timeout": 10,
    },
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions.

    Ensures proper transaction cleanup for Supabase Transaction Pooler.
    """
    async with async_session_maker() as session:
        try:
            yield session
            # Commit any pending changes
            await session.commit()
        except Exception:
            # Rollback on error
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
