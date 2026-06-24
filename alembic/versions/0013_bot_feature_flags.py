"""bot_feature_flags — feature flag table for bot_constructor toggle.

Adds a single-row ``bot_feature_flags`` table (id=1). The only current flag is
``legacy_bot_constructor`` which controls whether the in-bot tariff menus and
inline payment flow are registered on the aiogram dispatcher at startup.

Revision ID: 0013_bot_feature_flags
Revises: 0012_promo_redemptions
Create Date: 2026-06-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_bot_feature_flags"
down_revision: Union[str, None] = "0012_promo_redemptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, table: str) -> bool:
    return table in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "bot_feature_flags"):
        op.create_table(
            "bot_feature_flags",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "legacy_bot_constructor",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
        )
        op.execute(
            "INSERT INTO bot_feature_flags (id, legacy_bot_constructor) VALUES (1, false)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "bot_feature_flags"):
        op.drop_table("bot_feature_flags")
