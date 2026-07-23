"""Drop unique constraint on users tg_id

Revision ID: 0009_drop_users_tg_id_unique
Revises: 0008_fix_users_indices_and_types
Create Date: 2026-05-14
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0010_fix_varchar_size"
down_revision = "0009_drop_users_tg_id_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Увеличиваем лимит для invoice_tariff_slug
    with op.batch_alter_table("webapp_menu_nodes") as batch:
        batch.alter_column('invoice_tariff_slug',
                           existing_type=sa.String(length=50),
                           type_=sa.String(length=255),
                           existing_nullable=True)
        batch.alter_column('text',
                           existing_type=sa.String(length=200),
                           type_=sa.String(length=255),
                           existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("webapp_menu_nodes") as batch:
        batch.alter_column('invoice_tariff_slug',
                           existing_type=sa.String(length=255),
                           type_=sa.String(length=50))
