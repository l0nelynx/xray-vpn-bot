"""Android API auth tables: refresh tokens, email verifications,
Telegram link codes.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    family_id: Mapped[str] = mapped_column(String(36))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    issued_at: Mapped[str] = mapped_column(String(30))
    expires_at: Mapped[str] = mapped_column(String(30))
    revoked_at: Mapped[str] = mapped_column(String(30), nullable=True)
    replaced_by_id: Mapped[int] = mapped_column(Integer, nullable=True)
    user_agent: Mapped[str] = mapped_column(String(255), nullable=True)
    ip: Mapped[str] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_family_id", "family_id"),
    )


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(String(20))
    code_hash: Mapped[str] = mapped_column(String(128))
    payload: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[str] = mapped_column(String(30))
    expires_at: Mapped[str] = mapped_column(String(30))
    used_at: Mapped[str] = mapped_column(String(30), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    __table_args__ = (
        Index("ix_email_verifications_user_id_purpose", "user_id", "purpose"),
    )


class TelegramLinkCode(Base):
    __tablename__ = "telegram_link_codes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    code_hash: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[str] = mapped_column(String(30))
    expires_at: Mapped[str] = mapped_column(String(30))
    used_at: Mapped[str] = mapped_column(String(30), nullable=True)
    used_by_tg_id: Mapped[int] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (Index("ix_telegram_link_codes_user_id", "user_id"),)
