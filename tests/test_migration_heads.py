"""Exercise the real Alembic graph, not only individual upgrade functions."""
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]


def migration_config():
    cfg = Config()
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    return cfg


def test_migrations_have_one_head():
    heads = ScriptDirectory.from_config(migration_config()).get_heads()
    assert len(heads) == 1, f"Startup uses upgrade head; merge these heads: {heads}"


@pytest.mark.parametrize("applied", [
    (),
    ("0041_dashboard_branding_asset",),
    ("0041_support_workflow",),
    ("0041_dashboard_branding_asset", "0041_support_workflow"),
])
def test_startup_upgrades_from_either_branch(tmp_path, monkeypatch, applied):
    from migrations_runner import upgrade_to_head

    url = f"sqlite:///{(tmp_path / 'migration.sqlite').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("SUPPORT_LEGACY_TIMEZONE", "UTC")
    engine = sa.create_engine(url)
    # Relevant schema at 0040, with existing customer data to preserve.
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE support_tickets (id INTEGER PRIMARY KEY, subject VARCHAR(200), status VARCHAR(20), created_at VARCHAR(30), updated_at VARCHAR(30))")
        conn.exec_driver_sql("CREATE TABLE support_messages (id INTEGER PRIMARY KEY, ticket_id INTEGER, sender VARCHAR(20), text TEXT, created_at VARCHAR(30))")
        conn.exec_driver_sql("CREATE TABLE support_attachments (id INTEGER PRIMARY KEY, created_at VARCHAR(30))")
        conn.exec_driver_sql("INSERT INTO support_tickets VALUES (1, 'Existing ticket', 'in_progress', '2026-09-01T10:00:00Z', '2026-09-01T11:00:00')")
        conn.exec_driver_sql("INSERT INTO support_messages VALUES (1, 1, 'user', 'Original question', '2026-09-01T10:00:00Z'), (2, 1, 'admin', 'Original reply', '2026-09-01T11:00:00')")
    cfg = migration_config()
    command.stamp(cfg, "0040_giveaway_winning_ticket")
    for revision in applied:
        command.upgrade(cfg, revision)

    upgrade_to_head()
    # A second service startup must be a no-op, not repeat CREATE/ALTER.
    upgrade_to_head()
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalars().all() == ["0042_merge_support_branding"]
        assert sa.inspect(conn).has_table("dashboard_branding_assets")
        ticket = conn.execute(sa.text("SELECT subject, status, last_admin_message_id FROM support_tickets")).one()
        assert tuple(ticket) == ("Existing ticket", "waiting_user", 2)
        assert conn.execute(sa.text("SELECT text FROM support_messages ORDER BY id")).scalars().all() == ["Original question", "Original reply"]
    engine.dispose()
