"""Add the persistent Dashboard branding logo snapshot.

Revision ID: 0041_dashboard_branding_asset
Revises: 0040_giveaway_winning_ticket
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0041_dashboard_branding_asset"
down_revision: Union[str, None] = "0040_giveaway_winning_ticket"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dashboard_branding_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("mime_type", sa.String(length=40), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.String(length=30), nullable=False),
        sa.Column("updated_by", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("dashboard_branding_assets")
