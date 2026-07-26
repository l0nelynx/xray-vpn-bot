"""Add PKCE authorization codes for the subscription-page BFF.

Revision ID: 0032_web_authorization_codes
Revises: 0031_user_subscriptions
Create Date: 2026-07-26
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0032_web_authorization_codes"
down_revision: Union[str, None] = "0031_user_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "web_authorization_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("redirect_uri", sa.String(length=500), nullable=False),
        sa.Column("code_challenge", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.String(length=30), nullable=False),
        sa.Column("expires_at", sa.String(length=30), nullable=False),
        sa.Column("used_at", sa.String(length=30), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )
    op.create_index(
        "ix_web_authorization_codes_user_id",
        "web_authorization_codes",
        ["user_id"],
    )
    op.create_index(
        "ix_web_authorization_codes_expires_at",
        "web_authorization_codes",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_web_authorization_codes_expires_at", table_name="web_authorization_codes"
    )
    op.drop_index(
        "ix_web_authorization_codes_user_id", table_name="web_authorization_codes"
    )
    op.drop_table("web_authorization_codes")
