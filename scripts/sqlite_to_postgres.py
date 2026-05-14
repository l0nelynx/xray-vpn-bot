"""One-shot migrator: copy every row from a SQLite snapshot into a fresh
Postgres database whose schema has already been brought to `head` via
alembic.

Usage:
  SQLITE_PATH=/path/to/db.sqlite3 \
  DATABASE_URL='postgresql+psycopg2://user:pw@host/db' \
    python scripts/sqlite_to_postgres.py

Strategy:
- Reflect table list from Postgres (source of truth for schema).
- Skip `alembic_version` (already populated by migrations).
- Migrate in FK-aware order via `sa.MetaData.sorted_tables`.
- Before insert, TRUNCATE every target table (RESTART IDENTITY CASCADE).
  This wipes Alembic-seeded rows like `promo_settings(id=1)` that would
  otherwise collide with the SQLite copy.
- After every table, advance the sequence for SERIAL PKs to `max(id) + 1`,
  otherwise the next INSERT collides.
- Idempotency: re-runs are safe (truncate wipes prior copy).
"""
from __future__ import annotations

import logging
import os
import sys

import sqlalchemy as sa

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("migrator")

SQLITE_PATH = os.environ["SQLITE_PATH"]
DATABASE_URL = os.environ["DATABASE_URL"]

if "asyncpg" in DATABASE_URL:
    sys.exit("Use a sync DATABASE_URL (postgresql+psycopg2://...), not asyncpg.")

src = sa.create_engine(f"sqlite:///{SQLITE_PATH}")
dst = sa.create_engine(DATABASE_URL)

src_meta = sa.MetaData()
src_meta.reflect(bind=src)
dst_meta = sa.MetaData()
dst_meta.reflect(bind=dst)

SKIP = {"alembic_version", "sqlite_sequence"}

with src.connect() as src_conn, dst.begin() as dst_conn:
    if dst.dialect.name == "postgresql":
        targets = [t.name for t in dst_meta.sorted_tables if t.name not in SKIP]
        if targets:
            quoted = ", ".join(f'"{n}"' for n in targets)
            log.info("truncating %d tables (RESTART IDENTITY CASCADE)", len(targets))
            dst_conn.execute(sa.text(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE"))

    for table in dst_meta.sorted_tables:
        if table.name in SKIP:
            continue
        if table.name not in src_meta.tables:
            log.warning("table %s not in source — skipping", table.name)
            continue

        src_table = src_meta.tables[table.name]
        raw_rows = list(src_conn.execute(sa.select(src_table)).mappings())
        if not raw_rows:
            log.info("%s: empty", table.name)
            continue
        log.info("%s: copying %d rows", table.name, len(raw_rows))

        bool_cols = [c.name for c in table.columns if isinstance(c.type, sa.Boolean)]
        rows: list[dict] = []
        for r in raw_rows:
            row = dict(r)
            for c in bool_cols:
                if c in row and row[c] is not None:
                    row[c] = bool(row[c])
            rows.append(row)

        dst_conn.execute(table.insert(), rows)

    if dst.dialect.name == "postgresql":
        for table in dst_meta.sorted_tables:
            if table.name in SKIP:
                continue
            pk_cols = [c for c in table.primary_key.columns if isinstance(c.type, sa.Integer)]
            if not pk_cols:
                continue
            pk = pk_cols[0]
            seq_q = sa.text(
                f"SELECT setval(pg_get_serial_sequence('{table.name}', '{pk.name}'),"
                f" COALESCE((SELECT MAX({pk.name}) FROM {table.name}), 1))"
            )
            dst_conn.execute(seq_q)
            log.info("%s: sequence advanced", table.name)

log.info("done")
