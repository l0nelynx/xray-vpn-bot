"""Add pending subscription-page onboarding markers.

Revision ID: 0039_subscription_onboarding
Revises: 0038_miniapp_ux
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0039_subscription_onboarding"
down_revision: Union[str, None] = "0038_miniapp_ux"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pending_subscription_onboardings",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("rw_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.String(length=30), nullable=False),
        sa.Column("expires_at", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index(
        "ix_pending_subscription_onboardings_expires_at",
        "pending_subscription_onboardings",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pending_subscription_onboardings_expires_at",
        table_name="pending_subscription_onboardings",
    )
    op.drop_table("pending_subscription_onboardings")
