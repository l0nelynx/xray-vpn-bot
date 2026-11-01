"""Track CRM recipients independently of a linked Telegram account."""
from alembic import op
import sqlalchemy as sa

revision = "0047_crm_email_recipients"
down_revision = "0046_localized_payment_order"
branch_labels = None
depends_on = None

TABLES = (
    ("crm_campaign_deliveries", "campaign_id"),
    ("crm_event_deliveries", "event_id"),
    ("crm_webhook_deliveries", "rule_id"),
)


def upgrade():
    for table, owner in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("user_id", sa.BigInteger(), nullable=True))
            batch.alter_column("tg_id", existing_type=sa.BigInteger(), nullable=True)
            batch.create_index(f"ix_{table}_user", [owner, "user_id"])
        op.execute(sa.text(
            f"UPDATE {table} SET user_id = (SELECT MIN(users.id) FROM users WHERE users.tg_id = {table}.tg_id)"
        ))


def downgrade():
    # Restoring NOT NULL intentionally fails if email-only history still exists.
    for table, owner in reversed(TABLES):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_user")
            batch.alter_column("tg_id", existing_type=sa.BigInteger(), nullable=False)
            batch.drop_column("user_id")
