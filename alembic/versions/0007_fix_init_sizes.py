"""Fix integer sizes for Postgres compatibility (INT to BIGINT)

Revision ID: 0007_fix_int_sizes
Revises: 0006_postgres_compat
Create Date: 2026-05-14
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0007_fix_int_sizes"
down_revision = "0006_postgres_compat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Таблица users: переводим PK и поле vip (на случай больших значений)
    with op.batch_alter_table("users") as batch:
        batch.alter_column("id",
                           existing_type=sa.Integer(),
                           type_=sa.BigInteger(),
                           existing_nullable=False)
        batch.alter_column("vip",
                           existing_type=sa.Integer(),
                           type_=sa.BigInteger(),
                           existing_nullable=True)

    # 2. Таблица support_tickets: переводим PK и FK на пользователя
    with op.batch_alter_table("support_tickets") as batch:
        batch.alter_column("id",
                           existing_type=sa.Integer(),
                           type_=sa.BigInteger(),
                           existing_nullable=False)
        batch.alter_column("user_id",
                           existing_type=sa.Integer(),
                           type_=sa.BigInteger(),
                           existing_nullable=False)

    # 3. Таблица support_messages: переводим FK на тикет
    # (id там уже BigInteger по версии 0006)
    with op.batch_alter_table("support_messages") as batch:
        batch.alter_column("ticket_id",
                           existing_type=sa.Integer(),
                           type_=sa.BigInteger(),
                           existing_nullable=False)

    with op.batch_alter_table("support_users") as batch:
        batch.alter_column("user_id",
                           existing_type=sa.Integer(),
                           type_=sa.BigInteger(),
                           existing_nullable=False)

    # 4. Таблица tariff_plans: если есть FK на внешние профили
    # Проверяем наличие колонки перед изменением (согласно вашему стилю)
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = [c["name"] for c in insp.get_columns("tariff_plans")]

    if "squad_profile_id" in columns:
        with op.batch_alter_table("tariff_plans") as batch:
            batch.alter_column("squad_profile_id",
                               existing_type=sa.Integer(),
                               type_=sa.BigInteger(),
                               existing_nullable=True)



def downgrade() -> None:
    # Возврат к Integer (может вызвать ошибку, если данные уже превышают лимит)
    with op.batch_alter_table("support_messages") as batch:
        batch.alter_column("ticket_id",
                           existing_type=sa.BigInteger(),
                           type_=sa.Integer(),
                           existing_nullable=False)

    with op.batch_alter_table("support_tickets") as batch:
        batch.alter_column("user_id",
                           existing_type=sa.BigInteger(),
                           type_=sa.Integer(),
                           existing_nullable=False)
        batch.alter_column("id",
                           existing_type=sa.BigInteger(),
                           type_=sa.Integer(),
                           existing_nullable=False)

    with op.batch_alter_table("users") as batch:
        batch.alter_column("vip",
                           existing_type=sa.BigInteger(),
                           type_=sa.Integer(),
                           existing_nullable=True)
        batch.alter_column("id",
                           existing_type=sa.BigInteger(),
                           type_=sa.Integer(),
                           existing_nullable=False)
    with op.batch_alter_table("support_users") as batch:
        batch.alter_column("user_id",
                           existing_type=sa.BigInteger(),
                           type_=sa.Integer(),
                           existing_nullable=False)
