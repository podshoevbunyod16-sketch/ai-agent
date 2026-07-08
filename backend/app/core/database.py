"""
Async database layer using SQLAlchemy.
Auto-detects SQLite (local) vs PostgreSQL (Render) from DATABASE_URL.
"""
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from app.core.config import settings

# --- Engine creation ---
# IMPORTANT: create_async_engine needs an ASYNC driver in the URL.
# Render's DATABASE_URL comes as plain 'postgresql://...' (sync/psycopg2 dialect),
# so we always go through settings.async_database_url, which rewrites it to
# 'postgresql+asyncpg://...' when needed. SQLite passes through untouched.
if settings.is_postgres:
    # PostgreSQL on Render
    async_engine = create_async_engine(
        settings.async_database_url,
        poolclass=NullPool,
        echo=False,
    )
else:
    # SQLite locally
    async_engine = create_async_engine(
        settings.async_database_url,
        echo=False,
        connect_args={"check_same_thread": False},
    )

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db() -> AsyncSession:
    """FastAPI dependency: yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all tables on startup (development convenience).
    On production use `alembic upgrade head`."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
