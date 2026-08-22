"""Giveaway / raffle persistence."""
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

_BIGINT_PK = BigInteger().with_variant(Integer, "sqlite")

GIVEAWAY_STATUS_DRAFT = "draft"
GIVEAWAY_STATUS_ACTIVE = "active"
GIVEAWAY_STATUS_CLOSED = "closed"
GIVEAWAY_STATUS_DRAWN = "drawn"

ENTRY_CLICK_ONLY = "click_only"
ENTRY_CHANNEL_SUB = "channel_sub"

CHANCE_STATIC = "static"
CHANCE_DYNAMIC = "dynamic"

WINNER_RANDOM = "random"
WINNER_MOST_TICKETS = "most_tickets"

TICKET_SOURCE_JOIN = "join"
TICKET_SOURCE_INVITEE_REF = "invitee_ref_activation"
TICKET_SOURCE_INVITEE_PURCHASE = "invitee_purchase"


class Giveaway(Base):
    __tablename__ = "giveaways"

    id: Mapped[int] = mapped_column(_BIGINT_PK, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), default="", server_default="")
    channel_text: Mapped[str] = mapped_column(Text, default="", server_default="")
    status: Mapped[str] = mapped_column(
        String(20), default=GIVEAWAY_STATUS_DRAFT, server_default=GIVEAWAY_STATUS_DRAFT
    )
    config_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    winner_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    starts_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ends_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    drawn_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[str] = mapped_column(String(30))
    created_by: Mapped[str] = mapped_column(String(100), default="", server_default="")

    participants: Mapped[list["GiveawayParticipant"]] = relationship(
        back_populates="giveaway", cascade="all, delete-orphan"
    )
    tickets: Mapped[list["GiveawayTicket"]] = relationship(
        back_populates="giveaway", cascade="all, delete-orphan"
    )
    winners: Mapped[list["GiveawayWinner"]] = relationship(
        back_populates="giveaway", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_giveaways_status", "status"),
        Index("ix_giveaways_created_at", "created_at"),
    )


class GiveawayParticipant(Base):
    __tablename__ = "giveaway_participants"

    id: Mapped[int] = mapped_column(_BIGINT_PK, primary_key=True, autoincrement=True)
    giveaway_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("giveaways.id", ondelete="CASCADE")
    )
    tg_id: Mapped[int] = mapped_column(BigInteger)
    joined_at: Mapped[str] = mapped_column(String(30))

    giveaway: Mapped["Giveaway"] = relationship(back_populates="participants")

    __table_args__ = (
        UniqueConstraint("giveaway_id", "tg_id", name="uq_giveaway_participant"),
        Index("ix_giveaway_participants_giveaway_id", "giveaway_id"),
        Index("ix_giveaway_participants_tg_id", "tg_id"),
    )


class GiveawayTicket(Base):
    __tablename__ = "giveaway_tickets"

    id: Mapped[int] = mapped_column(_BIGINT_PK, primary_key=True, autoincrement=True)
    giveaway_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("giveaways.id", ondelete="CASCADE")
    )
    participant_tg_id: Mapped[int] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(40))
    source_tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[str] = mapped_column(String(30))

    giveaway: Mapped["Giveaway"] = relationship(back_populates="tickets")

    __table_args__ = (
        UniqueConstraint(
            "giveaway_id",
            "participant_tg_id",
            "source",
            "source_tg_id",
            name="uq_giveaway_ticket",
        ),
        Index("ix_giveaway_tickets_giveaway_id", "giveaway_id"),
        Index("ix_giveaway_tickets_participant", "giveaway_id", "participant_tg_id"),
    )


class GiveawayWinner(Base):
    __tablename__ = "giveaway_winners"

    id: Mapped[int] = mapped_column(_BIGINT_PK, primary_key=True, autoincrement=True)
    giveaway_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("giveaways.id", ondelete="CASCADE")
    )
    tg_id: Mapped[int] = mapped_column(BigInteger)
    rank: Mapped[int] = mapped_column(Integer)
    tickets: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    winning_ticket_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("giveaway_tickets.id", ondelete="SET NULL"),
        nullable=True,
    )

    giveaway: Mapped["Giveaway"] = relationship(back_populates="winners")

    __table_args__ = (
        UniqueConstraint("giveaway_id", "rank", name="uq_giveaway_winner_rank"),
        Index("ix_giveaway_winners_giveaway_id", "giveaway_id"),
        Index("ix_giveaway_winners_winning_ticket_id", "winning_ticket_id"),
    )
