"""0023: android_fcm_tokens + push_campaigns / push_campaign_deliveries."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023_android_fcm_push"
down_revision: Union[str, None] = "0022_telemt_free_rate_limits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, table: str) -> bool:
    return table in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "android_fcm_tokens"):
        op.create_table(
            "android_fcm_tokens",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "user_id",
                sa.BigInteger(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("token", sa.Text(), nullable=False),
            sa.Column(
                "platform", sa.String(20), nullable=False, server_default="android"
            ),
            sa.Column("app_version", sa.String(64), nullable=True),
            sa.Column("created_at", sa.String(30), nullable=False),
            sa.Column("updated_at", sa.String(30), nullable=False),
            sa.UniqueConstraint("token", name="uq_android_fcm_tokens_token"),
        )
        op.create_index(
            "ix_android_fcm_tokens_user_id", "android_fcm_tokens", ["user_id"]
        )

    if not _has_table(bind, "push_campaigns"):
        op.create_table(
            "push_campaigns",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("title", sa.String(200), nullable=False, server_default=""),
            sa.Column("body", sa.Text(), nullable=False, server_default=""),
            sa.Column("data_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column(
                "audience",
                sa.String(20),
                nullable=False,
                server_default="all_tokens",
            ),
            sa.Column(
                "audience_params", sa.Text(), nullable=False, server_default="{}"
            ),
            sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
            sa.Column(
                "total_targets", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column("sent", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.String(30), nullable=False),
            sa.Column("started_at", sa.String(30), nullable=True),
            sa.Column("completed_at", sa.String(30), nullable=True),
            sa.Column(
                "created_by", sa.String(100), nullable=False, server_default=""
            ),
        )
        op.create_index("ix_push_campaigns_status", "push_campaigns", ["status"])
        op.create_index(
            "ix_push_campaigns_created_at", "push_campaigns", ["created_at"]
        )

    if not _has_table(bind, "push_campaign_deliveries"):
        op.create_table(
            "push_campaign_deliveries",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "campaign_id",
                sa.BigInteger(),
                sa.ForeignKey("push_campaigns.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("token", sa.Text(), nullable=False),
            sa.Column(
                "status", sa.String(20), nullable=False, server_default="pending"
            ),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("sent_at", sa.String(30), nullable=True),
        )
        op.create_index(
            "ix_push_campaign_deliveries_campaign_id",
            "push_campaign_deliveries",
            ["campaign_id"],
        )
        op.create_index(
            "ix_push_campaign_deliveries_user_id",
            "push_campaign_deliveries",
            ["user_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "push_campaign_deliveries"):
        op.drop_table("push_campaign_deliveries")
    if _has_table(bind, "push_campaigns"):
        op.drop_table("push_campaigns")
    if _has_table(bind, "android_fcm_tokens"):
        op.drop_table("android_fcm_tokens")
