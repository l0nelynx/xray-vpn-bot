"""Referral receipts, one-time recovery and durable Telegram notices.

Existing completed purchases are reserved for the reviewed recovery operation;
the live worker must never silently backfill them without the 10% compensation.
Deploy all payment services together so the old untracked reward path is stopped.
"""
import sqlalchemy as sa
from alembic import op

revision = "0044_referral_recovery"
down_revision = "0043_web_analytics"
branch_labels = None
depends_on = None


def upgrade():
    # Do not mark recovery initialized without reserving historical purchases.
    # Validate before DDL too: SQLite may not roll back CREATE TABLE on failure.
    if not op.get_context().as_sql:
        inspector = sa.inspect(op.get_bind())
        required = {"transaction_id", "delivery_status", "order_status", "payment_method"}
        if not inspector.has_table("transactions") or not required.issubset(
            {column["name"] for column in inspector.get_columns("transactions")}
        ):
            raise RuntimeError("Referral migration requires the existing transactions schema")
    op.create_table(
        "referral_receipts",
        sa.Column("transaction_id", sa.String(100), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("promo_code", sa.String(20)),
        sa.Column("points", sa.Integer(), nullable=False),
    )
    state = op.create_table(
        "referral_recovery",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("snapshot", sa.JSON()),
    )
    op.create_table(
        "referral_notices",
        sa.Column("key", sa.String(120), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("tg_id", sa.BigInteger()),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("claimed_at", sa.Float()),
        sa.Column("error", sa.String(200)),
    )
    op.bulk_insert(state, [{"id": 1, "status": "ready", "snapshot": None}])
    op.execute(sa.text(
        "INSERT INTO referral_receipts (transaction_id, kind, points) "
        "SELECT transaction_id, 'legacy', 0 FROM transactions "
        "WHERE (delivery_status = 1 AND order_status IN ('confirmed', 'delivered')) "
        "OR (payment_method = 'BONUS_CREDITS' AND order_status IN ('confirmed', 'pending'))"
    ))


def downgrade():
    op.drop_table("referral_notices")
    op.drop_table("referral_recovery")
    op.drop_table("referral_receipts")
