"""Cooldown tracking for webhook email recipients without local accounts."""
from alembic import op
import sqlalchemy as sa

revision = "0048_crm_webhook_email"
down_revision = "0047_crm_email_recipients"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("crm_webhook_deliveries") as batch:
        batch.add_column(sa.Column("recipient_email", sa.String(320), nullable=True))
        batch.create_index("ix_crm_webhook_deliveries_email", ["rule_id", "recipient_email"])


def downgrade():
    with op.batch_alter_table("crm_webhook_deliveries") as batch:
        batch.drop_index("ix_crm_webhook_deliveries_email")
        batch.drop_column("recipient_email")
