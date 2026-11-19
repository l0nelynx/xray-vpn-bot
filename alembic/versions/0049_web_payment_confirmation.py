"""Keep the invoiced currency and first payment confirmation on the transaction."""
from alembic import op
import sqlalchemy as sa

revision = "0049_web_payment_confirmation"
down_revision = "0048_crm_webhook_email"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("transactions", sa.Column("currency", sa.String(16)))
    op.add_column("transactions", sa.Column("payment_confirmed_at", sa.Float()))


def downgrade():
    with op.batch_alter_table("transactions") as batch:
        batch.drop_column("payment_confirmed_at")
        batch.drop_column("currency")
