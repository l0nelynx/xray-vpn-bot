"""Persist the Remnawave subscription targeted by a purchase.

Revision ID: 0033_transaction_target_rw_id
Revises: 0032_web_authorization_codes
Create Date: 2026-07-26
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033_transaction_target_rw_id"
down_revision: Union[str, None] = "0032_web_authorization_codes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions", sa.Column("target_rw_id", sa.BigInteger(), nullable=True)
    )
    op.create_index(
        "ix_transactions_target_rw_id", "transactions", ["target_rw_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_target_rw_id", table_name="transactions")
    op.drop_column("transactions", "target_rw_id")
