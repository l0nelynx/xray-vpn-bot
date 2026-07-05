"""support_attachments — up to 3 images per support-ticket reply.

Adds support_attachments (1:N -> support_messages, ON DELETE CASCADE). Images
are stored on local disk under a bind-mounted directory shared by the miniapp
and dashboard containers (see docs/deployment.md); this table only tracks
metadata and a relative on-disk path — never an absolute filesystem path.

Revision ID: 0014_support_attachments
Revises: 0013_bot_feature_flags
Create Date: 2026-07-05
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_support_attachments"
down_revision: Union[str, None] = "0013_bot_feature_flags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, table: str) -> bool:
    return table in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "support_attachments"):
        op.create_table(
            "support_attachments",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "message_id",
                sa.BigInteger(),
                sa.ForeignKey("support_messages.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("original_filename", sa.String(255), nullable=False),
            sa.Column("stored_path", sa.String(500), nullable=False),
            sa.Column("mime_type", sa.String(100), nullable=False),
            sa.Column("size_bytes", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.String(30), nullable=False),
        )
        op.create_index(
            "ix_support_attachments_message_id",
            "support_attachments",
            ["message_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "support_attachments"):
        op.drop_table("support_attachments")
