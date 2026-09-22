"""Durable referral purchase receipts, recovery snapshot and notification outbox."""
from sqlalchemy import BigInteger, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class ReferralReceipt(Base):
    __tablename__ = "referral_receipts"
    transaction_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    promo_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    points: Mapped[int] = mapped_column(Integer, default=0)


class ReferralRecovery(Base):
    __tablename__ = "referral_recovery"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="ready")
    snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ReferralNotice(Base):
    __tablename__ = "referral_notices"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    claimed_at: Mapped[float | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(String(200), nullable=True)
