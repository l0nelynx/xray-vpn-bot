"""0030: add complete Remnawave delivery options to tariff nodes."""
from __future__ import annotations

from typing import Sequence, Union
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "0030_tariff_delivery_options"
down_revision: Union[str, None] = "0029_unified_tariff_constructor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(bind, table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()

    node_cols = _columns(bind, "webapp_menu_nodes")
    with op.batch_alter_table("webapp_menu_nodes") as batch:
        if "invoice_internal_squad_ids" not in node_cols:
            batch.add_column(sa.Column("invoice_internal_squad_ids", sa.JSON(), nullable=True))
        if "invoice_traffic_limit_bytes" not in node_cols:
            batch.add_column(sa.Column("invoice_traffic_limit_bytes", sa.BigInteger(), nullable=True))
        if "invoice_traffic_limit_strategy" not in node_cols:
            batch.add_column(sa.Column("invoice_traffic_limit_strategy", sa.String(30), nullable=True))
        if "invoice_remnawave_description" not in node_cols:
            batch.add_column(sa.Column("invoice_remnawave_description", sa.Text(), nullable=True))
        if "invoice_remnawave_tag" not in node_cols:
            batch.add_column(sa.Column("invoice_remnawave_tag", sa.String(16), nullable=True))

    nodes = sa.Table("webapp_menu_nodes", sa.MetaData(), autoload_with=bind)
    rows = bind.execute(
        sa.select(
            nodes.c.id,
            nodes.c.action,
            nodes.c.invoice_squad_id,
            nodes.c.invoice_external_squad_id,
        )
    ).mappings()
    for row in rows:
        squad_id = str(row["invoice_squad_id"] or "").strip()
        external_id = str(row["invoice_external_squad_id"] or "").strip()
        valid_target = True
        if row["action"] == "invoice":
            try:
                uuid.UUID(squad_id)
                uuid.UUID(external_id)
            except (ValueError, TypeError, AttributeError):
                valid_target = False
        bind.execute(
            nodes.update().where(nodes.c.id == row["id"]).values(
                invoice_internal_squad_ids=[squad_id] if squad_id else None,
                invoice_traffic_limit_bytes=0,
                invoice_traffic_limit_strategy="NO_RESET",
                **({"is_active": False} if not valid_target else {}),
            )
        )

    with op.batch_alter_table("webapp_menu_nodes") as batch:
        if "invoice_squad_id" in _columns(bind, "webapp_menu_nodes"):
            batch.drop_column("invoice_squad_id")

    tx_cols = _columns(bind, "transactions")
    with op.batch_alter_table("transactions") as batch:
        if "internal_squad_ids" not in tx_cols:
            batch.add_column(sa.Column("internal_squad_ids", sa.JSON(), nullable=True))
        if "traffic_limit_bytes" not in tx_cols:
            batch.add_column(sa.Column("traffic_limit_bytes", sa.BigInteger(), nullable=True))
        if "traffic_limit_strategy" not in tx_cols:
            batch.add_column(sa.Column("traffic_limit_strategy", sa.String(30), nullable=True))
        if "remnawave_description" not in tx_cols:
            batch.add_column(sa.Column("remnawave_description", sa.Text(), nullable=True))
        if "remnawave_tag" not in tx_cols:
            batch.add_column(sa.Column("remnawave_tag", sa.String(16), nullable=True))

    transactions = sa.Table("transactions", sa.MetaData(), autoload_with=bind)
    rows = bind.execute(
        sa.select(transactions.c.transaction_id, transactions.c.squad_id)
    ).mappings()
    for row in rows:
        squad_id = str(row["squad_id"] or "").strip()
        bind.execute(
            transactions.update()
            .where(transactions.c.transaction_id == row["transaction_id"])
            .values(
                internal_squad_ids=[squad_id] if squad_id else None,
                traffic_limit_bytes=0,
                traffic_limit_strategy="NO_RESET",
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    nodes = sa.Table("webapp_menu_nodes", sa.MetaData(), autoload_with=bind)
    with op.batch_alter_table("webapp_menu_nodes") as batch:
        batch.add_column(sa.Column("invoice_squad_id", sa.String(100), nullable=True))
    nodes = sa.Table("webapp_menu_nodes", sa.MetaData(), autoload_with=bind)
    for row in bind.execute(
        sa.select(nodes.c.id, nodes.c.invoice_internal_squad_ids)
    ).mappings():
        values = row["invoice_internal_squad_ids"] or []
        bind.execute(
            nodes.update().where(nodes.c.id == row["id"]).values(
                invoice_squad_id=str(values[0]) if values else None
            )
        )
    with op.batch_alter_table("webapp_menu_nodes") as batch:
        batch.drop_column("invoice_internal_squad_ids")
        batch.drop_column("invoice_traffic_limit_bytes")
        batch.drop_column("invoice_traffic_limit_strategy")
        batch.drop_column("invoice_remnawave_description")
        batch.drop_column("invoice_remnawave_tag")

    with op.batch_alter_table("transactions") as batch:
        batch.drop_column("internal_squad_ids")
        batch.drop_column("traffic_limit_bytes")
        batch.drop_column("traffic_limit_strategy")
        batch.drop_column("remnawave_description")
        batch.drop_column("remnawave_tag")
