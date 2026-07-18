"""0024: crm_webhook_rules + crm_webhook_deliveries."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024_crm_webhook_rules"
down_revision: Union[str, None] = "0023_android_fcm_push"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, table: str) -> bool:
    return table in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "crm_webhook_rules"):
        op.create_table(
            "crm_webhook_rules",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(200), nullable=False, server_default=""),
            sa.Column(
                "enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
            ),
            sa.Column("scope", sa.String(50), nullable=False, server_default=""),
            sa.Column("event", sa.String(100), nullable=False, server_default=""),
            sa.Column("actions_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("cooldown_hours", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.String(30), nullable=False),
            sa.Column("updated_at", sa.String(30), nullable=False),
            sa.Column("created_by", sa.String(100), nullable=False, server_default=""),
        )
        op.create_index("ix_crm_webhook_rules_enabled", "crm_webhook_rules", ["enabled"])
        op.create_index(
            "ix_crm_webhook_rules_scope_event",
            "crm_webhook_rules",
            ["scope", "event"],
        )

    if not _has_table(bind, "crm_webhook_deliveries"):
        op.create_table(
            "crm_webhook_deliveries",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "rule_id",
                sa.BigInteger(),
                sa.ForeignKey("crm_webhook_rules.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("tg_id", sa.BigInteger(), nullable=False),
            sa.Column("sent_at", sa.String(30), nullable=False),
        )
        op.create_index(
            "ix_crm_webhook_deliveries_rule_id", "crm_webhook_deliveries", ["rule_id"]
        )
        op.create_index(
            "ix_crm_webhook_deliveries_tg_id", "crm_webhook_deliveries", ["tg_id"]
        )
        op.create_index(
            "ix_crm_webhook_deliveries_rule_tg",
            "crm_webhook_deliveries",
            ["rule_id", "tg_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "crm_webhook_deliveries"):
        op.drop_table("crm_webhook_deliveries")
    if _has_table(bind, "crm_webhook_rules"):
        op.drop_table("crm_webhook_rules")
