"""User-related models.

Schema canon (synced with production after Alembic 0001..0011):
- users.id        : BigInteger PK (alembic 0007)
- users.tg_id     : BigInteger, NOT unique (alembic 0009 dropped unique)
- users.vip       : BigInteger, default=0, server_default="0", nullable=True (0007)
- users.api_provider : default="remnawave" in Python; server_default="marzban"
                       still on prod — kept as-is, do not silently flip
- users.language  : default=None, server_default="ru" (0001/0006)
- users.is_banned : Boolean, default=False, server_default="0", nullable=True
- users.email     : unique via Index('ix_users_email_unique', unique=True)
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Telegram user id. Not unique on prod (alembic 0009 dropped the constraint).
    tg_id: Mapped[int] = mapped_column(BigInteger, nullable=True)

    # Telegram username. Indexed for lookups but not unique.
    username: Mapped[str] = mapped_column(String(100), nullable=True)

    # Legacy name: this stores the Remnawave user UUID, not a protocol VLESS
    # credential UUID. New integrations must use rw_id as the canonical key.
    vless_uuid: Mapped[str] = mapped_column(String(100), nullable=True)

    # Remnawave panel numeric user id (int64). Nullable until backfilled.
    rw_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # API provider key. Python default ≠ DB server_default by design — see
    # module docstring. Don't change without an explicit Alembic migration.
    api_provider: Mapped[str] = mapped_column(
        String(50), default="remnawave", server_default="marzban"
    )

    # Optional email (used by Remnawave lookup and the Android API).
    email: Mapped[str] = mapped_column(String(100), nullable=True)

    # Ban flag.
    is_banned: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=True
    )

    # UI language (ru/en). NULL means "not yet chosen".
    language: Mapped[str] = mapped_column(
        String(5), default=None, server_default="ru", nullable=True
    )

    # VIP flag (Sub Clean protection). BigInteger on prod since 0007.
    vip: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0", nullable=True
    )

    # Spendable subscription-day credits (1 credit = 1 day on any tariff).
    bonus_credits: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    # Android API: argon2id password hash (NULL for Telegram-only accounts).
    password_hash: Mapped[str] = mapped_column(String(255), nullable=True)
    password_updated_at: Mapped[str] = mapped_column(String(30), nullable=True)
    email_verified_at: Mapped[str] = mapped_column(String(30), nullable=True)

    transactions: Mapped[list["Transaction"]] = relationship(  # noqa: F821
        back_populates="user"
    )
    subscriptions: Mapped[list["UserSubscription"]] = relationship(  # noqa: F821
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="UserSubscription.id",
    )

    __table_args__ = (
        Index("ix_user_username", "username"),
        Index("ix_users_email_unique", "email", unique=True),
        Index(
            "ux_users_rw_id",
            "rw_id",
            unique=True,
            postgresql_where=text("rw_id IS NOT NULL"),
            sqlite_where=text("rw_id IS NOT NULL"),
        ),
    )


class UserSubscription(Base):
    """A Remnawave subscription managed by a local account.

    ``rw_id`` is the stable external identity. Subscription URLs are secrets
    and deliberately are not persisted here; callers fetch them from
    Remnawave only when an authenticated response needs one.
    """

    __tablename__ = "user_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rw_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, default="legacy", server_default="legacy"
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[str] = mapped_column(String(30), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(30), nullable=False)

    user: Mapped["User"] = relationship(back_populates="subscriptions")

    __table_args__ = (
        Index("ux_user_subscriptions_rw_id", "rw_id", unique=True),
        Index("ix_user_subscriptions_user_id", "user_id"),
        Index(
            "ux_user_subscriptions_primary",
            "user_id",
            unique=True,
            postgresql_where=text("is_primary"),
            sqlite_where=text("is_primary = 1"),
        ),
    )


class SubscriptionTransfer(Base):
    """Idempotency/audit ledger for a remaining-time transfer."""

    __tablename__ = "subscription_transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_rw_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target_rw_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    days_transferred: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[str] = mapped_column(String(30), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(30), nullable=False)

    __table_args__ = (
        Index("ux_subscription_transfers_source_rw_id", "source_rw_id", unique=True),
        Index("ix_subscription_transfers_user_id", "user_id"),
    )


class DisabledUser(Base):
    __tablename__ = "disabled_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    original_status: Mapped[str] = mapped_column(String(20))
    disabled_at: Mapped[str] = mapped_column(String(30))
