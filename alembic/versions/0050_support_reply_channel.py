"""Route replies for Telegram support tickets through the support bot."""
from alembic import op
import sqlalchemy as sa

revision = "0050_support_reply_channel"
down_revision = "0049_web_payment_confirmation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("support_tickets", sa.Column("reply_channel", sa.String(20), nullable=False, server_default="miniapp"))


def downgrade():
    with op.batch_alter_table("support_tickets") as batch:
        batch.drop_column("reply_channel")
