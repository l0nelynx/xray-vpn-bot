"""Add account-managed Remnawave subscriptions.

Revision ID: 0031_user_subscriptions
Revises: 0030_tariff_delivery_options
Create Date: 2026-07-26
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031_user_subscriptions"
down_revision: Union[str, None] = "0030_tariff_delivery_options"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _indexes(bind, table: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()

    duplicate = bind.execute(
        sa.text(
            "SELECT rw_id, COUNT(*) AS n FROM users "
            "WHERE rw_id IS NOT NULL GROUP BY rw_id HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).mappings().first()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot make users.rw_id unique: duplicate Remnawave id "
            f"{duplicate['rw_id']} is linked to {duplicate['n']} users. "
            "Run the rw_id audit and resolve ownership before retrying."
        )

    user_indexes = _indexes(bind, "users")
    if "ix_users_rw_id" in user_indexes:
        op.drop_index("ix_users_rw_id", table_name="users")
    if "ux_users_rw_id" not in user_indexes:
        op.create_index(
            "ux_users_rw_id",
            "users",
            ["rw_id"],
            unique=True,
            postgresql_where=sa.text("rw_id IS NOT NULL"),
            sqlite_where=sa.text("rw_id IS NOT NULL"),
        )

    op.create_table(
        "user_subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("rw_id", sa.BigInteger(), nullable=False),
        sa.Column("product_key", sa.String(length=100), nullable=True),
        sa.Column("label", sa.String(length=100), nullable=True),
        sa.Column(
            "source", sa.String(length=30), server_default="legacy", nullable=False
        ),
        sa.Column(
            "is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("created_at", sa.String(length=30), nullable=False),
        sa.Column("updated_at", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_subscriptions_user_id", "user_subscriptions", ["user_id"]
    )
    op.create_index(
        "ux_user_subscriptions_rw_id",
        "user_subscriptions",
        ["rw_id"],
        unique=True,
    )
    op.create_index(
        "ux_user_subscriptions_primary",
        "user_subscriptions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
        sqlite_where=sa.text("is_primary = 1"),
    )

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    bind.execute(
        sa.text(
            "INSERT INTO user_subscriptions "
            "(user_id, rw_id, source, is_primary, created_at, updated_at) "
            "SELECT id, rw_id, 'legacy', true, :now, :now FROM users "
            "WHERE rw_id IS NOT NULL"
        ),
        {"now": now},
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("ux_user_subscriptions_primary", table_name="user_subscriptions")
    op.drop_index("ux_user_subscriptions_rw_id", table_name="user_subscriptions")
    op.drop_index("ix_user_subscriptions_user_id", table_name="user_subscriptions")
    op.drop_table("user_subscriptions")

    user_indexes = _indexes(bind, "users")
    if "ux_users_rw_id" in user_indexes:
        op.drop_index("ux_users_rw_id", table_name="users")
    if "ix_users_rw_id" not in user_indexes:
        op.create_index("ix_users_rw_id", "users", ["rw_id"])
