"""Run Alembic migrations programmatically at startup.

Standalone module shared by every service (bot, miniapp, dashboard) — depends
only on `alembic` and the `alembic/` directory. The first service that boots
brings the shared SQLite forward; subsequent boots are no-ops.

If a deployment was running before Alembic was wired in, we transparently
stamp it at `0001_baseline` first so the existing schema is treated as the
starting point instead of being recreated.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent
_ALEMBIC_INI = _ROOT / "alembic.ini"
_ALEMBIC_DIR = _ROOT / "alembic"
_BASELINE_REV = "0001_baseline"


def _resolve_db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        if url.startswith("postgresql+asyncpg://"):
            return "postgresql+psycopg2://" + url[len("postgresql+asyncpg://"):]
        if url.startswith("sqlite+aiosqlite:///"):
            return "sqlite:///" + url[len("sqlite+aiosqlite:///"):]
        return url
    db_path = os.environ.get("DB_PATH", str(_ROOT / "db.sqlite3"))
    return f"sqlite:///{db_path}"


def _has_table(db_url: str, name: str) -> bool:
    from sqlalchemy import create_engine, inspect
    try:
        eng = create_engine(db_url)
        with eng.connect() as conn:
            return inspect(conn).has_table(name)
    except Exception as exc:
        logger.warning("inspect(%s) failed: %s", name, exc)
        return False


def _apply_sqlite_pragmas(db_url: str) -> None:
    """Local-only ergonomics: when running against SQLite, enable WAL once
    so concurrent reads (e.g. dashboard preview) don't block writers.
    No-op for Postgres."""
    if not db_url.startswith("sqlite"):
        return
    from sqlalchemy import create_engine, text
    eng = create_engine(db_url)
    with eng.begin() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA busy_timeout=5000"))


def upgrade_to_head() -> None:
    if not _ALEMBIC_INI.exists() or not _ALEMBIC_DIR.exists():
        logger.warning(
            "Alembic config missing (ini=%s, dir=%s) — skipping migrations",
            _ALEMBIC_INI, _ALEMBIC_DIR,
        )
        return

    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

    try:
        from alembic import command
        from alembic.config import Config
    except ImportError:
        logger.warning("alembic not installed — skipping migrations")
        return

    cfg = Config()
    cfg.set_main_option("script_location", str(_ALEMBIC_DIR))

    db_url = _resolve_db_url()
    _apply_sqlite_pragmas(db_url)

    needs_baseline_stamp = _has_table(db_url, "users") and not _has_table(
        db_url, "alembic_version"
    )
    if needs_baseline_stamp:
        logger.info("Alembic: stamping pre-existing schema at %s", _BASELINE_REV)
        command.stamp(cfg, _BASELINE_REV)

    logger.info("Alembic: upgrading to head (db=%s)", db_url)
    command.upgrade(cfg, "head")
