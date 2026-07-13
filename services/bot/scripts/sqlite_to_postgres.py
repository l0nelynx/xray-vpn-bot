import logging
import os
import sys
from decimal import Decimal # Обязательно добавляем

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
    # 1. Тракнуем таблицы в Postgres
    if dst.dialect.name == "postgresql":
        targets = [t.name for t in dst_meta.sorted_tables if t.name not in SKIP]
        if targets:
            quoted = ", ".join(f'"{n}"' for n in targets)
            log.info("truncating %d tables", len(targets))
            dst_conn.execute(sa.text(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE"))

    # 2. Перенос данных
    for table in dst_meta.sorted_tables:
        if table.name in SKIP:
            continue
        if table.name not in src_meta.tables:
            log.warning("table %s not in source — skipping", table.name)
            continue

        # Читаем через sa.text(), чтобы избежать TypeError: must be real number, not str
        # Это отключает автоматические процессоры типов SQLAlchemy для источника
        raw_rows = list(src_conn.execute(sa.text(f"SELECT * FROM {table.name}")).mappings())
        
        if not raw_rows:
            log.info("%s: empty", table.name)
            continue
        
        log.info("%s: copying %d rows", table.name, len(raw_rows))

        # Определяем типы колонок для ручной коррекции
        bool_cols = [c.name for c in table.columns if isinstance(c.type, sa.Boolean)]
        # В SQLAlchemy Numeric и Float покрывают все дробные типы
        num_cols = [c.name for c in table.columns if isinstance(c.type, (sa.Numeric, sa.Float))]

        rows: list[dict] = []
        for r in raw_rows:
            row = dict(r)
            
            # Чиним Booleans (SQLite 0/1 -> Python True/False)
            for c in bool_cols:
                if c in row and row[c] is not None:
                    row[c] = bool(row[c])
            
            # Чиним Decimals (String/Float -> Python Decimal)
            for c in num_cols:
                if c in row and row[c] is not None:
                    try:
                        # Принудительно в Decimal через строку для точности
                        row[c] = Decimal(str(row[c]))
                    except Exception:
                        pass
            
            rows.append(row)

        dst_conn.execute(table.insert(), rows)

    # 3. Обновляем сиквенсы
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