"""Step 6: alembic autogenerate must produce ZERO ops against HEAD.

This is the *real* drift check the structural diff in test_alembic_target.py
could only approximate locally. Given a live Postgres at HEAD, ask alembic's
autogenerate engine to compare it against `common_db.Base.metadata`. If
anything diverges — wrong type, missing column, mismatched server_default,
mis-ordered constraints — autogenerate emits an op, and this test fails
loud and specific.

Why Postgres, not SQLite:
  - The migration history includes Postgres-only `ALTER COLUMN ... TYPE
    BIGINT` and sequence work that SQLite can't apply. The schema canon
    we wrote in common_db is Postgres-shaped (BigInteger PKs, etc.).
  - The whole production system runs on Postgres; that's the only
    schema worth pinning bit-for-bit.

How to run locally:
  $ export COMMON_DB_PG_URL='postgresql+psycopg2://user:pass@host:5432/db'
  $ python -m pytest packages/common_db/tests/test_autogenerate_diff.py -v

If COMMON_DB_PG_URL is unset, the test is skipped. CI sets it via a
docker-compose service so this runs on every PR.

What "zero ops" means:
  The MigrationContext.compare-against-metadata pass returns a list of
  alembic op directives. An empty list = perfect parity. Anything else
  prints the proposed ops and fails. False positives are rare in
  practice (server_default rendering, comment differences) and the
  fix is always to align common_db's model with the migration that
  actually shipped — never the other way around.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


COMMON_DB_PG_URL = os.environ.get("COMMON_DB_PG_URL")


def _require_postgres_url() -> str:
    if not COMMON_DB_PG_URL:
        pytest.skip(
            "COMMON_DB_PG_URL not set — autogenerate diff requires a live Postgres "
            "at HEAD. CI provides this via the postgres service; locally, export it "
            "to run the test."
        )
    if not COMMON_DB_PG_URL.startswith(("postgresql://", "postgresql+psycopg2://")):
        pytest.skip(
            f"COMMON_DB_PG_URL must be a sync postgres URL "
            f"(postgresql:// or postgresql+psycopg2://), got: {COMMON_DB_PG_URL!r}"
        )
    return COMMON_DB_PG_URL


def _repo_root() -> Path:
    # packages/common_db/tests/<this>.py -> parents[3]
    root = Path(__file__).resolve().parents[3]
    if not (root / "alembic.ini").exists():
        pytest.skip(f"alembic.ini not found at {root}")
    return root


def test_autogenerate_produces_no_ops_against_head() -> None:
    """Live Postgres + alembic autogenerate -> common_db metadata = zero ops."""
    url = _require_postgres_url()
    root = _repo_root()

    # Imports are inside the test so the module is collectable even when
    # alembic/sqlalchemy are unavailable in the package's standalone env.
    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine

    import common_db
    import common_db.models  # noqa: F401  populate metadata

    # 1. Bring the DB to HEAD using the project's alembic config.
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    # `command.upgrade` runs in-process; that's fine because alembic builds
    # a separate sync engine internally via env.py.
    from alembic import command
    # Honour env.py's resolution by exporting DATABASE_URL — alembic env.py
    # reads that env var first.
    prev = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        command.upgrade(cfg, "head")
    finally:
        if prev is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prev

    # 2. Run autogenerate's compare-against-metadata pass directly.
    engine = create_engine(url, future=True)
    try:
        with engine.connect() as conn:
            mc = MigrationContext.configure(connection=conn)
            diff = compare_metadata(mc, common_db.Base.metadata)
    finally:
        engine.dispose()

    # 3. Filter: alembic surfaces vestigial tables (e.g. support_users)
    # as `remove_table` ops because they're in the DB but not in the
    # metadata. That's intentional — see test_alembic_target.py — so we
    # drop them from the diff. Everything else must be empty.
    from .test_alembic_target import VESTIGIAL_TABLES

    def _table_name(op) -> str | None:
        # op shapes: ('remove_table', Table) | ('add_table', Table) |
        # ('add_column', schema, table, Column) | ...
        if isinstance(op, tuple) and len(op) >= 2:
            cand = op[1]
            if hasattr(cand, "name"):
                return cand.name
            if isinstance(cand, str):
                return cand
            if len(op) >= 3 and isinstance(op[2], str):
                return op[2]
        return None

    real_ops = [op for op in diff if _table_name(op) not in VESTIGIAL_TABLES]

    assert not real_ops, (
        "alembic autogenerate produced ops against common_db.Base.metadata "
        "— common_db is drifting from the migration head. Fix common_db/models/ "
        "to match the actual migrated schema (NOT the other way around: never "
        "change the test to silence drift).\n\nOps:\n  "
        + "\n  ".join(repr(op) for op in real_ops)
    )
