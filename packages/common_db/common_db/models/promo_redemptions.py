"""Promo redemptions — history of which user redeemed which code.

Replaces the old single ``promos.used_promo`` column so the system can
express both invariants the product needs:

- a *referral* code can be redeemed at most once per user, ever;
- a *promotional* code can be redeemed by anyone, but each code only once
  per user.

The discount and type are *snapshotted* at redemption time so later edits
to the source promo (or its owner's override) don't retroactively change a
redemption that's already been granted. Exactly one redemption per user may
be ``status="active"`` at a time; it flips to ``"consumed"`` on the user's
first paid delivery.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base

REDEMPTION_ACTIVE = "active"
REDEMPTION_CONSUMED = "consumed"


class PromoRedemption(Base):
    __tablename__ = "promo_redemptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger)
    promo_code: Mapped[str] = mapped_column(String(20))

    # Snapshot of the code's type + effective discount at redemption time.
    promo_type: Mapped[str] = mapped_column(String(20))
    discount_percent: Mapped[int] = mapped_column(Integer)

    # "active" (discount unspent) → "consumed" (spent on a paid delivery).
    status: Mapped[str] = mapped_column(
        String(16), default=REDEMPTION_ACTIVE, server_default=REDEMPTION_ACTIVE
    )

    created_at: Mapped[str] = mapped_column(String(30))
    consumed_at: Mapped[str] = mapped_column(String(30), nullable=True)

    __table_args__ = (
        Index("ix_promo_redemptions_tg_id", "tg_id"),
        Index("ix_promo_redemptions_promo_code", "promo_code"),
    )
