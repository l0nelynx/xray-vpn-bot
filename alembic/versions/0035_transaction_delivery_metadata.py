"""Add transaction purchase source and delivery error.

Revision ID: 0035_tx_delivery_metadata
Revises: 0034_subscription_transfers
Create Date: 2026-07-29
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0035_tx_delivery_metadata"
down_revision: Union[str, None] = "0034_subscription_transfers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "purchase_source",
            sa.String(length=20),
            server_default="legacy_unknown",
            nullable=False,
        ),
    )
    op.add_column(
        "transactions",
        sa.Column("delivery_error", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_transactions_purchase_source",
        "transactions",
        ["purchase_source"],
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_purchase_source", table_name="transactions")
    op.drop_column("transactions", "delivery_error")
    op.drop_column("transactions", "purchase_source")
