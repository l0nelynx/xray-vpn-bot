"""Google Play IAP tables."""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class GooglePlayPurchase(Base):
    __tablename__ = "google_play_purchases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    product_id: Mapped[str] = mapped_column(String(100))
    purchase_token: Mapped[str] = mapped_column(String(512), unique=True)
    order_id: Mapped[str] = mapped_column(String(100), nullable=True)
    expiry_time: Mapped[str] = mapped_column(String(30), nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    raw_payload: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(30))
    updated_at: Mapped[str] = mapped_column(String(30))

    # Subscription fields (Stage 5).
    subscription_id: Mapped[str] = mapped_column(String(100), nullable=True)
    linked_purchase_token: Mapped[str] = mapped_column(String(512), nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=True)
    auto_renewing: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    start_time: Mapped[str] = mapped_column(String(30), nullable=True)
    latest_notification_type: Mapped[int] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_google_play_purchases_user_id", "user_id"),
        Index("ix_google_play_purchases_state", "state"),
        Index("ix_google_play_purchases_linked_token", "linked_purchase_token"),
    )


class GooglePlaySku(Base):
    __tablename__ = "google_play_skus"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(String(100), unique=True)
    days: Mapped[int] = mapped_column(Integer)
    squad_id: Mapped[str] = mapped_column(String(100))
    external_squad_id: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[str] = mapped_column(String(200), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[str] = mapped_column(String(30), nullable=True)
    updated_at: Mapped[str] = mapped_column(String(30), nullable=True)
