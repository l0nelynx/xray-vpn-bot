"""0019: bonus credits wallet + promo credit_grant.

Adds users.bonus_credits, credit_ledger, promos.credit_grant,
promo_settings.default_credit_grant. Converts legacy discount_percent
via ceil(pct/10*5). Backfills active promo_redemptions to user balances.
Simplifies promo_redemptions to audit-only (drops status/discount_percent).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_bonus_credits"
down_revision: Union[str, None] = "0018_crm_conditions_actions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind, table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _has_table(bind, table: str) -> bool:
    return table in sa.inspect(bind).get_table_names()


def _now_iso_sql(dialect: str) -> str:
    if dialect == "postgresql":
        return "to_char(now(), 'YYYY-MM-DD\"T\"HH24:MI:SS')"
    return "replace(datetime('now'), ' ', 'T')"


def _credit_formula_sql(col: str) -> str:
    """ceil(col / 10 * 5) for integer percent columns."""
    return f"(({col}) * 5 + 9) / 10"


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    now_sql = _now_iso_sql(dialect)

    # 1. users.bonus_credits
    if not _has_column(bind, "users", "bonus_credits"):
        with op.batch_alter_table("users") as batch:
            batch.add_column(
                sa.Column(
                    "bonus_credits",
                    sa.Integer(),
                    server_default="0",
                    nullable=False,
                )
            )

    # 2. credit_ledger
    if not _has_table(bind, "credit_ledger"):
        op.create_table(
            "credit_ledger",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("source", sa.String(32), nullable=False),
            sa.Column("reference", sa.String(100), nullable=True),
            sa.Column("balance_after", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.String(30), nullable=False),
        )
        op.create_index("ix_credit_ledger_user_id", "credit_ledger", ["user_id"])

    # 3. promos.credit_grant
    if not _has_column(bind, "promos", "credit_grant"):
        with op.batch_alter_table("promos") as batch:
            batch.add_column(sa.Column("credit_grant", sa.Integer(), nullable=True))

    if _has_column(bind, "promos", "discount_percent") and _has_column(
        bind, "promos", "credit_grant"
    ):
        formula = _credit_formula_sql("discount_percent")
        op.execute(
            f"UPDATE promos SET credit_grant = {formula} "
            f"WHERE credit_grant IS NULL AND discount_percent IS NOT NULL"
        )
        default_expr = _credit_formula_sql("COALESCE(default_discount_percent, 20)")
        if _has_table(bind, "promo_settings"):
            op.execute(
                f"""
                UPDATE promos SET credit_grant = (
                    SELECT {default_expr} FROM promo_settings WHERE id = 1
                )
                WHERE credit_grant IS NULL
                """
            )
        else:
            op.execute(f"UPDATE promos SET credit_grant = 10 WHERE credit_grant IS NULL")

    # 4. promo_settings.default_credit_grant
    if _has_table(bind, "promo_settings"):
        if not _has_column(bind, "promo_settings", "default_credit_grant"):
            with op.batch_alter_table("promo_settings") as batch:
                batch.add_column(
                    sa.Column(
                        "default_credit_grant",
                        sa.Integer(),
                        server_default="10",
                        nullable=False,
                    )
                )
        if _has_column(bind, "promo_settings", "default_discount_percent"):
            formula = _credit_formula_sql("COALESCE(default_discount_percent, 20)")
            op.execute(
                f"UPDATE promo_settings SET default_credit_grant = {formula} "
                f"WHERE id = 1"
            )

    # 5. Backfill active redemptions → user balance
    if (
        _has_table(bind, "promo_redemptions")
        and _has_column(bind, "promo_redemptions", "status")
        and _has_column(bind, "promo_redemptions", "discount_percent")
    ):
        credits_expr = _credit_formula_sql("pr.discount_percent")
        op.execute(
            f"""
            UPDATE users SET bonus_credits = bonus_credits + sub.credits
            FROM (
                SELECT u.id AS user_id, {credits_expr} AS credits
                FROM promo_redemptions pr
                JOIN users u ON u.tg_id = pr.tg_id
                WHERE pr.status = 'active'
            ) sub
            WHERE users.id = sub.user_id
            """
            if dialect == "postgresql"
            else f"""
            UPDATE users SET bonus_credits = bonus_credits + (
                SELECT {credits_expr} FROM promo_redemptions pr
                WHERE pr.tg_id = users.tg_id AND pr.status = 'active'
                LIMIT 1
            )
            WHERE EXISTS (
                SELECT 1 FROM promo_redemptions pr
                WHERE pr.tg_id = users.tg_id AND pr.status = 'active'
            )
            """
        )
        op.execute(
            f"""
            INSERT INTO credit_ledger (user_id, amount, source, reference, balance_after, created_at)
            SELECT u.id, {credits_expr}, 'migration', pr.promo_code, u.bonus_credits, {now_sql}
            FROM promo_redemptions pr
            JOIN users u ON u.tg_id = pr.tg_id
            WHERE pr.status = 'active'
            """
        )

    # 6. Simplify promo_redemptions — drop legacy discount/status columns
    if _has_table(bind, "promo_redemptions"):
        cols_to_drop = [
            c
            for c in ("discount_percent", "status", "consumed_at")
            if _has_column(bind, "promo_redemptions", c)
        ]
        if cols_to_drop:
            with op.batch_alter_table("promo_redemptions") as batch:
                for col in cols_to_drop:
                    batch.drop_column(col)


def downgrade() -> None:
    bind = op.get_bind()

    if _has_table(bind, "promo_redemptions"):
        if not _has_column(bind, "promo_redemptions", "discount_percent"):
            with op.batch_alter_table("promo_redemptions") as batch:
                batch.add_column(sa.Column("discount_percent", sa.Integer(), nullable=True))
                batch.add_column(
                    sa.Column(
                        "status",
                        sa.String(16),
                        server_default="consumed",
                        nullable=False,
                    )
                )
                batch.add_column(sa.Column("consumed_at", sa.String(30), nullable=True))

    if _has_table(bind, "credit_ledger"):
        op.drop_index("ix_credit_ledger_user_id", table_name="credit_ledger")
        op.drop_table("credit_ledger")

    if _has_column(bind, "users", "bonus_credits"):
        with op.batch_alter_table("users") as batch:
            batch.drop_column("bonus_credits")

    if _has_column(bind, "promos", "credit_grant"):
        with op.batch_alter_table("promos") as batch:
            batch.drop_column("credit_grant")

    if _has_column(bind, "promo_settings", "default_credit_grant"):
        with op.batch_alter_table("promo_settings") as batch:
            batch.drop_column("default_credit_grant")
