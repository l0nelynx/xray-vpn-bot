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

from sqlalchemy import BigInteger, Boolean, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Telegram user id. Not unique on prod (alembic 0009 dropped the constraint).
    tg_id: Mapped[int] = mapped_column(BigInteger, nullable=True)

    # Telegram username. Indexed for lookups but not unique.
    username: Mapped[str] = mapped_column(String(100), nullable=True)

    # VLESS UUID assigned by the VPN provider.
    vless_uuid: Mapped[str] = mapped_column(String(100), nullable=True)

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

    # Android API: argon2id password hash (NULL for Telegram-only accounts).
    password_hash: Mapped[str] = mapped_column(String(255), nullable=True)
    password_updated_at: Mapped[str] = mapped_column(String(30), nullable=True)
    email_verified_at: Mapped[str] = mapped_column(String(30), nullable=True)

    transactions: Mapped[list["Transaction"]] = relationship(  # noqa: F821
        back_populates="user"
    )

    __table_args__ = (
        Index("ix_user_username", "username"),
        Index("ix_users_email_unique", "email", unique=True),
    )


class DisabledUser(Base):
    __tablename__ = "disabled_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    original_status: Mapped[str] = mapped_column(String(20))
    disabled_at: Mapped[str] = mapped_column(String(30))
