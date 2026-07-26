"""Data-preserving SQLite coverage for the unified tariff migration."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def _config(db_path: Path) -> Config:
    config = Config(str(Path(__file__).parents[3] / "alembic.ini"))
    config.set_main_option(
        "script_location", str(Path(__file__).parents[3] / "alembic")
    )
    config.cmd_opts = type("Options", (), {"x": [f"dburl=sqlite:///{db_path}"]})()
    return config


def test_upgrade_resolves_targets_and_removes_legacy_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "migration.sqlite3"
    config = _config(db_path)
    command.upgrade(config, "0028_app_integrations")
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO users (id, tg_id, username, vless_uuid) "
            "VALUES (1, 10, 'test', 'user-vless')"
        ))
        conn.execute(text(
            "INSERT INTO squad_profiles "
            "(id, name, squad_id, external_squad_id) "
            "VALUES (1, 'Main', 'squad-a', 'external-a')"
        ))
        conn.execute(text(
            "INSERT INTO tariff_plans "
            "(id, slug, name_ru, name_en, days, sort_order, is_active, "
            "discount_percent, squad_profile_id) "
            "VALUES (1, 'legacy-month', 'Месяц', 'Month', 30, 1, 1, 0, 1)"
        ))
        conn.execute(text(
            "INSERT INTO tariff_prices "
            "(id, tariff_id, payment_method, price, currency, is_active) "
            "VALUES (1, 1, 'crypto', 10, 'USDT', 1)"
        ))
        conn.execute(text(
            "INSERT INTO webapp_menu_nodes "
            "(id, text, action, sort_order, is_active, invoice_provider, "
            "invoice_amount, invoice_currency, invoice_method, invoice_days, "
            "invoice_tariff_slug) VALUES "
            "(1, 'Encoded', 'invoice', 1, 1, 'crypto', 10, 'USDT', "
            "'default', 30, 'sid:squad-x:esid:external-x'), "
            "(2, 'Legacy', 'invoice', 2, 1, 'crypto', 10, 'USDT', "
            "'default', 30, 'legacy-month'), "
            "(3, 'Broken', 'invoice', 3, 1, 'crypto', 10, 'USDT', "
            "'default', 30, NULL), "
            "(4, 'Bad amount', 'invoice', 4, 1, 'crypto', 0, 'USDT', "
            "'default', 30, 'sid:squad-x:esid:external-x')"
        ))
        for tx_id, slug, status in (
            ("provider-encoded", "sid:squad-x:esid:external-x", "created"),
            ("provider-legacy", "legacy-month", "pending"),
            ("provider-derived", None, "created"),
            ("provider-history", "legacy-month", "paid"),
        ):
            conn.execute(text(
                "INSERT INTO transactions "
                "(transaction_id, vless_uuid, username, order_status, "
                "delivery_status, payment_method, amount, days_ordered, "
                "user_id, tariff_slug) "
                "VALUES (:tx, 'delivery-uuid', 'test', :status, 0, 'crypto', "
                "10, 30, 1, :slug)"
            ), {"tx": tx_id, "slug": slug, "status": status})

    command.upgrade(config, "head")
    with engine.connect() as conn:
        tables = set(inspect(conn).get_table_names())
        assert not {"tariff_prices", "tariff_plans", "squad_profiles"} & tables

        node_columns = {item["name"] for item in inspect(conn).get_columns(
            "webapp_menu_nodes"
        )}
        assert "text" not in node_columns
        assert "invoice_tariff_slug" not in node_columns
        nodes = {
            row.id: row
            for row in conn.execute(text(
                "SELECT id, text_ru, text_en, is_active, invoice_internal_squad_ids, "
                "invoice_external_squad_id FROM webapp_menu_nodes"
            ))
        }
        assert (
            json.loads(nodes[1].invoice_internal_squad_ids),
            nodes[1].invoice_external_squad_id,
        ) == (["squad-x"], "external-x")
        assert (
            json.loads(nodes[2].invoice_internal_squad_ids),
            nodes[2].invoice_external_squad_id,
        ) == (["squad-a"], "external-a")
        assert nodes[2].text_ru == nodes[2].text_en == "Legacy"
        assert not nodes[3].is_active
        assert not nodes[4].is_active

        transactions = {
            row.provider_invoice_id: row
            for row in conn.execute(text(
                "SELECT transaction_id, provider_invoice_id, squad_id, internal_squad_ids, "
                "external_squad_id, order_status FROM transactions"
            ))
        }
        for provider_id in (
            "provider-encoded", "provider-legacy", "provider-derived"
        ):
            uuid.UUID(transactions[provider_id].transaction_id)
            assert transactions[provider_id].transaction_id != provider_id
        assert transactions["provider-history"].transaction_id == "provider-history"
        assert transactions["provider-derived"].squad_id == "squad-a"
        assert json.loads(transactions["provider-derived"].internal_squad_ids) == ["squad-a"]
        assert transactions["provider-derived"].external_squad_id == "external-a"
    engine.dispose()
