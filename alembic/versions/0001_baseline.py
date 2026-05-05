"""baseline schema (matches production DB pre-Alembic).

This revision describes the schema that already exists on running deployments
just before Alembic is wired in. On those DBs run `alembic stamp 0001_baseline`
once; on a fresh DB `alembic upgrade head` will create everything from scratch.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tg_id", sa.BigInteger(), unique=True),
        sa.Column("username", sa.String(100)),
        sa.Column("vless_uuid", sa.String(100)),
        sa.Column("api_provider", sa.String(50), server_default="marzban"),
        sa.Column("is_banned", sa.Boolean(), server_default="0"),
        sa.Column("email", sa.String(100)),
        sa.Column("language", sa.String(5), server_default="ru"),
        sa.Column("vip", sa.Integer(), server_default="0"),
    )
    op.create_index("ix_user_username", "users", ["username"])

    op.create_table(
        "promos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tg_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("promo_code", sa.String(20), nullable=False, unique=True),
        sa.Column("used_promo", sa.String(20)),
        sa.Column("days_purchased", sa.Integer(), nullable=False),
        sa.Column("days_rewarded", sa.Integer(), nullable=False),
    )

    op.create_table(
        "transactions",
        sa.Column("transaction_id", sa.String(100), primary_key=True),
        sa.Column("vless_uuid", sa.String(100), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("order_status", sa.String(50), nullable=False),
        sa.Column("delivery_status", sa.Integer(), nullable=False),
        sa.Column("days_ordered", sa.BigInteger(), nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("payment_method", sa.String(50)),
        sa.Column("amount", sa.Float()),
        sa.Column("created_at", sa.String(30)),
        sa.Column("expire_date", sa.String(30)),
    )
    op.create_index("ix_transaction_user_id", "transactions", ["user_id"])

    op.create_table(
        "disabled_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tg_id", sa.BigInteger(), unique=True),
        sa.Column("original_status", sa.String(20), nullable=False),
        sa.Column("disabled_at", sa.String(30), nullable=False),
    )

    op.create_table(
        "cache_version",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
    )

    op.create_table(
        "squad_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("squad_id", sa.String(100), nullable=False),
        sa.Column("external_squad_id", sa.String(100), nullable=False),
    )

    op.create_table(
        "tariff_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(50), nullable=False, unique=True),
        sa.Column("name_ru", sa.String(100), nullable=False),
        sa.Column("name_en", sa.String(100), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("discount_percent", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(30)),
        sa.Column("squad_profile_id", sa.Integer(), sa.ForeignKey("squad_profiles.id")),
    )

    op.create_table(
        "tariff_prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tariff_id",
            sa.Integer(),
            sa.ForeignKey("tariff_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("payment_method", sa.String(30), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("tariff_id", "payment_method", name="uq_tariff_payment"),
    )

    op.create_table(
        "menu_screens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("message_text_ru", sa.Text()),
        sa.Column("message_text_en", sa.Text()),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )

    op.create_table(
        "menu_buttons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "screen_id",
            sa.Integer(),
            sa.ForeignKey("menu_screens.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text_ru", sa.String(200), nullable=False),
        sa.Column("text_en", sa.String(200), nullable=False),
        sa.Column("callback_data", sa.String(100)),
        sa.Column("url", sa.String(500)),
        sa.Column("row", sa.Integer(), nullable=False),
        sa.Column("col", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("button_type", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("visibility_condition", sa.String(50), nullable=False),
    )

    op.create_table(
        "telemt_free_params",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("max_tcp_conns", sa.Integer()),
        sa.Column("max_unique_ips", sa.Integer()),
        sa.Column("data_quota_bytes", sa.BigInteger()),
        sa.Column("expire_days", sa.Integer(), nullable=False),
    )

    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("username", sa.String(100)),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.String(30), nullable=False),
        sa.Column("updated_at", sa.String(30), nullable=False),
    )
    op.create_index("ix_support_tickets_user_id", "support_tickets", ["user_id"])
    op.create_index("ix_support_tickets_status", "support_tickets", ["status"])

    op.create_table(
        "support_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "ticket_id",
            sa.Integer(),
            sa.ForeignKey("support_tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sender", sa.String(20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(30), nullable=False),
    )
    op.create_index("ix_support_messages_ticket_id", "support_messages", ["ticket_id"])

    op.create_table(
        "webapp_menu_nodes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey("webapp_menu_nodes.id", ondelete="CASCADE"),
        ),
        sa.Column("text", sa.String(200), nullable=False),
        sa.Column("action", sa.String(20), nullable=False, server_default="buttons"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("invoice_provider", sa.String(30)),
        sa.Column("invoice_amount", sa.Float()),
        sa.Column("invoice_currency", sa.String(10)),
        sa.Column("invoice_days", sa.Integer()),
        sa.Column("invoice_tariff_slug", sa.String(50)),
    )
    op.create_index(
        "ix_webapp_menu_nodes_parent_id", "webapp_menu_nodes", ["parent_id"]
    )

    op.create_table(
        "support_users",
        sa.Column("user_id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.Text()),
        sa.Column("full_name", sa.Text()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_table("support_users")
    op.drop_index("ix_webapp_menu_nodes_parent_id", table_name="webapp_menu_nodes")
    op.drop_table("webapp_menu_nodes")
    op.drop_index("ix_support_messages_ticket_id", table_name="support_messages")
    op.drop_table("support_messages")
    op.drop_index("ix_support_tickets_status", table_name="support_tickets")
    op.drop_index("ix_support_tickets_user_id", table_name="support_tickets")
    op.drop_table("support_tickets")
    op.drop_table("telemt_free_params")
    op.drop_table("menu_buttons")
    op.drop_table("menu_screens")
    op.drop_table("tariff_prices")
    op.drop_table("tariff_plans")
    op.drop_table("squad_profiles")
    op.drop_table("cache_version")
    op.drop_table("disabled_users")
    op.drop_index("ix_transaction_user_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("promos")
    op.drop_index("ix_user_username", table_name="users")
    op.drop_table("users")
