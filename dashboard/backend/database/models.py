from sqlalchemy import BigInteger, String, ForeignKey, Index, Integer, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id = mapped_column(BigInteger, unique=True)
    username: Mapped[str] = mapped_column(String(100), nullable=True)
    vless_uuid: Mapped[str] = mapped_column(String(100), nullable=True)
    api_provider: Mapped[str] = mapped_column(String(50), default="marzban")
    email: Mapped[str] = mapped_column(String(100), nullable=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=True)
    language: Mapped[str] = mapped_column(String(5), default=None, nullable=True)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")

    __table_args__ = (Index("ix_user_username", "username"),)


class Promo(Base):
    __tablename__ = "promos"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    promo_code: Mapped[str] = mapped_column(String(20), unique=True)
    used_promo: Mapped[str] = mapped_column(String(20), nullable=True)
    days_purchased: Mapped[int] = mapped_column(Integer, default=0)
    days_rewarded: Mapped[int] = mapped_column(Integer, default=0)


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    vless_uuid: Mapped[str] = mapped_column(String(100))
    username: Mapped[str] = mapped_column(String(50))
    order_status: Mapped[str] = mapped_column(String(50))
    delivery_status: Mapped[int] = mapped_column(Integer)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=True)
    amount: Mapped[float] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(String(30), nullable=True)
    days_ordered: Mapped[int] = mapped_column(BigInteger)
    expire_date: Mapped[str] = mapped_column(String(30), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    user: Mapped["User"] = relationship(back_populates="transactions")

    __table_args__ = (Index("ix_transaction_user_id", "user_id"),)
