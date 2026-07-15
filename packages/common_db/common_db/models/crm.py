"""CRM campaign persistence (dashboard)."""
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

# SQLite only autoincrements INTEGER PRIMARY KEY; keep BIGINT on Postgres.
_BIGINT_PK = BigInteger().with_variant(Integer, "sqlite")


class CrmEvent(Base):
    __tablename__ = "crm_events"

    id: Mapped[int] = mapped_column(_BIGINT_PK, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    enabled: Mapped[bool] = mapped_column(default=True, server_default="true")
    segment_type: Mapped[str] = mapped_column(String(50), nullable=True)
    segment_params: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    conditions_json: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    actions_json: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    run_at_time: Mapped[str] = mapped_column(String(5), default="01:00", server_default="01:00")
    frequency: Mapped[str] = mapped_column(String(20), default="daily", server_default="daily")
    weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message_text: Mapped[str] = mapped_column(Text, default="", server_default="")
    attach_button: Mapped[bool] = mapped_column(default=False, server_default="false")
    bonus_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bonus_traffic_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    repeat_policy: Mapped[str] = mapped_column(
        String(20), default="cooldown", server_default="cooldown"
    )
    repeat_cooldown_days: Mapped[int] = mapped_column(Integer, default=7, server_default="7")
    last_run_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    next_run_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[str] = mapped_column(String(30))
    updated_at: Mapped[str] = mapped_column(String(30))
    created_by: Mapped[str] = mapped_column(String(100), default="", server_default="")

    campaigns: Mapped[list["CrmCampaign"]] = relationship(back_populates="event")
    deliveries: Mapped[list["CrmEventDelivery"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_crm_events_enabled", "enabled"),
        Index("ix_crm_events_next_run_at", "next_run_at"),
    )


class CrmEventDelivery(Base):
    __tablename__ = "crm_event_deliveries"

    id: Mapped[int] = mapped_column(_BIGINT_PK, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("crm_events.id", ondelete="CASCADE")
    )
    tg_id: Mapped[int] = mapped_column(BigInteger)
    sent_at: Mapped[str] = mapped_column(String(30))

    event: Mapped["CrmEvent"] = relationship(back_populates="deliveries")

    __table_args__ = (
        Index("ix_crm_event_deliveries_event_id", "event_id"),
        Index("ix_crm_event_deliveries_tg_id", "tg_id"),
        Index("ix_crm_event_deliveries_event_tg", "event_id", "tg_id"),
    )


class CrmCampaign(Base):
    __tablename__ = "crm_campaigns"

    id: Mapped[int] = mapped_column(_BIGINT_PK, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    segment_type: Mapped[str] = mapped_column(String(50), nullable=True)
    segment_params: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    conditions_json: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    actions_json: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    message_text: Mapped[str] = mapped_column(Text, default="", server_default="")
    attach_button: Mapped[bool] = mapped_column(default=False, server_default="false")
    bonus_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bonus_traffic_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft"
    )
    total_targets: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    messages_sent: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    messages_failed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    perks_applied: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    perks_failed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    event_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("crm_events.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[str] = mapped_column(String(30))
    started_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), default="", server_default="")

    event: Mapped["CrmEvent | None"] = relationship(back_populates="campaigns")
    deliveries: Mapped[list["CrmCampaignDelivery"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_crm_campaigns_status", "status"),
        Index("ix_crm_campaigns_created_at", "created_at"),
        Index("ix_crm_campaigns_event_id", "event_id"),
    )


class CrmCampaignDelivery(Base):
    __tablename__ = "crm_campaign_deliveries"

    id: Mapped[int] = mapped_column(_BIGINT_PK, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("crm_campaigns.id", ondelete="CASCADE")
    )
    tg_id: Mapped[int] = mapped_column(BigInteger)
    vless_uuid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    perk_status: Mapped[str] = mapped_column(
        String(20), default="skipped", server_default="skipped"
    )
    message_status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending"
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    campaign: Mapped["CrmCampaign"] = relationship(back_populates="deliveries")

    __table_args__ = (
        Index("ix_crm_campaign_deliveries_campaign_id", "campaign_id"),
        Index("ix_crm_campaign_deliveries_tg_id", "tg_id"),
    )
