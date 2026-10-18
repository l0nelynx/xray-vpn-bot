"""Durable Remnawave incident state and Telegram recovery subscriptions."""
from sqlalchemy import BigInteger, Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class RemnawaveAvailability(Base):
    __tablename__ = "remnawave_availability"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident: Mapped[int] = mapped_column(Integer, default=0)
    unavailable: Mapped[bool] = mapped_column(Boolean, default=False)
    next_probe_at: Mapped[float] = mapped_column(Float, default=0)


class RemnawaveRecoverySubscription(Base):
    __tablename__ = "remnawave_recovery_subscriptions"

    incident: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    language: Mapped[str] = mapped_column(String(2), default="ru")


class RemnawaveNotice(Base):
    __tablename__ = "remnawave_notices"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    admin: Mapped[bool] = mapped_column(Boolean)
    tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    next_attempt_at: Mapped[float] = mapped_column(Float, default=0)
