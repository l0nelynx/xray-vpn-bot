"""promo redemptions + referral/promotional types + reward settings.

Introduces the ``promo_redemptions`` table (history of which user redeemed
which code) and migrates the legacy single ``promos.used_promo`` column into
it. Adds ``promos.promo_type`` (referral vs promotional) and the reward
tunables (``days_reward_per_30``, ``reward_cap_days``) onto the singleton
``promo_settings`` so the bot, miniapp and dashboard share one source of
truth instead of splitting them between config.yml and the DB.

Idempotent (mirrors 0002): safe to re-run. Legacy ``used_promo`` /
``used_promo_consumed`` columns are intentionally kept for now.

Revision ID: 0012_promo_redemptions
Revises: 0011_fix_sequences
Create Date: 2026-06-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0012_promo_redemptions"
down_revision: Union[str, None] = "0011_fix_sequences"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def _has_table(bind, table: str) -> bool:
    insp = sa.inspect(bind)
    return table in insp.get_table_names()


def _now_iso_sql(dialect: str) -> str:
    """SQL expression yielding an ISO-8601 string (matches String(30) cols)."""
    if dialect == "postgresql":
        return "to_char(now(), 'YYYY-MM-DD\"T\"HH24:MI:SS')"
    # sqlite
    return "replace(datetime('now'), ' ', 'T')"


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # 1. promos.promo_type
    if not _has_column(bind, "promos", "promo_type"):
        with op.batch_alter_table("promos") as batch:
            batch.add_column(
                sa.Column(
                    "promo_type",
                    sa.String(20),
                    server_default="referral",
                    nullable=False,
                )
            )
        # Admin/dashboard codes were created under synthetic negative tg_ids
        # and have no invitee semantics — classify them as promotional.
        op.execute("UPDATE promos SET promo_type = 'promotional' WHERE tg_id < 0")

    # 2. promo_settings reward tunables
    if _has_table(bind, "promo_settings"):
        if not _has_column(bind, "promo_settings", "days_reward_per_30"):
            with op.batch_alter_table("promo_settings") as batch:
                batch.add_column(
                    sa.Column(
                        "days_reward_per_30",
                        sa.Integer(),
                        server_default="3",
                        nullable=False,
                    )
                )
        if not _has_column(bind, "promo_settings", "reward_cap_days"):
            with op.batch_alter_table("promo_settings") as batch:
                batch.add_column(
                    sa.Column(
                        "reward_cap_days",
                        sa.Integer(),
                        server_default="180",
                        nullable=False,
                    )
                )

    # 3. promo_redemptions table
    if not _has_table(bind, "promo_redemptions"):
        op.create_table(
            "promo_redemptions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tg_id", sa.BigInteger(), nullable=False),
            sa.Column("promo_code", sa.String(20), nullable=False),
            sa.Column("promo_type", sa.String(20), nullable=False),
            sa.Column("discount_percent", sa.Integer(), nullable=False),
            sa.Column(
                "status", sa.String(16), server_default="active", nullable=False
            ),
            sa.Column("created_at", sa.String(30), nullable=False),
            sa.Column("consumed_at", sa.String(30), nullable=True),
        )
        op.create_index(
            "ix_promo_redemptions_tg_id", "promo_redemptions", ["tg_id"]
        )
        op.create_index(
            "ix_promo_redemptions_promo_code", "promo_redemptions", ["promo_code"]
        )

        # 4. Backfill from legacy promos.used_promo. Resolve the discount the
        #    same way the runtime cascade does: owner's discount_percent, else
        #    the promo_settings default (coalesced to 20 if the row is absent).
        now_sql = _now_iso_sql(dialect)
        op.execute(
            f"""
            INSERT INTO promo_redemptions
                (tg_id, promo_code, promo_type, discount_percent, status, created_at)
            SELECT
                u.tg_id,
                u.used_promo,
                COALESCE(owner.promo_type, 'referral'),
                COALESCE(
                    owner.discount_percent,
                    (SELECT default_discount_percent FROM promo_settings WHERE id = 1),
                    20
                ),
                CASE WHEN u.used_promo_consumed THEN 'consumed' ELSE 'active' END,
                {now_sql}
            FROM promos u
            LEFT JOIN promos owner ON owner.promo_code = u.used_promo
            WHERE u.used_promo IS NOT NULL
            """
        )


def downgrade() -> None:
    bind = op.get_bind()

    if _has_table(bind, "promo_redemptions"):
        op.drop_index("ix_promo_redemptions_promo_code", table_name="promo_redemptions")
        op.drop_index("ix_promo_redemptions_tg_id", table_name="promo_redemptions")
        op.drop_table("promo_redemptions")

    if _has_table(bind, "promo_settings"):
        if _has_column(bind, "promo_settings", "reward_cap_days"):
            with op.batch_alter_table("promo_settings") as batch:
                batch.drop_column("reward_cap_days")
        if _has_column(bind, "promo_settings", "days_reward_per_30"):
            with op.batch_alter_table("promo_settings") as batch:
                batch.drop_column("days_reward_per_30")

    if _has_column(bind, "promos", "promo_type"):
        with op.batch_alter_table("promos") as batch:
            batch.drop_column("promo_type")
