"""
Async database connection pool — Customer Success Digital FTE
"""
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from .models import Base


# ---------------------------------------------------------------------------
# Engine factory
# ---------------------------------------------------------------------------

def _build_database_url() -> str:
    """Build async PostgreSQL URL from environment variables."""
    url = os.environ.get("DATABASE_URL")
    if url:
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        # Strip incompatible parameters for asyncpg
        if "?" in url:
            base, query = url.split("?", 1)
            params = [p for p in query.split("&") if not p.startswith(("sslmode=", "channel_binding="))]
            url = f"{base}?{'&'.join(params)}" if params else base
        return url

    # Fallback to individual components (deprecated)
    user = os.environ.get('DB_USER', 'postgres')
    pw = os.environ.get('DB_PASSWORD', '')
    host = os.environ.get('DB_HOST', 'localhost')
    port = os.environ.get('DB_PORT', '5432')
    name = os.environ.get('DB_NAME', 'postgres')
    return f"postgresql+asyncpg://{user}:{pw}@{host}:{port}/{name}"


def create_engine(url: str | None = None, *, testing: bool = False) -> AsyncEngine:
    """Create SQLAlchemy async engine with optimised connection pool."""
    database_url = url or _build_database_url()
    kwargs: dict = {
        "echo": os.environ.get("DB_ECHO", "false").lower() == "true",
        "future": True,
    }

    # Handle SSL for Neon PostgreSQL
    if "neon.tech" in database_url:
        kwargs["connect_args"] = {"ssl": True}

    if testing:
        kwargs["poolclass"] = NullPool
    else:
        kwargs.update(
            {
                "pool_size": int(os.environ.get("DB_POOL_SIZE", "10")),
                "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "20")),
                "pool_timeout": int(os.environ.get("DB_POOL_TIMEOUT", "30")),
                "pool_recycle": int(os.environ.get("DB_POOL_RECYCLE", "1800")),
                "pool_pre_ping": True,
            }
        )
    return create_async_engine(database_url, **kwargs)


# ---------------------------------------------------------------------------
# Module-level singletons (initialised in lifespan)
# ---------------------------------------------------------------------------

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(url: str | None = None, *, testing: bool = False) -> None:
    """Initialise the module-level engine and session factory."""
    global _engine, _session_factory
    _engine = create_engine(url, testing=testing)
    _session_factory = async_sessionmaker(
        _engine, expire_on_commit=False, class_=AsyncSession
    )


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    return _engine


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency-injectable async session context manager."""
    if _session_factory is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all_tables() -> None:
    """Create all tables (used in testing or first-run setup)."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose the engine connection pool gracefully."""
    if _engine:
        await _engine.dispose()
