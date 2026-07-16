"""0022: Telemt free-user default rate limits (up/down bps)."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_telemt_free_rate_limits"
down_revision: Union[str, None] = "0021_referral_owner_points"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "telemt_free_params",
        sa.Column("rate_limit_up_bps", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "telemt_free_params",
        sa.Column("rate_limit_down_bps", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("telemt_free_params", "rate_limit_down_bps")
    op.drop_column("telemt_free_params", "rate_limit_up_bps")
