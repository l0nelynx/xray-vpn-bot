"""The recovery migration must reserve history without issuing money or notices."""
import importlib.util
import io
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from common_db.models.referral_recovery import ReferralReceipt, ReferralRecovery, ReferralNotice


def migration(operations):
    path = Path(__file__).resolve().parents[1] / "alembic/versions/0044_referral_recovery.py"
    spec = importlib.util.spec_from_file_location("referral_migration_checked", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = operations
    return module


@pytest.mark.parametrize("dialect", ["postgresql", "sqlite"])
def test_offline_sql_includes_history_reservation(dialect):
    output = io.StringIO()
    context = MigrationContext.configure(dialect_name=dialect, opts={
        "as_sql": True, "output_buffer": output, "literal_binds": True,
    })
    migration(Operations(context)).upgrade()
    sql = output.getvalue()
    assert "INSERT INTO referral_receipts" in sql
    assert "FROM transactions" in sql
    assert "INSERT INTO referral_recovery" in sql
    assert "INSERT INTO referral_notices" not in sql
    assert "UPDATE users" not in sql
    assert "credit_ledger" not in sql


@pytest.mark.parametrize("incomplete_table", [False, True])
def test_invalid_source_schema_fails_before_creating_tables(incomplete_table):
    engine = sa.create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            if incomplete_table:
                connection.exec_driver_sql("CREATE TABLE transactions (transaction_id TEXT PRIMARY KEY)")
            with pytest.raises(RuntimeError, match="existing transactions schema"):
                migration(Operations(MigrationContext.configure(connection))).upgrade()
            assert not sa.inspect(connection).has_table("referral_recovery")
            assert not sa.inspect(connection).has_table("referral_receipts")
    finally:
        engine.dispose()


def test_migrated_columns_match_models_and_preserve_original_data():
    engine = sa.create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE transactions (transaction_id VARCHAR(100) PRIMARY KEY, delivery_status INTEGER, order_status VARCHAR(50), payment_method VARCHAR(50))")
            connection.exec_driver_sql("CREATE TABLE users (id BIGINT PRIMARY KEY, bonus_credits INTEGER)")
            connection.exec_driver_sql("INSERT INTO users VALUES (1, 127)")
            connection.exec_driver_sql("INSERT INTO transactions VALUES ('paid',1,'delivered','CARD'), ('bonus',0,'pending','BONUS_CREDITS'), ('cancelled',1,'cancelled','CARD'), ('created',0,'created','CARD')")
            before = connection.exec_driver_sql("SELECT * FROM transactions ORDER BY transaction_id").all()
            module = migration(Operations(MigrationContext.configure(connection)))
            module.upgrade()
            inspector = sa.inspect(connection)
            for model in (ReferralReceipt, ReferralRecovery, ReferralNotice):
                columns = {c["name"]: c for c in inspector.get_columns(model.__tablename__)}
                assert set(columns) == set(model.__table__.columns.keys())
                for expected in model.__table__.columns:
                    actual = columns[expected.name]
                    assert actual["nullable"] == expected.nullable
                    assert bool(actual["primary_key"]) == expected.primary_key
                    assert actual["type"]._type_affinity == expected.type._type_affinity
            assert connection.exec_driver_sql("SELECT * FROM transactions ORDER BY transaction_id").all() == before
            assert connection.exec_driver_sql("SELECT bonus_credits FROM users").scalar() == 127
            assert set(connection.exec_driver_sql("SELECT transaction_id FROM referral_receipts").scalars()) == {"paid", "bonus"}
            module.downgrade()
            assert connection.exec_driver_sql("SELECT * FROM transactions ORDER BY transaction_id").all() == before
            assert connection.exec_driver_sql("SELECT bonus_credits FROM users").scalar() == 127
    finally:
        engine.dispose()
