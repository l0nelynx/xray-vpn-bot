"""Drop unique constraint on users tg_id

Revision ID: 0009_drop_users_tg_id_unique
Revises: 0008_fix_users_indices_and_types
Create Date: 2026-05-14
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0009_drop_users_tg_id_unique"
down_revision = "0008_fix_support_users_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1. Ищем и удаляем Unique Constraint
    unique_constraints = insp.get_unique_constraints("users")
    for uc in unique_constraints:
        if "tg_id" in uc["column_names"]:
            op.drop_constraint(uc["name"], "users", type_="unique")
            print(f"Dropped unique constraint: {uc['name']}")

    # 2. На случай, если это не Constraint, а просто Unique Index
    indexes = insp.get_indexes("users")
    for idx in indexes:
        if idx["unique"] and "tg_id" in idx["column_names"]:
            op.drop_index(idx["name"], table_name="users")
            print(f"Dropped unique index: {idx['name']}")


def downgrade() -> None:
    # Возвращаем уникальность (может не сработать, если в базе уже дубликаты)
    op.create_unique_constraint("users_tg_id_key", "users", ["tg_id"])