"""android-api invoice link.

Adds `transactions.android_user_id` so external-payment webhooks can resolve
an Android-only user (no `tg_id`). Existing Telegram-bot invoices keep using
`user_id` (FK to users.id via tg_id resolution) — both columns are nullable;
the delivery code chooses based on whichever is set.

Revision ID: 0004_android_invoices
Revises: 0003_android_api
Create Date: 2026-05-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_android_invoices"
down_revision: Union[str, None] = "0003_android_api"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("transactions") as batch:
        batch.add_column(sa.Column("android_user_id", sa.Integer(), nullable=True))

    op.create_index(
        "ix_transactions_android_user_id",
        "transactions",
        ["android_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_transactions_android_user_id", table_name="transactions"
    )
    with op.batch_alter_table("transactions") as batch:
        batch.drop_column("android_user_id")
