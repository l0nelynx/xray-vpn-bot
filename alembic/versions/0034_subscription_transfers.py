"""Add idempotent remaining-time transfer ledger.

Revision ID: 0034_subscription_transfers
Revises: 0033_transaction_target_rw_id
Create Date: 2026-07-26
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0034_subscription_transfers"
down_revision: Union[str, None] = "0033_transaction_target_rw_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscription_transfers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("source_rw_id", sa.BigInteger(), nullable=False),
        sa.Column("target_rw_id", sa.BigInteger(), nullable=False),
        sa.Column("days_transferred", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.String(length=30), nullable=False),
        sa.Column("updated_at", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ux_subscription_transfers_source_rw_id",
        "subscription_transfers",
        ["source_rw_id"],
        unique=True,
    )
    op.create_index(
        "ix_subscription_transfers_user_id",
        "subscription_transfers",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_subscription_transfers_user_id", table_name="subscription_transfers"
    )
    op.drop_index(
        "ux_subscription_transfers_source_rw_id", table_name="subscription_transfers"
    )
    op.drop_table("subscription_transfers")
