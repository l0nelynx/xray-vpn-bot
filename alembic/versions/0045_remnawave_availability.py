"""Persist Remnawave incidents, recovery subscriptions and pending notices."""
from alembic import op
import sqlalchemy as sa

revision = "0045_remnawave_availability"
down_revision = "0044_referral_recovery"
branch_labels = None
depends_on = None


def upgrade():
    state = op.create_table(
        "remnawave_availability",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("incident", sa.Integer(), nullable=False),
        sa.Column("unavailable", sa.Boolean(), nullable=False),
        sa.Column("next_probe_at", sa.Float(), nullable=False),
    )
    op.bulk_insert(state, [{"id": 1, "incident": 0, "unavailable": False, "next_probe_at": 0}])
    op.create_table(
        "remnawave_recovery_subscriptions",
        sa.Column("incident", sa.Integer(), primary_key=True),
        sa.Column("tg_id", sa.BigInteger(), primary_key=True),
        sa.Column("language", sa.String(2), nullable=False),
    )
    op.create_table(
        "remnawave_notices",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("admin", sa.Boolean(), nullable=False),
        sa.Column("tg_id", sa.BigInteger(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("next_attempt_at", sa.Float(), nullable=False),
    )


def downgrade():
    op.drop_table("remnawave_notices")
    op.drop_table("remnawave_recovery_subscriptions")
    op.drop_table("remnawave_availability")
