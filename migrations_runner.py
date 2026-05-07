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


def _resolve_db_path() -> str:
    return os.environ.get("DB_PATH", str(_ROOT / "db.sqlite3"))


def _has_table(db_path: str, name: str) -> bool:
    import sqlite3

    if not os.path.exists(db_path):
        return False
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
    return row is not None


def upgrade_to_head() -> None:
    if not _ALEMBIC_INI.exists() or not _ALEMBIC_DIR.exists():
        logger.warning(
            "Alembic config missing (ini=%s, dir=%s) — skipping migrations",
            _ALEMBIC_INI,
            _ALEMBIC_DIR,
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

    # Alembic при `Config(ini_path)` дёргает logging.config.fileConfig()
    # с дефолтным `disable_existing_loggers=True`, который ВЫРУБАЕТ все
    # ранее созданные логгеры (включая `backend.*`). Создаём Config БЕЗ
    # ini-файла — секция script_location всё, что нам нужно из него,
    # а sqlalchemy.url alembic/env.py строит сам из DB_PATH.
    cfg = Config()
    cfg.set_main_option("script_location", str(_ALEMBIC_DIR))

    db_path = _resolve_db_path()
    needs_baseline_stamp = _has_table(db_path, "users") and not _has_table(
        db_path, "alembic_version"
    )

    if needs_baseline_stamp:
        logger.info("Alembic: stamping pre-existing schema at %s", _BASELINE_REV)
        command.stamp(cfg, _BASELINE_REV)

    logger.info("Alembic: upgrading to head (db=%s)", db_path)
    command.upgrade(cfg, "head")
