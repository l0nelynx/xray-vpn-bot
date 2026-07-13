"""Tariff plans and their per-payment-method prices.

Note on tariff_plans.squad_profile_id:
- alembic 0006 added the column (Integer FK).
- alembic 0007 widened it to BigInteger to match users.id-style PK growth.
  squad_profiles.id itself is still Integer in 0001 (no later widening),
  so the FK type is BigInteger pointing at an Integer column; PG accepts
  this. We keep the BigInteger to match prod and silence autogenerate.
"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


class SquadProfile(Base):
    __tablename__ = "squad_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    squad_id: Mapped[str] = mapped_column(String(100))
    external_squad_id: Mapped[str] = mapped_column(String(100))

    tariffs: Mapped[list["TariffPlan"]] = relationship(back_populates="squad_profile")


class TariffPlan(Base):
    __tablename__ = "tariff_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True)
    name_ru: Mapped[str] = mapped_column(String(100))
    name_en: Mapped[str] = mapped_column(String(100))
    days: Mapped[int] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    discount_percent: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(30), nullable=True)
    squad_profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("squad_profiles.id"), nullable=True
    )

    prices: Mapped[list["TariffPrice"]] = relationship(
        back_populates="tariff", cascade="all, delete-orphan"
    )
    squad_profile: Mapped["SquadProfile"] = relationship(back_populates="tariffs")


class TariffPrice(Base):
    __tablename__ = "tariff_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    tariff_id: Mapped[int] = mapped_column(
        ForeignKey("tariff_plans.id", ondelete="CASCADE")
    )
    payment_method: Mapped[str] = mapped_column(String(30))
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tariff: Mapped["TariffPlan"] = relationship(back_populates="prices")

    __table_args__ = (
        UniqueConstraint("tariff_id", "payment_method", name="uq_tariff_payment"),
    )
