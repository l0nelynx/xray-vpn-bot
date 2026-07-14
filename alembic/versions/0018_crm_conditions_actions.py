"""CRM conditions_json + actions_json on campaigns and events.

Revision ID: 0018_crm_conditions_actions
Revises: 0017_crm_events
Create Date: 2026-07-14
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_crm_conditions_actions"
down_revision: Union[str, None] = "0017_crm_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind, table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _flat_to_conditions(segment_type, segment_params_raw):
    try:
        params = json.loads(segment_params_raw or "{}")
    except json.JSONDecodeError:
        params = {}
    if not segment_type:
        return []
    user_type = params.pop("user_type", None)
    target_tg_ids = params.pop("target_tg_ids", None)
    conditions = [
        {"type": "segment", "segment_id": segment_type, "params": params}
    ]
    if user_type and user_type != "all":
        conditions.append({"type": "user_type", "value": user_type})
    if target_tg_ids:
        conditions.append({"type": "tg_allowlist", "tg_ids": list(target_tg_ids)})
    return conditions


def _flat_to_actions(message_text, attach_button, bonus_days, bonus_traffic_gb):
    actions = []
    order = 1
    if bonus_days and bonus_days > 0:
        actions.append(
            {"type": "rw_bonus_days", "enabled": True, "order": order, "days": bonus_days}
        )
        order += 1
    if bonus_traffic_gb and bonus_traffic_gb > 0:
        actions.append(
            {
                "type": "rw_bonus_traffic",
                "enabled": True,
                "order": order,
                "gb": bonus_traffic_gb,
            }
        )
        order += 1
    if message_text and str(message_text).strip():
        actions.append(
            {
                "type": "send_message",
                "enabled": True,
                "order": order,
                "text": message_text,
            }
        )
        order += 1
    if attach_button:
        actions.append(
            {
                "type": "attach_button",
                "enabled": True,
                "order": order,
                "button_type": "open_bot",
            }
        )
    return actions


def _backfill_table(table: str) -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            f"SELECT id, segment_type, segment_params, message_text, attach_button, "
            f"bonus_days, bonus_traffic_gb FROM {table}"
        )
    ).fetchall()
    for row in rows:
        conditions = _flat_to_conditions(row.segment_type, row.segment_params)
        actions = _flat_to_actions(
            row.message_text,
            row.attach_button,
            row.bonus_days,
            row.bonus_traffic_gb,
        )
        bind.execute(
            sa.text(
                f"UPDATE {table} SET conditions_json = :c, actions_json = :a WHERE id = :id"
            ),
            {
                "c": json.dumps(conditions, ensure_ascii=False),
                "a": json.dumps(actions, ensure_ascii=False),
                "id": row.id,
            },
        )


def upgrade() -> None:
    bind = op.get_bind()
    for table in ("crm_campaigns", "crm_events"):
        if not _has_column(bind, table, "conditions_json"):
            op.add_column(
                table,
                sa.Column(
                    "conditions_json",
                    sa.Text(),
                    nullable=False,
                    server_default="[]",
                ),
            )
        if not _has_column(bind, table, "actions_json"):
            op.add_column(
                table,
                sa.Column(
                    "actions_json",
                    sa.Text(),
                    nullable=False,
                    server_default="[]",
                ),
            )
        _backfill_table(table)


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("crm_campaigns", "crm_events"):
        if _has_column(bind, table, "actions_json"):
            op.drop_column(table, "actions_json")
        if _has_column(bind, table, "conditions_json"):
            op.drop_column(table, "conditions_json")
