"""crm_events + crm_event_deliveries; crm_campaigns.event_id.

Revision ID: 0017_crm_events
Revises: 0016_users_rw_id
Create Date: 2026-07-14
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_crm_events"
down_revision: Union[str, None] = "0016_users_rw_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, table: str) -> bool:
    return table in sa.inspect(bind).get_table_names()


def _has_column(bind, table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "crm_events"):
        op.create_table(
            "crm_events",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(200), nullable=False, server_default=""),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("segment_type", sa.String(50), nullable=True),
            sa.Column("segment_params", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("run_at_time", sa.String(5), nullable=False, server_default="01:00"),
            sa.Column("frequency", sa.String(20), nullable=False, server_default="daily"),
            sa.Column("weekday", sa.Integer(), nullable=True),
            sa.Column("message_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("attach_button", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("bonus_days", sa.Integer(), nullable=True),
            sa.Column("bonus_traffic_gb", sa.Integer(), nullable=True),
            sa.Column("repeat_policy", sa.String(20), nullable=False, server_default="cooldown"),
            sa.Column("repeat_cooldown_days", sa.Integer(), nullable=False, server_default="7"),
            sa.Column("last_run_at", sa.String(30), nullable=True),
            sa.Column("next_run_at", sa.String(30), nullable=True),
            sa.Column("created_at", sa.String(30), nullable=False),
            sa.Column("updated_at", sa.String(30), nullable=False),
            sa.Column("created_by", sa.String(100), nullable=False, server_default=""),
        )
        op.create_index("ix_crm_events_enabled", "crm_events", ["enabled"])
        op.create_index("ix_crm_events_next_run_at", "crm_events", ["next_run_at"])

    if not _has_table(bind, "crm_event_deliveries"):
        op.create_table(
            "crm_event_deliveries",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "event_id",
                sa.BigInteger(),
                sa.ForeignKey("crm_events.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("tg_id", sa.BigInteger(), nullable=False),
            sa.Column("sent_at", sa.String(30), nullable=False),
        )
        op.create_index("ix_crm_event_deliveries_event_id", "crm_event_deliveries", ["event_id"])
        op.create_index("ix_crm_event_deliveries_tg_id", "crm_event_deliveries", ["tg_id"])
        op.create_index(
            "ix_crm_event_deliveries_event_tg",
            "crm_event_deliveries",
            ["event_id", "tg_id"],
        )

    if _has_table(bind, "crm_campaigns") and not _has_column(bind, "crm_campaigns", "event_id"):
        with op.batch_alter_table("crm_campaigns") as batch:
            batch.add_column(sa.Column("event_id", sa.BigInteger(), nullable=True))
            batch.create_foreign_key(
                "fk_crm_campaigns_event_id",
                "crm_events",
                ["event_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch.create_index("ix_crm_campaigns_event_id", ["event_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "crm_campaigns") and _has_column(bind, "crm_campaigns", "event_id"):
        with op.batch_alter_table("crm_campaigns") as batch:
            batch.drop_index("ix_crm_campaigns_event_id")
            batch.drop_constraint(
                "fk_crm_campaigns_event_id", type_="foreignkey"
            )
            batch.drop_column("event_id")
    if _has_table(bind, "crm_event_deliveries"):
        op.drop_table("crm_event_deliveries")
    if _has_table(bind, "crm_events"):
        op.drop_table("crm_events")
