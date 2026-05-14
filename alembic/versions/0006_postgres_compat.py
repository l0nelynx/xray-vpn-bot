"""Move legacy ad-hoc ALTER/CREATE blocks from models.async_main into a
proper Alembic revision. Idempotent: every step checks current state, so
running on an already-migrated SQLite is a no-op.

Revision ID: 0006_postgres_compat
Revises: 0005_google_play_iap
Create Date: 2026-05-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_postgres_compat"
down_revision = "0005_google_play_iap"
branch_labels = None
depends_on = None


def _has_column(insp, table: str, col: str) -> bool:
    return col in {c["name"] for c in insp.get_columns(table)}


def _has_index(insp, table: str, idx: str) -> bool:
    return idx in {i["name"] for i in insp.get_indexes(table)}


def _has_table(insp, table: str) -> bool:
    return table in set(insp.get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not _has_column(insp, "users", "email"):
        op.add_column("users", sa.Column("email", sa.String(100), nullable=True))
    if not _has_column(insp, "users", "is_banned"):
        op.add_column(
            "users",
            sa.Column("is_banned", sa.Boolean(), nullable=True, server_default=sa.text("FALSE")),
        )
    if not _has_column(insp, "users", "language"):
        op.add_column(
            "users",
            sa.Column("language", sa.String(5), nullable=True, server_default="ru"),
        )
    if not _has_column(insp, "users", "vip"):
        op.add_column(
            "users",
            sa.Column("vip", sa.Integer(), nullable=True, server_default="0"),
        )

    if _has_table(insp, "tariff_plans"):
        tp_cols = {c["name"] for c in insp.get_columns("tariff_plans")}
        if "squad_profile_id" not in tp_cols:
            op.add_column(
                "tariff_plans",
                sa.Column(
                    "squad_profile_id",
                    sa.Integer(),
                    sa.ForeignKey("squad_profiles.id"),
                    nullable=True,
                ),
            )

    if not _has_index(insp, "users", "ix_user_username"):
        op.create_index("ix_user_username", "users", ["username"])

    if not _has_table(insp, "support_tickets"):
        op.create_table(
            "support_tickets",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("username", sa.String(100), nullable=True),
            sa.Column("subject", sa.String(200), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="open"),
            sa.Column("created_at", sa.String(30), nullable=False),
            sa.Column("updated_at", sa.String(30), nullable=False),
        )
        op.create_index("ix_support_tickets_user_id", "support_tickets", ["user_id"])
        op.create_index("ix_support_tickets_status", "support_tickets", ["status"])

    if not _has_table(insp, "support_messages"):
        op.create_table(
            "support_messages",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "ticket_id",
                sa.Integer(),
                sa.ForeignKey("support_tickets.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("sender", sa.String(20), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("created_at", sa.String(30), nullable=False),
        )
        op.create_index("ix_support_messages_ticket_id", "support_messages", ["ticket_id"])


def downgrade() -> None:
    pass
