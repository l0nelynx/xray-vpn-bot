"""0025: CRM webhook rule counters (received / messages sent / failed)."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025_crm_webhook_stats"
down_revision: Union[str, None] = "0024_crm_webhook_rules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, table: str) -> bool:
    return table in sa.inspect(bind).get_table_names()


def _has_column(bind, table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "crm_webhook_rules"):
        return
    with op.batch_alter_table("crm_webhook_rules") as batch:
        if not _has_column(bind, "crm_webhook_rules", "webhooks_received"):
            batch.add_column(
                sa.Column(
                    "webhooks_received",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                )
            )
        if not _has_column(bind, "crm_webhook_rules", "messages_sent"):
            batch.add_column(
                sa.Column(
                    "messages_sent",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                )
            )
        if not _has_column(bind, "crm_webhook_rules", "messages_failed"):
            batch.add_column(
                sa.Column(
                    "messages_failed",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "crm_webhook_rules"):
        return
    with op.batch_alter_table("crm_webhook_rules") as batch:
        if _has_column(bind, "crm_webhook_rules", "messages_failed"):
            batch.drop_column("messages_failed")
        if _has_column(bind, "crm_webhook_rules", "messages_sent"):
            batch.drop_column("messages_sent")
        if _has_column(bind, "crm_webhook_rules", "webhooks_received"):
            batch.drop_column("webhooks_received")
