"""Add MiniApp onboarding state and UX funnel events.

Revision ID: 0038_miniapp_ux
Revises: 0037_api_health
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0038_miniapp_ux"
down_revision: Union[str, None] = "0037_api_health"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "miniapp_onboarding_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_table(
        "miniapp_ux_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=True),
        sa.Column("transaction_id", sa.String(100), nullable=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("onboarding_version", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column("platform", sa.String(32), nullable=True),
        sa.Column("source", sa.String(32), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.String(30), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["user_subscriptions.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_miniapp_ux_events_user_created",
        "miniapp_ux_events",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_miniapp_ux_events_name_created",
        "miniapp_ux_events",
        ["name", "created_at"],
    )
    op.create_index(
        "ix_miniapp_ux_events_transaction",
        "miniapp_ux_events",
        ["transaction_id"],
    )


def downgrade() -> None:
    op.drop_table("miniapp_ux_events")
    op.drop_column("users", "miniapp_onboarding_version")
