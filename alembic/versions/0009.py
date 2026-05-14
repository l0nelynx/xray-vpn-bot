"""Fix users tg_id unique constraint and integer sizes

Revision ID: 0008_fix_users_indices_and_types
Revises: 0007_fix_int_sizes
Create Date: 2026-05-14
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0008_fix_users_indices_and_types"
down_revision = "0007_fix_int_sizes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Удаляем ограничение уникальности с tg_id
    # Используем блок try/except или проверяем существование,
    # так как Postgres называет констреинты по-разному
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Пытаемся найти имя уникального ключа для колонки tg_id
    unique_constraints = insp.get_unique_constraints("users")
    for uc in unique_constraints:
        if "tg_id" in uc["column_names"]:
            op.drop_constraint(uc["name"], "users", type_="unique")

    # 2. На всякий случай убеждаемся, что tg_id и другие поля имеют тип BigInteger
    # Это предотвратит NumericValueOutOfRange для очень больших Telegram ID
    op.alter_column("users", "id",
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)

    op.alter_column("users", "tg_id",
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=True)


def downgrade() -> None:
    # Возвращаем BigInteger обратно в Integer (не рекомендуется, если данные большие)
    op.alter_column("users", "tg_id",
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=True)

    op.alter_column("users", "id",
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=False)

    # Возвращаем уникальность (может упасть, если в базе уже появились дубликаты)
    op.create_unique_constraint("users_tg_id_key", "users", ["tg_id"])