"""Persisted MiniApp UX funnel events."""
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class MiniappUxEvent(Base):
    __tablename__ = "miniapp_ux_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subscription_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("user_subscriptions.id", ondelete="SET NULL"),
        nullable=True,
    )
    transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    onboarding_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[str] = mapped_column(String(30), nullable=False)

    __table_args__ = (
        Index("ix_miniapp_ux_events_user_created", "user_id", "created_at"),
        Index("ix_miniapp_ux_events_name_created", "name", "created_at"),
        Index("ix_miniapp_ux_events_transaction", "transaction_id"),
    )
