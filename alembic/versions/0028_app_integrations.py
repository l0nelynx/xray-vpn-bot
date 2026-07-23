"""0028: app_integrations (encrypted service credentials dual-source)."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028_app_integrations"
down_revision: Union[str, None] = "0027_runtime_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, table: str) -> bool:
    return table in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "app_integrations"):
        op.create_table(
            "app_integrations",
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
    if _has_table(bind, "app_integrations"):
        op.drop_table("app_integrations")
