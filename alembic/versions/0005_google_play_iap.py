"""google play subscription IAP.

Extends `google_play_purchases` with the fields needed for auto-renewing
subscriptions (state, linked_purchase_token, latest_notification_type,
auto_renewing, start_time, subscription_id) and adds an admin-managed
`google_play_skus` table that maps `product_id` -> (days, squad).

Revision ID: 0005_google_play_iap
Revises: 0004_android_invoices
Create Date: 2026-05-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_google_play_iap"
down_revision: Union[str, None] = "0004_android_invoices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("google_play_purchases") as batch:
        # Subscriptions are identified by `product_id` (the app SKU); the
        # base subscription id from v2 may differ when add-ons exist.
        batch.add_column(sa.Column("subscription_id", sa.String(100)))
        # `linked_purchase_token` chains the original purchase across
        # upgrades/downgrades & resubscriptions; lets us follow renewals.
        batch.add_column(sa.Column("linked_purchase_token", sa.String(512)))
        # State machine: ACTIVE | CANCELED | IN_GRACE_PERIOD | ON_HOLD |
        # PAUSED | EXPIRED | PENDING. Drives delivery decisions.
        batch.add_column(sa.Column("state", sa.String(32)))
        batch.add_column(sa.Column("auto_renewing", sa.Boolean(), server_default="0"))
        batch.add_column(sa.Column("start_time", sa.String(30)))
        # Last RTDN notification type observed for this token (int per
        # Google's enum). Mostly diagnostic.
        batch.add_column(sa.Column("latest_notification_type", sa.Integer()))

    op.create_index(
        "ix_google_play_purchases_state",
        "google_play_purchases",
        ["state"],
    )
    op.create_index(
        "ix_google_play_purchases_linked_token",
        "google_play_purchases",
        ["linked_purchase_token"],
    )

    op.create_table(
        "google_play_skus",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("product_id", sa.String(100), nullable=False, unique=True),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("squad_id", sa.String(100), nullable=False),
        sa.Column("external_squad_id", sa.String(100), nullable=False),
        # Optional human-readable label for admin UIs.
        sa.Column("display_name", sa.String(200)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.String(30)),
        sa.Column("updated_at", sa.String(30)),
    )


def downgrade() -> None:
    op.drop_table("google_play_skus")

    op.drop_index(
        "ix_google_play_purchases_linked_token",
        table_name="google_play_purchases",
    )
    op.drop_index(
        "ix_google_play_purchases_state",
        table_name="google_play_purchases",
    )
    with op.batch_alter_table("google_play_purchases") as batch:
        batch.drop_column("latest_notification_type")
        batch.drop_column("start_time")
        batch.drop_column("auto_renewing")
        batch.drop_column("state")
        batch.drop_column("linked_purchase_token")
        batch.drop_column("subscription_id")
