"""android api schema (auth + payments).

Adds:
  - users.password_hash, users.password_updated_at, users.email_verified_at
  - users.tg_id becomes nullable (Android-only accounts have no Telegram link)
  - users.email gets a unique index (case-insensitive emails are normalised
    in code before write)
  - refresh_tokens table (rotating JWT refresh family)
  - email_verifications table (codes for verify / password-reset / email-change)
  - google_play_purchases table (replay-safe IAP receipts)
  - telegram_link_codes table (one-time codes for /link in the bot)

Revision ID: 0003_android_api
Revises: 0002_align_with_models
Create Date: 2026-05-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_android_api"
down_revision: Union[str, None] = "0002_align_with_models"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("password_hash", sa.String(255)))
        batch.add_column(sa.Column("password_updated_at", sa.String(30)))
        batch.add_column(sa.Column("email_verified_at", sa.String(30)))
        # tg_id may already be nullable in baseline (it is on production), but
        # batch_alter explicitly enforces it for fresh DBs.
        batch.alter_column("tg_id", existing_type=sa.BigInteger(), nullable=True)

    op.create_index(
        "ix_users_email_unique", "users", ["email"], unique=True
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("family_id", sa.String(36), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("issued_at", sa.String(30), nullable=False),
        sa.Column("expires_at", sa.String(30), nullable=False),
        sa.Column("revoked_at", sa.String(30)),
        sa.Column("replaced_by_id", sa.Integer()),
        sa.Column("user_agent", sa.String(255)),
        sa.Column("ip", sa.String(64)),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index(
        "ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"]
    )

    op.create_table(
        "email_verifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # 'verify' | 'password_reset' | 'email_change'
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("code_hash", sa.String(128), nullable=False),
        # for email_change: the new email, validated on confirm
        sa.Column("payload", sa.String(255)),
        sa.Column("created_at", sa.String(30), nullable=False),
        sa.Column("expires_at", sa.String(30), nullable=False),
        sa.Column("used_at", sa.String(30)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_email_verifications_user_id_purpose",
        "email_verifications",
        ["user_id", "purpose"],
    )

    op.create_table(
        "google_play_purchases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("product_id", sa.String(100), nullable=False),
        sa.Column("purchase_token", sa.String(512), nullable=False, unique=True),
        sa.Column("order_id", sa.String(100)),
        sa.Column("expiry_time", sa.String(30)),
        sa.Column(
            "acknowledged",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("raw_payload", sa.Text()),
        sa.Column("created_at", sa.String(30), nullable=False),
        sa.Column("updated_at", sa.String(30), nullable=False),
    )
    op.create_index(
        "ix_google_play_purchases_user_id",
        "google_play_purchases",
        ["user_id"],
    )

    op.create_table(
        "telegram_link_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("created_at", sa.String(30), nullable=False),
        sa.Column("expires_at", sa.String(30), nullable=False),
        sa.Column("used_at", sa.String(30)),
        sa.Column("used_by_tg_id", sa.BigInteger()),
    )
    op.create_index(
        "ix_telegram_link_codes_user_id",
        "telegram_link_codes",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_telegram_link_codes_user_id", table_name="telegram_link_codes"
    )
    op.drop_table("telegram_link_codes")

    op.drop_index(
        "ix_google_play_purchases_user_id", table_name="google_play_purchases"
    )
    op.drop_table("google_play_purchases")

    op.drop_index(
        "ix_email_verifications_user_id_purpose",
        table_name="email_verifications",
    )
    op.drop_table("email_verifications")

    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_users_email_unique", table_name="users")

    with op.batch_alter_table("users") as batch:
        batch.drop_column("email_verified_at")
        batch.drop_column("password_updated_at")
        batch.drop_column("password_hash")
