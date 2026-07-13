"""align baseline with models.py (replaces ad-hoc ALTERs).

Adds the columns/tables that the runtime previously created on each startup
via app.database.models.async_main() and miniapp.backend.main.ensure_support_tables().

Revision ID: 0002_align_with_models
Revises: 0001_baseline
Create Date: 2026-05-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_align_with_models"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def _has_table(bind, table: str) -> bool:
    insp = sa.inspect(bind)
    return table in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    # promos: discount_percent, used_promo_consumed
    if not _has_column(bind, "promos", "discount_percent"):
        with op.batch_alter_table("promos") as batch:
            batch.add_column(sa.Column("discount_percent", sa.Integer()))
    if not _has_column(bind, "promos", "used_promo_consumed"):
        with op.batch_alter_table("promos") as batch:
            batch.add_column(
                sa.Column(
                    "used_promo_consumed",
                    sa.Boolean(),
                    server_default="0",
                    nullable=False,
                )
            )

    # promo_settings — new singleton table
    if not _has_table(bind, "promo_settings"):
        op.create_table(
            "promo_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "default_discount_percent",
                sa.Integer(),
                nullable=False,
                server_default="20",
            ),
        )
        op.execute(
            "INSERT INTO promo_settings (id, default_discount_percent) VALUES (1, 20)"
        )

    # transactions: tariff_slug
    if not _has_column(bind, "transactions", "tariff_slug"):
        with op.batch_alter_table("transactions") as batch:
            batch.add_column(sa.Column("tariff_slug", sa.String(200)))
        # Backfill expire_date from created_at + days_ordered. The expression
        # is dialect-specific; on a fresh Postgres install the table is empty
        # anyway, so skipping it there is safe.
        if bind.dialect.name == "sqlite":
            op.execute(
                "UPDATE transactions "
                "SET expire_date = replace(datetime(created_at, '+' || days_ordered || ' days'), ' ', 'T') "
                "WHERE expire_date IS NULL "
                "AND order_status IN ('confirmed', 'delivered') "
                "AND created_at IS NOT NULL "
                "AND days_ordered IS NOT NULL"
            )
        elif bind.dialect.name == "postgresql":
            op.execute(
                "UPDATE transactions "
                "SET expire_date = to_char("
                "  (created_at::timestamp + (days_ordered || ' days')::interval),"
                "  'YYYY-MM-DD\"T\"HH24:MI:SS'"
                ") "
                "WHERE expire_date IS NULL "
                "AND order_status IN ('confirmed', 'delivered') "
                "AND created_at IS NOT NULL "
                "AND days_ordered IS NOT NULL"
            )

    # webapp_menu_nodes.invoice_method (model has it; production DB may not)
    if _has_table(bind, "webapp_menu_nodes") and not _has_column(
        bind, "webapp_menu_nodes", "invoice_method"
    ):
        with op.batch_alter_table("webapp_menu_nodes") as batch:
            batch.add_column(sa.Column("invoice_method", sa.String(30)))


def downgrade() -> None:
    bind = op.get_bind()

    if _has_table(bind, "webapp_menu_nodes") and _has_column(
        bind, "webapp_menu_nodes", "invoice_method"
    ):
        with op.batch_alter_table("webapp_menu_nodes") as batch:
            batch.drop_column("invoice_method")

    if _has_column(bind, "transactions", "tariff_slug"):
        with op.batch_alter_table("transactions") as batch:
            batch.drop_column("tariff_slug")

    if _has_table(bind, "promo_settings"):
        op.drop_table("promo_settings")

    if _has_column(bind, "promos", "used_promo_consumed"):
        with op.batch_alter_table("promos") as batch:
            batch.drop_column("used_promo_consumed")

    if _has_column(bind, "promos", "discount_percent"):
        with op.batch_alter_table("promos") as batch:
            batch.drop_column("discount_percent")
