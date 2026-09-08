import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_existing_conversations_migrate_and_downgrade(monkeypatch):
    path = Path(__file__).parents[3] / "alembic/versions/0041_support_workflow.py"
    spec = importlib.util.spec_from_file_location("support_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE support_tickets (id INTEGER PRIMARY KEY, status VARCHAR(20), created_at VARCHAR(30), updated_at VARCHAR(30))")
        connection.exec_driver_sql("CREATE TABLE support_messages (id INTEGER PRIMARY KEY, ticket_id INTEGER, sender VARCHAR(20), created_at VARCHAR(30))")
        connection.exec_driver_sql("CREATE TABLE support_attachments (id INTEGER PRIMARY KEY, created_at VARCHAR(30))")
        connection.exec_driver_sql("INSERT INTO support_tickets VALUES (1, 'in_progress', '2026-09-01T10:00:00Z', '2026-09-01T14:00:00')")
        connection.exec_driver_sql("INSERT INTO support_messages VALUES (1, 1, 'user', '2026-09-01T10:00:00Z'), (2, 1, 'admin', '2026-09-01T14:00:00')")
        monkeypatch.setenv("SUPPORT_LEGACY_TIMEZONE", "+03:00")
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        row = connection.execute(sa.text("SELECT * FROM support_tickets")).mappings().one()
        assert row["status"] == "waiting_user"
        assert row["updated_at"] == "2026-09-01T11:00:00+00:00"
        assert row["last_admin_message_id"] == 2
        assert row["last_user_message_id"] == 1
        migration.downgrade()
        assert connection.scalar(sa.text("SELECT status FROM support_tickets")) == "in_progress"
    engine.dispose()
