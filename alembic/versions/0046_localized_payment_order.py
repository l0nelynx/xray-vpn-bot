"""Independent RU/EN payment-option positions in the tariff constructor."""
from alembic import op
import sqlalchemy as sa

revision = "0046_localized_payment_order"
down_revision = "0045_remnawave_availability"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("webapp_menu_nodes", sa.Column("sort_order_ru", sa.Integer(), nullable=True))
    op.add_column("webapp_menu_nodes", sa.Column("sort_order_en", sa.Integer(), nullable=True))
    # Preserve the current invoice order in both languages, within each parent.
    op.execute(sa.text("""
        WITH positions AS (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY parent_id ORDER BY sort_order, id
            ) - 1 AS position
            FROM webapp_menu_nodes WHERE action = 'invoice'
        )
        UPDATE webapp_menu_nodes
        SET sort_order_ru = (SELECT position FROM positions WHERE positions.id = webapp_menu_nodes.id),
            sort_order_en = (SELECT position FROM positions WHERE positions.id = webapp_menu_nodes.id)
        WHERE action = 'invoice'
    """))


def downgrade():
    with op.batch_alter_table("webapp_menu_nodes") as batch:
        batch.drop_column("sort_order_en")
        batch.drop_column("sort_order_ru")
