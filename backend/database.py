"""Database setup with SQLAlchemy async."""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings


engine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


# Columns added after tables may already exist in a deployed DB.
# `create_all` never ALTERs, so patch them in idempotently on startup.
_ADDITIVE_COLUMNS = {
    "locations": [
        ("website", "VARCHAR(500) DEFAULT '' NOT NULL"),
        ("description", "TEXT DEFAULT '' NOT NULL"),
        ("phone", "VARCHAR(50) DEFAULT '' NOT NULL"),
        ("image_url", "VARCHAR(500) DEFAULT '' NOT NULL"),
    ],
}


async def _apply_additive_migrations(conn):
    from sqlalchemy import text

    is_sqlite = "sqlite" in settings.database_url
    for table, columns in _ADDITIVE_COLUMNS.items():
        for name, ddl in columns:
            if is_sqlite:
                # SQLite has no ADD COLUMN IF NOT EXISTS — probe first.
                cols = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
                if any(row[1] == name for row in cols.fetchall()):
                    continue
                await conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
            else:
                await conn.exec_driver_sql(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {ddl}"
                )


async def init_db():
    """Create all tables, then apply additive column migrations."""
    from backend.models import wine, location, user, community, spirit  # noqa: F401 — register models

    async with engine.begin() as conn:
        # Enable WAL mode for concurrent read/write
        if "sqlite" in settings.database_url:
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            await conn.exec_driver_sql("PRAGMA busy_timeout=5000")
        await conn.run_sync(Base.metadata.create_all)
        await _apply_additive_migrations(conn)