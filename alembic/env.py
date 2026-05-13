"""Alembic environment.

Uses sync sqlite for migrations (alembic does not need async). The DB path
is read from the same DB_PATH env var the runtime uses, so dev/prod both
work without editing alembic.ini.
"""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _resolve_db_url() -> str:
    x_args = context.get_x_argument(as_dictionary=True)
    if "dburl" in x_args:
        return x_args["dburl"]
    url = os.environ.get("DATABASE_URL")
    if url:
        # alembic uses sync drivers — coerce asyncpg → psycopg2
        if url.startswith("postgresql+asyncpg://"):
            return "postgresql+psycopg2://" + url[len("postgresql+asyncpg://"):]
        if url.startswith("sqlite+aiosqlite:///"):
            return "sqlite:///" + url[len("sqlite+aiosqlite:///"):]
        return url
    db_path = os.environ.get("DB_PATH", str(ROOT / "db.sqlite3"))
    return f"sqlite:///{db_path}"


# target_metadata is only needed for `alembic revision --autogenerate`, which
# is run from the bot container (where app.database.models is importable).
# Keeping the import lazy lets miniapp/dashboard run migrations without
# pulling in aiogram-side modules.
try:
    from app.database import models as app_models  # noqa: E402
    target_metadata = app_models.Base.metadata
except Exception:
    target_metadata = None


def run_migrations_offline() -> None:
    context.configure(
        url=_resolve_db_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_resolve_db_url().startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg_section = config.get_section(config.config_ini_section) or {}
    cfg_section["sqlalchemy.url"] = _resolve_db_url()
    connectable = engine_from_config(
        cfg_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=_resolve_db_url().startswith("sqlite"),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
