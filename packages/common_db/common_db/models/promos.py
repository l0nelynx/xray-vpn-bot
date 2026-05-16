"""Promo codes and global promo settings."""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class Promo(Base):
    __tablename__ = "promos"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    promo_code: Mapped[str] = mapped_column(String(20), unique=True)
    used_promo: Mapped[str] = mapped_column(String(20), nullable=True)
    days_purchased: Mapped[int] = mapped_column(Integer, default=0)
    days_rewarded: Mapped[int] = mapped_column(Integer, default=0)

    # NULL = use PromoSettings.default_discount_percent.
    discount_percent: Mapped[int] = mapped_column(Integer, nullable=True)

    # True after the user's first paid purchase consumed the activated promo's
    # discount; user is then allowed to activate a new promo. The original
    # `used_promo` value is preserved so referral rewards continue to flow.
    used_promo_consumed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )


class PromoSettings(Base):
    """Single-row settings table for promo defaults."""

    __tablename__ = "promo_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    default_discount_percent: Mapped[int] = mapped_column(Integer, default=20)
