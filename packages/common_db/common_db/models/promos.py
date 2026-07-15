"""Promo codes and global promo settings."""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base

# Promo code types.
PROMO_TYPE_REFERRAL = "referral"
PROMO_TYPE_PROMOTIONAL = "promotional"


class Promo(Base):
    """Catalog of promo codes (one row = one code).

    A "referral" promo is a user's own code, auto-generated the first time
    they open the invite screen; its owner earns reward days when invitees
    purchase. A "promotional" promo is an admin/dashboard marketing code,
    usually owned by a synthetic negative tg_id.

    Redemptions (who used which code) live in ``promo_redemptions`` — this
    table only models the codes themselves plus the owner reward counters.
    """

    __tablename__ = "promos"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    promo_code: Mapped[str] = mapped_column(String(20), unique=True)

    # Referral (user-owned) vs promotional (marketing) code.
    promo_type: Mapped[str] = mapped_column(
        String(20), default=PROMO_TYPE_REFERRAL, server_default=PROMO_TYPE_REFERRAL
    )

    days_purchased: Mapped[int] = mapped_column(Integer, default=0)
    days_rewarded: Mapped[int] = mapped_column(Integer, default=0)

    # NULL = use PromoSettings.default_credit_grant.
    credit_grant: Mapped[int] = mapped_column(Integer, nullable=True)

    # Legacy — superseded by credit_grant; kept for migration reads.
    discount_percent: Mapped[int] = mapped_column(Integer, nullable=True)

    # --- legacy single-redemption columns (superseded by promo_redemptions) ---
    # Kept so the 0012 backfill can read them and so historical rows stay
    # intact; a later migration may drop them once nothing reads them.
    used_promo: Mapped[str] = mapped_column(String(20), nullable=True)
    used_promo_consumed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )


class PromoSettings(Base):
    """Single-row settings table for promo/referral defaults.

    Single source of truth for tunables that used to be split between
    config.yml (bot) and this table (miniapp/dashboard).
    """

    __tablename__ = "promo_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    default_credit_grant: Mapped[int] = mapped_column(
        Integer, default=10, server_default="10"
    )

    # Legacy — superseded by default_credit_grant.
    default_discount_percent: Mapped[int] = mapped_column(Integer, default=20)

    # Reward days granted to a referral owner per 30 days an invitee buys.
    days_reward_per_30: Mapped[int] = mapped_column(
        Integer, default=3, server_default="3"
    )
    # Cumulative cap (days) on the reward a single owner can ever earn.
    reward_cap_days: Mapped[int] = mapped_column(
        Integer, default=180, server_default="180"
    )
