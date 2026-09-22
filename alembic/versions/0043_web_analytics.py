"""Durable GA4 purchase outbox."""
import sqlalchemy as sa
from alembic import op

revision = "0043_web_analytics"
down_revision = "0042_merge_support_branding"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "web_analytics_purchases",
        sa.Column("transaction_id", sa.String(100), sa.ForeignKey("transactions.transaction_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("confirmed_at", sa.Float(), nullable=True),
        sa.Column("sent_at", sa.Float(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.Float(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(50), nullable=True),
    )
    op.create_index("ix_web_analytics_purchases_next_attempt_at", "web_analytics_purchases", ["next_attempt_at"])


def downgrade():
    op.drop_table("web_analytics_purchases")
