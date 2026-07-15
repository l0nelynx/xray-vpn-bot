"""0021: referral owner rewards in bonus points (not subscription days).

Rename reward counters/settings and scale ×10 (3 days → 30 points, cap 180 → 1800).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021_referral_owner_points"
down_revision: Union[str, None] = "0020_bonus_points_rub"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MULTIPLIER = 10


def _scale_and_rename_promo_settings() -> None:
    op.execute(
        sa.text(
            f"UPDATE promo_settings SET days_reward_per_30 = days_reward_per_30 * {MULTIPLIER}"
        )
    )
    op.execute(
        sa.text(
            f"UPDATE promo_settings SET reward_cap_days = reward_cap_days * {MULTIPLIER}"
        )
    )
    op.execute(
        sa.text(f"UPDATE promos SET days_rewarded = days_rewarded * {MULTIPLIER}")
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "promo_settings",
            "days_reward_per_30",
            new_column_name="points_reward_per_30",
        )
        op.alter_column(
            "promo_settings",
            "reward_cap_days",
            new_column_name="reward_cap_points",
        )
        op.alter_column("promos", "days_rewarded", new_column_name="points_rewarded")
    else:
        with op.batch_alter_table("promo_settings") as batch:
            batch.alter_column(
                "days_reward_per_30",
                new_column_name="points_reward_per_30",
            )
            batch.alter_column(
                "reward_cap_days",
                new_column_name="reward_cap_points",
            )
        with op.batch_alter_table("promos") as batch:
            batch.alter_column("days_rewarded", new_column_name="points_rewarded")

    if bind.dialect.name == "postgresql":
        op.alter_column(
            "promo_settings",
            "points_reward_per_30",
            server_default=sa.text(str(3 * MULTIPLIER)),
        )
        op.alter_column(
            "promo_settings",
            "reward_cap_points",
            server_default=sa.text(str(180 * MULTIPLIER)),
        )
    else:
        with op.batch_alter_table("promo_settings") as batch:
            batch.alter_column(
                "points_reward_per_30",
                server_default=sa.text(str(3 * MULTIPLIER)),
            )
            batch.alter_column(
                "reward_cap_points",
                server_default=sa.text(str(180 * MULTIPLIER)),
            )


def _rename_back_promo_settings() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column("promos", "points_rewarded", new_column_name="days_rewarded")
        op.alter_column(
            "promo_settings",
            "reward_cap_points",
            new_column_name="reward_cap_days",
        )
        op.alter_column(
            "promo_settings",
            "points_reward_per_30",
            new_column_name="days_reward_per_30",
        )
    else:
        with op.batch_alter_table("promos") as batch:
            batch.alter_column("points_rewarded", new_column_name="days_rewarded")
        with op.batch_alter_table("promo_settings") as batch:
            batch.alter_column(
                "reward_cap_points",
                new_column_name="reward_cap_days",
            )
            batch.alter_column(
                "points_reward_per_30",
                new_column_name="days_reward_per_30",
            )

    op.execute(
        sa.text(
            f"UPDATE promos SET days_rewarded = days_rewarded / {MULTIPLIER}"
        )
    )
    op.execute(
        sa.text(
            f"UPDATE promo_settings SET reward_cap_days = reward_cap_days / {MULTIPLIER}"
        )
    )
    op.execute(
        sa.text(
            f"UPDATE promo_settings SET days_reward_per_30 = days_reward_per_30 / {MULTIPLIER}"
        )
    )

    if bind.dialect.name == "postgresql":
        op.alter_column(
            "promo_settings",
            "days_reward_per_30",
            server_default=sa.text("3"),
        )
        op.alter_column(
            "promo_settings",
            "reward_cap_days",
            server_default=sa.text("180"),
        )
    else:
        with op.batch_alter_table("promo_settings") as batch:
            batch.alter_column(
                "days_reward_per_30",
                server_default=sa.text("3"),
            )
            batch.alter_column(
                "reward_cap_days",
                server_default=sa.text("180"),
            )


def upgrade() -> None:
    _scale_and_rename_promo_settings()


def downgrade() -> None:
    _rename_back_promo_settings()
