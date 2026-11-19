"""Durable web purchase analytics outbox; no customer contact data."""
from sqlalchemy import Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from ..base import Base


class WebAnalyticsPurchase(Base):
    __tablename__ = "web_analytics_purchases"

    transaction_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("transactions.transaction_id", ondelete="CASCADE"), primary_key=True
    )
    payload: Mapped[dict] = mapped_column(JSON)
    confirmed_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    sent_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_attempt_at: Mapped[float] = mapped_column(Float, default=0, server_default="0", index=True)
    last_error: Mapped[str | None] = mapped_column(String(50), nullable=True)
