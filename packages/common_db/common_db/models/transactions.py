"""Payment transactions.

Schema canon:
- transactions.user_id   : FK -> users.id (Integer in 0001; users.id grew
                           to BigInteger in 0007, FK was not retyped — left
                           as Integer to match prod row-by-row).
- transactions.username  : String(50), nullable=True
- transactions.squad_id / external_squad_id: immutable delivery target
- transactions.provider_invoice_id: provider-side correlation key; the local
                           transaction_id remains the application identity
- transactions.android_user_id: Integer, nullable=True + index
- relationship user      : back_populates="transactions" on User
"""
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    vless_uuid: Mapped[str] = mapped_column(String(100))
    username: Mapped[str] = mapped_column(String(50), nullable=True)
    order_status: Mapped[str] = mapped_column(String(50))
    delivery_status: Mapped[int] = mapped_column(Integer)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=True)
    amount: Mapped[float] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(String(30), nullable=True)
    days_ordered: Mapped[int] = mapped_column(BigInteger)
    expire_date: Mapped[str] = mapped_column(String(30), nullable=True)

    # Immutable delivery snapshot captured when the invoice is created.
    squad_id: Mapped[str] = mapped_column(String(100), nullable=True)
    internal_squad_ids: Mapped[list[str]] = mapped_column(JSON, nullable=True)
    external_squad_id: Mapped[str] = mapped_column(String(100), nullable=True)
    traffic_limit_bytes: Mapped[int] = mapped_column(BigInteger, nullable=True)
    traffic_limit_strategy: Mapped[str] = mapped_column(String(30), nullable=True)
    remnawave_description: Mapped[str] = mapped_column(Text, nullable=True)
    remnawave_tag: Mapped[str] = mapped_column(String(16), nullable=True)
    provider_invoice_id: Mapped[str] = mapped_column(String(100), nullable=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    user: Mapped["User"] = relationship(back_populates="transactions")  # noqa: F821

    # Android API: equals users.id when the invoice was created via the
    # Android API (user has no tg_id). NULL for Telegram-bot invoices.
    android_user_id: Mapped[int] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_transaction_user_id", "user_id"),
        Index("ix_transactions_android_user_id", "android_user_id"),
        Index("ix_transactions_provider_invoice_id", "provider_invoice_id"),
    )
