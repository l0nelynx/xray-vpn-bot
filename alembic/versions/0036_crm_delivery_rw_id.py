"""Add numeric Remnawave user id to CRM deliveries.

Revision ID: 0036_crm_delivery_rw_id
Revises: 0035_tx_delivery_metadata
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0036_crm_delivery_rw_id"
down_revision: Union[str, None] = "0035_tx_delivery_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "crm_campaign_deliveries",
        sa.Column("rw_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_crm_campaign_deliveries_rw_id",
        "crm_campaign_deliveries",
        ["rw_id"],
    )
    # Historical UUIDs are backfilled only when exactly one local user owns
    # that legacy value. Ambiguous rows deliberately remain NULL.
    op.execute(
        """
        UPDATE crm_campaign_deliveries AS d
        SET rw_id = (
            SELECT MIN(u.rw_id) FROM users AS u
            WHERE u.vless_uuid = d.vless_uuid AND u.rw_id IS NOT NULL
            HAVING COUNT(*) = 1
        )
        WHERE d.rw_id IS NULL AND d.vless_uuid IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_crm_campaign_deliveries_rw_id", table_name="crm_campaign_deliveries")
    op.drop_column("crm_campaign_deliveries", "rw_id")
