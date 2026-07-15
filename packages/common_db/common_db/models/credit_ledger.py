"""Bonus credit ledger — audit trail for user subscription-day credits."""
from __future__ import annotations

from sqlalchemy import BigInteger, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base

SOURCE_PROMO = "promo"
SOURCE_CRM = "crm"
SOURCE_PAYMENT = "payment"
SOURCE_ADMIN = "admin"
SOURCE_MIGRATION = "migration"


class CreditLedger(Base):
    __tablename__ = "credit_ledger"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    amount: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(32))
    reference: Mapped[str] = mapped_column(String(100), nullable=True)
    balance_after: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(30))

    __table_args__ = (
        Index("ix_credit_ledger_user_id", "user_id"),
    )
