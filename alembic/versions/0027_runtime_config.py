"""0027: app_runtime_settings + payment_integrations (dual-source config)."""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027_runtime_config"
down_revision: Union[str, None] = "0026_giveaways"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_RUNTIME = {
    "maintenance": {
        "enabled": False,
        "title": "Технические работы",
        "text": "Сервис временно недоступен. Попробуйте позже.",
    }
}


def _has_table(bind, table: str) -> bool:
    return table in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "app_runtime_settings"):
        op.create_table(
            "app_runtime_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "config_json",
                sa.Text(),
                nullable=False,
                server_default="{}",
            ),
            sa.Column("updated_at", sa.String(30), nullable=True),
            sa.Column("updated_by", sa.String(100), nullable=True),
        )
        op.execute(
            sa.text(
                "INSERT INTO app_runtime_settings (id, config_json, updated_by) "
                "VALUES (1, :cfg, 'migration')"
            ).bindparams(cfg=json.dumps(_DEFAULT_RUNTIME, ensure_ascii=False))
        )

    if not _has_table(bind, "payment_integrations"):
        op.create_table(
            "payment_integrations",
            sa.Column("provider", sa.String(32), primary_key=True),
            sa.Column(
                "enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "managed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "encrypted_config",
                sa.Text(),
                nullable=False,
                server_default="",
            ),
            sa.Column("updated_at", sa.String(30), nullable=True),
            sa.Column("updated_by", sa.String(100), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "payment_integrations"):
        op.drop_table("payment_integrations")
    if _has_table(bind, "app_runtime_settings"):
        op.drop_table("app_runtime_settings")
