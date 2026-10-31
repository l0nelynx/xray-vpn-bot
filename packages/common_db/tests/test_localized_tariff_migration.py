"""Preserve existing tariff order through upgrade and downgrade."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_existing_invoice_order_is_copied_to_both_languages(tmp_path):
    root = Path(__file__).parents[3]
    db_path = tmp_path / "localized-order.sqlite3"
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.cmd_opts = type("Options", (), {"x": [f"dburl=sqlite:///{db_path}"]})()
    command.upgrade(config, "0045_remnawave_availability")
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO webapp_menu_nodes (id, parent_id, text_ru, text_en, action, sort_order, is_active)
            VALUES (1, NULL, 'Категория', 'Category', 'buttons', 0, 1),
                   (2, 1, 'B', 'B', 'invoice', 30, 1),
                   (3, 1, 'A', 'A', 'invoice', 10, 0),
                   (4, NULL, 'Root', 'Root', 'invoice', 99, 1)
        """))
    command.upgrade(config, "0046_localized_payment_order")
    with engine.connect() as connection:
        assert connection.execute(text(
            "SELECT id, sort_order_ru, sort_order_en FROM webapp_menu_nodes ORDER BY id"
        )).all() == [(1, None, None), (2, 1, 1), (3, 0, 0), (4, 0, 0)]
    command.downgrade(config, "0045_remnawave_availability")
    with engine.connect() as connection:
        assert not {"sort_order_ru", "sort_order_en"} & {
            column["name"] for column in inspect(connection).get_columns("webapp_menu_nodes")
        }
        assert connection.execute(text(
            "SELECT id, parent_id, sort_order, is_active FROM webapp_menu_nodes ORDER BY id"
        )).all() == [(1, None, 0, 1), (2, 1, 30, 1), (3, 1, 10, 0), (4, None, 99, 1)]
    engine.dispose()
