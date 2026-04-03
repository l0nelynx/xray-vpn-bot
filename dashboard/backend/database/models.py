from sqlalchemy import BigInteger, String, ForeignKey, Index, Integer, Boolean, Float, Text, UniqueConstraint
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
    vip: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=True)

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


class CacheVersion(Base):
    __tablename__ = "cache_version"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=0)


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
    squad_profile_id: Mapped[int] = mapped_column(ForeignKey("squad_profiles.id"), nullable=True)

    prices: Mapped[list["TariffPrice"]] = relationship(back_populates="tariff", cascade="all, delete-orphan")
    squad_profile: Mapped["SquadProfile"] = relationship(back_populates="tariffs")


class TariffPrice(Base):
    __tablename__ = "tariff_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    tariff_id: Mapped[int] = mapped_column(ForeignKey("tariff_plans.id", ondelete="CASCADE"))
    payment_method: Mapped[str] = mapped_column(String(30))
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tariff: Mapped["TariffPlan"] = relationship(back_populates="prices")

    __table_args__ = (
        UniqueConstraint("tariff_id", "payment_method", name="uq_tariff_payment"),
    )


class MenuScreen(Base):
    __tablename__ = "menu_screens"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    message_text_ru: Mapped[str] = mapped_column(Text, nullable=True)
    message_text_en: Mapped[str] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    buttons: Mapped[list["MenuButton"]] = relationship(back_populates="screen", cascade="all, delete-orphan")


class MenuButton(Base):
    __tablename__ = "menu_buttons"

    id: Mapped[int] = mapped_column(primary_key=True)
    screen_id: Mapped[int] = mapped_column(ForeignKey("menu_screens.id", ondelete="CASCADE"))
    text_ru: Mapped[str] = mapped_column(String(200))
    text_en: Mapped[str] = mapped_column(String(200))
    callback_data: Mapped[str] = mapped_column(String(100), nullable=True)
    url: Mapped[str] = mapped_column(String(500), nullable=True)
    row: Mapped[int] = mapped_column(Integer, default=0)
    col: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    button_type: Mapped[str] = mapped_column(String(20), default="callback")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    visibility_condition: Mapped[str] = mapped_column(String(50), default="always")

    screen: Mapped["MenuScreen"] = relationship(back_populates="buttons")
