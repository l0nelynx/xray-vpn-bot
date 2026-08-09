"""Add application API health telemetry.

Revision ID: 0037_api_health
Revises: 0036_crm_delivery_rw_id
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0037_api_health"
down_revision: Union[str, None] = "0036_crm_delivery_rw_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _metric_table(name: str, unique_name: str) -> None:
    op.create_table(
        name,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bucket_start", sa.String(30), nullable=False),
        sa.Column("service", sa.String(24), nullable=False),
        sa.Column("method", sa.String(12), nullable=False),
        sa.Column("route", sa.String(255), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("request_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("duration_sum_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("duration_max_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("request_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("response_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("histogram_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("dropped_events", sa.BigInteger(), nullable=False, server_default="0"),
        sa.UniqueConstraint("bucket_start", "service", "method", "route", "status_code", name=unique_name),
    )
    op.create_index(f"ix_{name}_bucket", name, ["bucket_start"])
    op.create_index(f"ix_{name}_service_bucket", name, ["service", "bucket_start"])


def upgrade() -> None:
    _metric_table("api_metric_minutes", "ux_api_metric_minute_key")
    _metric_table("api_metric_hours", "ux_api_metric_hour_key")
    op.create_table(
        "api_error_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("occurred_at", sa.String(30), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False, unique=True),
        sa.Column("service", sa.String(24), nullable=False),
        sa.Column("method", sa.String(12), nullable=False),
        sa.Column("route", sa.String(255), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("user_id", sa.BigInteger()), sa.Column("tg_id", sa.BigInteger()),
        sa.Column("actor", sa.String(100)), sa.Column("client_ip", sa.String(64)),
        sa.Column("client_channel", sa.String(24)), sa.Column("user_agent", sa.String(512)),
        sa.Column("app_version", sa.String(64)),
        sa.Column("request_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("response_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("exception_type", sa.String(255)), sa.Column("error_message", sa.Text()),
        sa.Column("error_fingerprint", sa.String(64), nullable=False), sa.Column("traceback", sa.Text()),
    )
    for name, cols in {
        "ix_api_errors_occurred": ["occurred_at"], "ix_api_errors_service_occurred": ["service", "occurred_at"],
        "ix_api_errors_route_occurred": ["route", "occurred_at"], "ix_api_errors_status_occurred": ["status_code", "occurred_at"],
        "ix_api_errors_user": ["user_id"], "ix_api_errors_tg": ["tg_id"], "ix_api_errors_ip": ["client_ip"],
        "ix_api_errors_fingerprint": ["error_fingerprint"],
    }.items(): op.create_index(name, "api_error_events", cols)
    op.create_table(
        "api_service_status", sa.Column("service", sa.String(24), primary_key=True),
        sa.Column("is_healthy", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("checked_at", sa.String(30), nullable=False), sa.Column("last_ok_at", sa.String(30)),
        sa.Column("last_error", sa.String(500)), sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("response_time_ms", sa.Float()),
    )
    op.create_table(
        "api_alert_state", sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_sent_at", sa.String(30)), sa.Column("last_value", sa.Float()),
        sa.Column("updated_at", sa.String(30), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("api_alert_state"); op.drop_table("api_service_status"); op.drop_table("api_error_events")
    op.drop_table("api_metric_hours"); op.drop_table("api_metric_minutes")
