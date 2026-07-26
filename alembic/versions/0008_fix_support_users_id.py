"""Fix support_users user_id size

Revision ID: 0008_fix_support_users_id
Revises: 0007_fix_int_sizes
"""
import sqlalchemy as sa
from alembic import op

revision = "0008_fix_support_users_id"
down_revision = "0007_fix_int_sizes"

def upgrade():
    with op.batch_alter_table("support_users") as batch:
        batch.alter_column("user_id",
                           existing_type=sa.Integer(),
                           type_=sa.BigInteger(),
                           existing_nullable=False)

def downgrade():
    with op.batch_alter_table("support_users") as batch:
        batch.alter_column("user_id",
                           existing_type=sa.BigInteger(),
                           type_=sa.Integer(),
                           existing_nullable=False)
