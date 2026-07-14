"""crm_campaigns + crm_campaign_deliveries — dashboard CRM history/audit.

Revision ID: 0015_crm_campaigns
Revises: 0014_support_attachments
Create Date: 2026-07-13
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_crm_campaigns"
down_revision: Union[str, None] = "0014_support_attachments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, table: str) -> bool:
    return table in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "crm_campaigns"):
        op.create_table(
            "crm_campaigns",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(200), nullable=False, server_default=""),
            sa.Column("segment_type", sa.String(50), nullable=True),
            sa.Column("segment_params", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("message_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("attach_button", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("bonus_days", sa.Integer(), nullable=True),
            sa.Column("bonus_traffic_gb", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
            sa.Column("total_targets", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("messages_sent", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("messages_failed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("perks_applied", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("perks_failed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.String(30), nullable=False),
            sa.Column("started_at", sa.String(30), nullable=True),
            sa.Column("completed_at", sa.String(30), nullable=True),
            sa.Column("created_by", sa.String(100), nullable=False, server_default=""),
        )
        op.create_index("ix_crm_campaigns_status", "crm_campaigns", ["status"])
        op.create_index("ix_crm_campaigns_created_at", "crm_campaigns", ["created_at"])

    if not _has_table(bind, "crm_campaign_deliveries"):
        op.create_table(
            "crm_campaign_deliveries",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "campaign_id",
                sa.BigInteger(),
                sa.ForeignKey("crm_campaigns.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("tg_id", sa.BigInteger(), nullable=False),
            sa.Column("vless_uuid", sa.String(64), nullable=True),
            sa.Column("perk_status", sa.String(20), nullable=False, server_default="skipped"),
            sa.Column("message_status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("error", sa.Text(), nullable=True),
        )
        op.create_index(
            "ix_crm_campaign_deliveries_campaign_id",
            "crm_campaign_deliveries",
            ["campaign_id"],
        )
        op.create_index(
            "ix_crm_campaign_deliveries_tg_id",
            "crm_campaign_deliveries",
            ["tg_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "crm_campaign_deliveries"):
        op.drop_table("crm_campaign_deliveries")
    if _has_table(bind, "crm_campaigns"):
        op.drop_table("crm_campaigns")
