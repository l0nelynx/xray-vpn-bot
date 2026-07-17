"""Dashboard FCM push campaigns."""
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

# SQLite only autoincrements INTEGER PRIMARY KEY; keep BIGINT on Postgres.
_BIGINT_PK = BigInteger().with_variant(Integer, "sqlite")


class PushCampaign(Base):
    __tablename__ = "push_campaigns"

    id: Mapped[int] = mapped_column(_BIGINT_PK, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), default="", server_default="")
    body: Mapped[str] = mapped_column(Text, default="", server_default="")
    data_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    audience: Mapped[str] = mapped_column(
        String(20), default="all_tokens", server_default="all_tokens"
    )
    audience_params: Mapped[str] = mapped_column(
        Text, default="{}", server_default="{}"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft"
    )
    total_targets: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    sent: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    failed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[str] = mapped_column(String(30), nullable=False)
    started_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(100), default="", server_default=""
    )

    deliveries: Mapped[list["PushCampaignDelivery"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_push_campaigns_status", "status"),
        Index("ix_push_campaigns_created_at", "created_at"),
    )


class PushCampaignDelivery(Base):
    __tablename__ = "push_campaign_deliveries"

    id: Mapped[int] = mapped_column(_BIGINT_PK, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("push_campaigns.id", ondelete="CASCADE")
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending"
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[str | None] = mapped_column(String(30), nullable=True)

    campaign: Mapped["PushCampaign"] = relationship(back_populates="deliveries")

    __table_args__ = (
        Index("ix_push_campaign_deliveries_campaign_id", "campaign_id"),
        Index("ix_push_campaign_deliveries_user_id", "user_id"),
    )
