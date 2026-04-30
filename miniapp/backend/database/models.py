from sqlalchemy import BigInteger, String, ForeignKey, Index, Integer, Boolean, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id = mapped_column(BigInteger, unique=True)
    username: Mapped[str] = mapped_column(String(100), nullable=True)
    vless_uuid: Mapped[str] = mapped_column(String(100), nullable=True)
    api_provider: Mapped[str] = mapped_column(String(50), default="remnawave")
    email: Mapped[str] = mapped_column(String(100), nullable=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    language: Mapped[str] = mapped_column(String(5), default=None, nullable=True)
    vip: Mapped[int] = mapped_column(Integer, default=0, nullable=True)

    __table_args__ = (Index("ix_user_username", "username"),)


class Promo(Base):
    __tablename__ = "promos"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    promo_code: Mapped[str] = mapped_column(String(20), unique=True)
    used_promo: Mapped[str] = mapped_column(String(20), nullable=True)
    days_purchased: Mapped[int] = mapped_column(Integer, default=0)
    days_rewarded: Mapped[int] = mapped_column(Integer, default=0)
    discount_percent: Mapped[int] = mapped_column(Integer, nullable=True)
    used_promo_consumed: Mapped[bool] = mapped_column(Boolean, default=False)


class PromoSettings(Base):
    __tablename__ = "promo_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    default_discount_percent: Mapped[int] = mapped_column(Integer, default=20)


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
    tariff_slug: Mapped[str] = mapped_column(String(200), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    username: Mapped[str] = mapped_column(String(100), nullable=True)
    subject: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[str] = mapped_column(String(30))
    updated_at: Mapped[str] = mapped_column(String(30))

    messages: Mapped[list["SupportMessage"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )


class TelmtFreeParams(Base):
    __tablename__ = "telmt_free_params"

    id: Mapped[int] = mapped_column(primary_key=True)
    max_tcp_conns: Mapped[int] = mapped_column(Integer, nullable=True)
    max_unique_ips: Mapped[int] = mapped_column(Integer, nullable=True)
    data_quota_bytes: Mapped[int] = mapped_column(BigInteger, nullable=True)
    expire_days: Mapped[int] = mapped_column(Integer, default=30, nullable=True)


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("support_tickets.id", ondelete="CASCADE")
    )
    sender: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(30))

    ticket: Mapped["SupportTicket"] = relationship(back_populates="messages")
