"""users.rw_id — Remnawave panel numeric user id.

Revision ID: 0016_users_rw_id
Revises: 0015_crm_campaigns
Create Date: 2026-07-14
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_users_rw_id"
down_revision: Union[str, None] = "0015_crm_campaigns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind, table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "users", "rw_id"):
        op.add_column("users", sa.Column("rw_id", sa.BigInteger(), nullable=True))
        op.create_index("ix_users_rw_id", "users", ["rw_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, "users", "rw_id"):
        op.drop_index("ix_users_rw_id", table_name="users")
        op.drop_column("users", "rw_id")
