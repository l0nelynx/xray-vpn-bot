"""Run Base.metadata.create_all on an in-memory sqlite engine.

This is a coarse but fast end-to-end smoke: it confirms every column type,
FK, and index in common_db.models is at least syntactically valid for a
real engine. PG-only nuances (BigInteger sequences, enum types, etc.) are
covered in step 6 by an integration test against staging.
"""
from __future__ import annotations

from sqlalchemy import create_engine, inspect

from common_db import Base
import common_db.models  # noqa: F401  (registers models on Base.metadata)


def test_create_all_succeeds() -> None:
    engine = create_engine("sqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        insp = inspect(engine)
        tables = set(insp.get_table_names())

        # Spot-check critical tables made it in.
        assert {
            "users",
            "user_subscriptions",
            "subscription_transfers",
            "web_authorization_codes",
            "support_tickets",
            "support_messages",
            "transactions",
            "api_metric_minutes",
            "api_metric_hours",
            "api_error_events",
            "api_service_status",
            "api_alert_state",
        } <= tables

        # Spot-check critical indexes survived create_all.
        ticket_indexes = {ix["name"] for ix in insp.get_indexes("support_tickets")}
        assert "ix_support_tickets_user_id" in ticket_indexes
        assert "ix_support_tickets_status" in ticket_indexes

        msg_indexes = {ix["name"] for ix in insp.get_indexes("support_messages")}
        assert "ix_support_messages_ticket_id" in msg_indexes

        user_indexes = {ix["name"] for ix in insp.get_indexes("users")}
        assert "ix_user_username" in user_indexes
        assert "ix_users_email_unique" in user_indexes
        assert "ux_users_rw_id" in user_indexes

        subscription_indexes = {
            ix["name"] for ix in insp.get_indexes("user_subscriptions")
        }
        assert "ux_user_subscriptions_rw_id" in subscription_indexes
        assert "ux_user_subscriptions_primary" in subscription_indexes

        transfer_indexes = {
            ix["name"] for ix in insp.get_indexes("subscription_transfers")
        }
        assert "ux_subscription_transfers_source_rw_id" in transfer_indexes
        assert "ix_subscription_transfers_user_id" in transfer_indexes

        # FK from support_messages.ticket_id -> support_tickets.id with CASCADE.
        fks = insp.get_foreign_keys("support_messages")
        cascade_fk = [
            fk
            for fk in fks
            if fk["referred_table"] == "support_tickets"
            and "ticket_id" in fk["constrained_columns"]
        ]
        assert len(cascade_fk) == 1
        # SQLAlchemy preserves ON DELETE on FK options dict.
        assert cascade_fk[0].get("options", {}).get("ondelete") == "CASCADE"
    finally:
        engine.dispose()


def test_metadata_round_trip_reflects_columns() -> None:
    engine = create_engine("sqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        insp = inspect(engine)

        users_cols = {c["name"]: c for c in insp.get_columns("users")}
        # All the additions from later alembic revisions must be there.
        for required in (
            "id",
            "tg_id",
            "username",
            "vless_uuid",
            "rw_id",
            "api_provider",
            "email",
            "is_banned",
            "language",
            "vip",
            "password_hash",
            "password_updated_at",
            "email_verified_at",
        ):
            assert required in users_cols, f"missing column users.{required}"

        subscription_cols = {
            c["name"] for c in insp.get_columns("user_subscriptions")
        }
        assert subscription_cols == {
            "id",
            "user_id",
            "rw_id",
            "product_key",
            "label",
            "source",
            "is_primary",
            "created_at",
            "updated_at",
        }

        transfer_cols = {
            c["name"] for c in insp.get_columns("subscription_transfers")
        }
        assert transfer_cols == {
            "id",
            "user_id",
            "source_rw_id",
            "target_rw_id",
            "days_transferred",
            "status",
            "error_code",
            "created_at",
            "updated_at",
        }

        transaction_cols = {c["name"] for c in insp.get_columns("transactions")}
        assert "target_rw_id" in transaction_cols

        ticket_cols = {c["name"] for c in insp.get_columns("support_tickets")}
        assert ticket_cols == {
            "id",
            "user_id",
            "username",
            "subject",
            "message",
            "status",
            "created_at",
            "updated_at",
        }
    finally:
        engine.dispose()
