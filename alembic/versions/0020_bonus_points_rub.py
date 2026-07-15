"""0020: convert bonus credits (days) to RUB points (×10).

1 old credit = 10 RUB points. Semantics of users.bonus_credits and
credit_ledger change from subscription-days to RUB bonus points.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_bonus_points_rub"
down_revision: Union[str, None] = "0019_bonus_credits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MULTIPLIER = 10


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text(f"UPDATE users SET bonus_credits = bonus_credits * {MULTIPLIER}"))
        op.execute(
            sa.text(
                f"UPDATE promos SET credit_grant = credit_grant * {MULTIPLIER} "
                "WHERE credit_grant IS NOT NULL"
            )
        )
        op.execute(
            sa.text(
                f"UPDATE promo_settings SET default_credit_grant = default_credit_grant * {MULTIPLIER}"
            )
        )
        op.execute(sa.text(f"UPDATE credit_ledger SET amount = amount * {MULTIPLIER}"))
        op.execute(
            sa.text(f"UPDATE credit_ledger SET balance_after = balance_after * {MULTIPLIER}")
        )
        op.alter_column(
            "promo_settings",
            "default_credit_grant",
            server_default=sa.text(str(MULTIPLIER * 10)),
        )
    else:
        op.execute(sa.text(f"UPDATE users SET bonus_credits = bonus_credits * {MULTIPLIER}"))
        op.execute(
            sa.text(
                f"UPDATE promos SET credit_grant = credit_grant * {MULTIPLIER} "
                "WHERE credit_grant IS NOT NULL"
            )
        )
        op.execute(
            sa.text(
                f"UPDATE promo_settings SET default_credit_grant = default_credit_grant * {MULTIPLIER}"
            )
        )
        op.execute(sa.text(f"UPDATE credit_ledger SET amount = amount * {MULTIPLIER}"))
        op.execute(
            sa.text(f"UPDATE credit_ledger SET balance_after = balance_after * {MULTIPLIER}")
        )
        op.alter_column(
            "promo_settings",
            "default_credit_grant",
            server_default=sa.text(str(MULTIPLIER * 10)),
        )


def downgrade() -> None:
    bind = op.get_bind()
    divisor = MULTIPLIER
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(f"UPDATE credit_ledger SET balance_after = balance_after / {divisor}")
        )
        op.execute(sa.text(f"UPDATE credit_ledger SET amount = amount / {divisor}"))
        op.execute(
            sa.text(
                f"UPDATE promo_settings SET default_credit_grant = default_credit_grant / {divisor}"
            )
        )
        op.execute(
            sa.text(
                f"UPDATE promos SET credit_grant = credit_grant / {divisor} "
                "WHERE credit_grant IS NOT NULL"
            )
        )
        op.execute(sa.text(f"UPDATE users SET bonus_credits = bonus_credits / {divisor}"))
        op.alter_column(
            "promo_settings",
            "default_credit_grant",
            server_default=sa.text("10"),
        )
    else:
        op.execute(
            sa.text(f"UPDATE credit_ledger SET balance_after = balance_after / {divisor}")
        )
        op.execute(sa.text(f"UPDATE credit_ledger SET amount = amount / {divisor}"))
        op.execute(
            sa.text(
                f"UPDATE promo_settings SET default_credit_grant = default_credit_grant / {divisor}"
            )
        )
        op.execute(
            sa.text(
                f"UPDATE promos SET credit_grant = credit_grant / {divisor} "
                "WHERE credit_grant IS NOT NULL"
            )
        )
        op.execute(sa.text(f"UPDATE users SET bonus_credits = bonus_credits / {divisor}"))
        op.alter_column(
            "promo_settings",
            "default_credit_grant",
            server_default=sa.text("10"),
        )
