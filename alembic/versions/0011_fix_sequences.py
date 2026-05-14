"""Drop unique constraint on users tg_id

Revision ID: 0009_drop_users_tg_id_unique
Revises: 0008_fix_users_indices_and_types
Create Date: 2026-05-14
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0011_fix_sequences"
down_revision = "0010_fix_varchar_size"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Изменяем тип последовательностей на BIGINT
    op.execute("ALTER SEQUENCE support_users_user_id_seq AS BIGINT")
    # Если у таблицы users тоже были большие ID
    op.execute("ALTER SEQUENCE users_id_seq AS BIGINT")
    op.execute("ALTER SEQUENCE support_tickets_id_seq AS BIGINT")

def downgrade() -> None:
    op.execute("ALTER SEQUENCE support_users_user_id_seq AS INTEGER")