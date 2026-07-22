"""Promo redemptions — audit of which user redeemed which code.

Tracks redemption history for gating rules (referral once ever, promotional
each code once). Credits are granted immediately on redeem via credit_ledger;
there is no pending discount state.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class PromoRedemption(Base):
    __tablename__ = "promo_redemptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger)
    promo_code: Mapped[str] = mapped_column(String(20))
    promo_type: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[str] = mapped_column(String(30))

    __table_args__ = (
        Index("ix_promo_redemptions_tg_id", "tg_id"),
        Index("ix_promo_redemptions_promo_code", "promo_code"),
    )
