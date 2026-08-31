"""Database setup with SQLAlchemy async."""

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings


def _connect_args() -> dict:
    url = settings.database_url
    if "sqlite" in url:
        return {"check_same_thread": False}
    if getattr(settings, "db_require_ssl", False):
        # asyncpg wants an ``ssl`` arg, not libpq's ``sslmode`` query param.
        return {"ssl": True}
    return {}


engine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,
    connect_args=_connect_args(),
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


def _reconcile_columns(sync_conn) -> list[str]:
    """Add any model column missing from an already-created table.

    ``create_all`` never ``ALTER``s existing tables, so a column added to a model
    after its table was first deployed is silently absent until now. This diffs
    each mapped table against the live schema and issues additive-only
    ``ALTER TABLE ... ADD COLUMN`` statements. It never drops or retypes columns.

    New columns are added **nullable** even when the model marks them
    ``nullable=False`` and gives no ``server_default`` — Postgres rejects adding a
    NOT NULL column to a populated table, and the ORM's client-side ``default=``
    keeps freshly-inserted rows populated regardless.
    """
    inspector = inspect(sync_conn)
    dialect = sync_conn.dialect
    is_sqlite = dialect.name == "sqlite"
    applied: list[str] = []

    existing_tables = set(inspector.get_table_names())

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # create_all just made it — fully in sync
        live_cols = {c["name"] for c in inspector.get_columns(table.name)}

        for col in table.columns:
            if col.name in live_cols:
                continue

            ddl = f'"{col.name}" {col.type.compile(dialect=dialect)}'

            # A server_default lets the new column populate existing rows. Skip it
            # on SQLite, which only accepts a constant default in ADD COLUMN.
            if col.server_default is not None and not is_sqlite:
                default_arg = getattr(col.server_default, "arg", None)
                if isinstance(default_arg, str):
                    ddl += f" DEFAULT {default_arg}"
                elif default_arg is not None and hasattr(default_arg, "compile"):
                    try:
                        ddl += f" DEFAULT {default_arg.compile(dialect=dialect, compile_kwargs={'literal_binds': True})}"
                    except Exception:
                        pass

            if is_sqlite:
                stmt = f'ALTER TABLE "{table.name}" ADD COLUMN {ddl}'
            else:
                stmt = f'ALTER TABLE "{table.name}" ADD COLUMN IF NOT EXISTS {ddl}'

            sync_conn.exec_driver_sql(stmt)
            applied.append(f"{table.name}.{col.name}")

    return applied


async def init_db():
    """Create all tables, then reconcile any columns added to models later."""
    from backend.models import wine, location, user, community  # noqa: F401 — register models

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        applied = await conn.run_sync(_reconcile_columns)

    for name in applied:
        print(f"[migrate] added column {name}")
