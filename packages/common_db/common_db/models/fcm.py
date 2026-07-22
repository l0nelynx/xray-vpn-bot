"""Android FCM device tokens for push notifications."""
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base

# SQLite only autoincrements INTEGER PRIMARY KEY; keep BIGINT on Postgres.
_BIGINT_PK = BigInteger().with_variant(Integer, "sqlite")


class AndroidFcmToken(Base):
    __tablename__ = "android_fcm_tokens"

    id: Mapped[int] = mapped_column(_BIGINT_PK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    platform: Mapped[str] = mapped_column(
        String(20), default="android", server_default="android"
    )
    app_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(30), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(30), nullable=False)

    __table_args__ = (Index("ix_android_fcm_tokens_user_id", "user_id"),)
