import logging
import os

from sqlalchemy import BigInteger, String, ForeignKey, Index, Integer, Boolean, Float, Text, UniqueConstraint, text, inspect
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

DB_PATH = os.environ.get('DB_PATH', 'db.sqlite3')
engine = create_async_engine(url=f'sqlite+aiosqlite:///{DB_PATH}')

async_session = async_sessionmaker(engine)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id = mapped_column(BigInteger, unique=True)

    # Имя пользователя (Telegram username)
    # Примечание: unique=True удален, так как SQLite не поддерживает добавление UNIQUE к существующей таблице
    username: Mapped[str] = mapped_column(String(100), nullable=True)

    # UUID для VLESS конфигурации
    vless_uuid: Mapped[str] = mapped_column(String(100), nullable=True)

    # API провайдер, на котором зарегистрирован пользователь (remnawave)
    api_provider: Mapped[str] = mapped_column(String(50), default="remnawave")

    # Email пользователя (для поиска в RemnaWave)
    email: Mapped[str] = mapped_column(String(100), nullable=True)

    # Флаг бана пользователя
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=True)

    # Язык интерфейса пользователя (ru/en), None = не выбран
    language: Mapped[str] = mapped_column(String(5), default=None, nullable=True)

    # VIP-флаг (защита от Sub Clean)
    vip: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=True)

    # Добавляем отношение один-ко-многим с таблицей transactions
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")

    __table_args__ = (
        Index('ix_user_username', 'username'),
    )


class Promo(Base):
    __tablename__ = 'promos'

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    promo_code: Mapped[str] = mapped_column(String(20), unique=True)
    used_promo: Mapped[str] = mapped_column(String(20), nullable=True)
    days_purchased: Mapped[int] = mapped_column(Integer, default=0)
    days_rewarded: Mapped[int] = mapped_column(Integer, default=0)
    # NULL = use PromoSettings.default_discount_percent
    discount_percent: Mapped[int] = mapped_column(Integer, nullable=True)
    # True after the user's first paid purchase consumed the activated promo's
    # discount; user is then allowed to activate a new promo. The original
    # `used_promo` value is preserved so referral rewards continue to flow.
    used_promo_consumed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class PromoSettings(Base):
    """Single-row settings table for promo defaults."""
    __tablename__ = 'promo_settings'

    id: Mapped[int] = mapped_column(primary_key=True)
    default_discount_percent: Mapped[int] = mapped_column(Integer, default=20)


class Transaction(Base):
    __tablename__ = 'transactions'

    # Уникальный идентификатор транзакции
    transaction_id: Mapped[str] = mapped_column(String(100), primary_key=True)

    # Уникальный идентификатор vless
    vless_uuid: Mapped[str] = mapped_column(String(100))

    # Имя пользователя
    username: Mapped[str] = mapped_column(String(50), nullable=True)

    # Статус заказа
    order_status: Mapped[str] = mapped_column(String(50))

    # Количество дней в заказе
    delivery_status: Mapped[int] = mapped_column(Integer)

    # Способ оплаты
    payment_method: Mapped[str] = mapped_column(String(50), nullable=True)

    # Сумма платежа
    amount: Mapped[float] = mapped_column(nullable=True)

    # Дата создания транзакции (ISO формат)
    created_at: Mapped[str] = mapped_column(String(30), nullable=True)

    # Количество дней в заказе
    days_ordered: Mapped[int] = mapped_column(BigInteger)

    # Дата истечения подписки (ISO формат, рассчитывается при подтверждении)
    expire_date: Mapped[str] = mapped_column(String(30), nullable=True)

    # Tariff slug (existing tariff slug OR ad-hoc encoded squad: "sid:<id>:esid:<id>")
    tariff_slug: Mapped[str] = mapped_column(String(200), nullable=True)

    # Внешний ключ к таблице users
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # Отношение многие-к-одному с таблицей users
    user: Mapped["User"] = relationship(back_populates="transactions")

    # Добавляем индекс для user_id для ускорения JOIN-запросов
    __table_args__ = (
        Index('ix_transaction_user_id', 'user_id'),
    )


class DisabledUser(Base):
    __tablename__ = 'disabled_users'
    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id = mapped_column(BigInteger, unique=True)
    original_status: Mapped[str] = mapped_column(String(20))
    disabled_at: Mapped[str] = mapped_column(String(30))


class CacheVersion(Base):
    __tablename__ = 'cache_version'

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=0)


class SquadProfile(Base):
    __tablename__ = 'squad_profiles'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    squad_id: Mapped[str] = mapped_column(String(100))
    external_squad_id: Mapped[str] = mapped_column(String(100))

    tariffs: Mapped[list["TariffPlan"]] = relationship(back_populates="squad_profile")


class TariffPlan(Base):
    __tablename__ = 'tariff_plans'

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
    __tablename__ = 'tariff_prices'

    id: Mapped[int] = mapped_column(primary_key=True)
    tariff_id: Mapped[int] = mapped_column(ForeignKey("tariff_plans.id", ondelete="CASCADE"))
    payment_method: Mapped[str] = mapped_column(String(30))
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tariff: Mapped["TariffPlan"] = relationship(back_populates="prices")

    __table_args__ = (
        UniqueConstraint('tariff_id', 'payment_method', name='uq_tariff_payment'),
    )


class MenuScreen(Base):
    __tablename__ = 'menu_screens'

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    message_text_ru: Mapped[str] = mapped_column(Text, nullable=True)
    message_text_en: Mapped[str] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    buttons: Mapped[list["MenuButton"]] = relationship(back_populates="screen", cascade="all, delete-orphan")


class MenuButton(Base):
    __tablename__ = 'menu_buttons'

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


class TelmtFreeParams(Base):
    """Single-row settings table for Telemt free user parameters."""
    __tablename__ = 'telemt_free_params'

    id: Mapped[int] = mapped_column(primary_key=True)
    max_tcp_conns: Mapped[int] = mapped_column(Integer, nullable=True)
    max_unique_ips: Mapped[int] = mapped_column(Integer, nullable=True)
    data_quota_bytes: Mapped[int] = mapped_column(BigInteger, nullable=True)
    expire_days: Mapped[int] = mapped_column(Integer, default=30)


class SupportTicket(Base):
    __tablename__ = 'support_tickets'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    username: Mapped[str] = mapped_column(String(100), nullable=True)
    subject: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open", server_default="open")
    created_at: Mapped[str] = mapped_column(String(30))
    updated_at: Mapped[str] = mapped_column(String(30))

    messages: Mapped[list["SupportMessage"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('ix_support_tickets_user_id', 'user_id'),
        Index('ix_support_tickets_status', 'status'),
    )


class SupportMessage(Base):
    __tablename__ = 'support_messages'

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("support_tickets.id", ondelete="CASCADE")
    )
    sender: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(30))

    ticket: Mapped["SupportTicket"] = relationship(back_populates="messages")

    __table_args__ = (
        Index('ix_support_messages_ticket_id', 'ticket_id'),
    )


async def async_main():
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.execute(text("PRAGMA busy_timeout=5000"))
        await conn.run_sync(Base.metadata.create_all)

        # Миграция: добавляем is_banned если колонки ещё нет
        def _check_and_migrate(sync_conn):
            insp = inspect(sync_conn)
            columns = [col['name'] for col in insp.get_columns('users')]
            if 'email' not in columns:
                sync_conn.execute(text(
                    "ALTER TABLE users ADD COLUMN email VARCHAR(100)"
                ))
                logging.info("Migration: added email column to users table")

            if 'is_banned' not in columns:
                sync_conn.execute(text(
                    "ALTER TABLE users ADD COLUMN is_banned BOOLEAN DEFAULT 0"
                ))
                logging.info("Migration: added is_banned column to users table")

            if 'language' not in columns:
                sync_conn.execute(text(
                    "ALTER TABLE users ADD COLUMN language VARCHAR(5) DEFAULT 'ru'"
                ))
                logging.info("Migration: added language column to users table")

            if 'vip' not in columns:
                sync_conn.execute(text(
                    "ALTER TABLE users ADD COLUMN vip INTEGER DEFAULT 0"
                ))
                logging.info("Migration: added vip column to users table")

            # Миграция: добавляем новые колонки в transactions если таблица существует
            if 'transactions' in insp.get_table_names():
                tx_columns = [col['name'] for col in insp.get_columns('transactions')]
                if 'payment_method' not in tx_columns:
                    sync_conn.execute(text(
                        "ALTER TABLE transactions ADD COLUMN payment_method VARCHAR(50)"
                    ))
                    logging.info("Migration: added payment_method column to transactions table")
                if 'amount' not in tx_columns:
                    sync_conn.execute(text(
                        "ALTER TABLE transactions ADD COLUMN amount FLOAT"
                    ))
                    logging.info("Migration: added amount column to transactions table")
                if 'created_at' not in tx_columns:
                    sync_conn.execute(text(
                        "ALTER TABLE transactions ADD COLUMN created_at VARCHAR(30)"
                    ))
                    logging.info("Migration: added created_at column to transactions table")
                if 'expire_date' not in tx_columns:
                    sync_conn.execute(text(
                        "ALTER TABLE transactions ADD COLUMN expire_date VARCHAR(30)"
                    ))
                    logging.info("Migration: added expire_date column to transactions table")
                    # Бэкфилл: рассчитываем expire_date для существующих confirmed/delivered транзакций
                    sync_conn.execute(text(
                        "UPDATE transactions "
                        "SET expire_date = replace(datetime(created_at, '+' || days_ordered || ' days'), ' ', 'T') "
                        "WHERE expire_date IS NULL "
                        "AND order_status IN ('confirmed', 'delivered') "
                        "AND created_at IS NOT NULL "
                        "AND days_ordered IS NOT NULL"
                    ))
                    logging.info("Migration: backfilled expire_date for existing confirmed/delivered transactions")
                if 'tariff_slug' not in tx_columns:
                    sync_conn.execute(text(
                        "ALTER TABLE transactions ADD COLUMN tariff_slug VARCHAR(200)"
                    ))
                    logging.info("Migration: added tariff_slug column to transactions table")

            # Миграция: добавляем discount_percent в promos
            if 'promos' in insp.get_table_names():
                pr_columns = [col['name'] for col in insp.get_columns('promos')]
                if 'discount_percent' not in pr_columns:
                    sync_conn.execute(text(
                        "ALTER TABLE promos ADD COLUMN discount_percent INTEGER"
                    ))
                    logging.info("Migration: added discount_percent column to promos table")
                if 'used_promo_consumed' not in pr_columns:
                    sync_conn.execute(text(
                        "ALTER TABLE promos ADD COLUMN used_promo_consumed BOOLEAN DEFAULT 0"
                    ))
                    logging.info("Migration: added used_promo_consumed column to promos table")

            # Миграция: добавляем squad_profile_id в tariff_plans если колонки ещё нет
            if 'tariff_plans' in insp.get_table_names():
                tp_columns = [col['name'] for col in insp.get_columns('tariff_plans')]
                if 'squad_profile_id' not in tp_columns:
                    sync_conn.execute(text(
                        "ALTER TABLE tariff_plans ADD COLUMN squad_profile_id INTEGER REFERENCES squad_profiles(id)"
                    ))
                    logging.info("Migration: added squad_profile_id column to tariff_plans table")

            # Миграция: добавляем индекс на username если его ещё нет
            indexes = [idx['name'] for idx in insp.get_indexes('users')]
            if 'ix_user_username' not in indexes:
                sync_conn.execute(text(
                    "CREATE INDEX ix_user_username ON users (username)"
                ))
                logging.info("Migration: added ix_user_username index to users table")

            # Миграция: создаём таблицы поддержки (MiniApp)
            existing_tables = set(insp.get_table_names())
            if 'support_tickets' not in existing_tables:
                sync_conn.execute(text(
                    "CREATE TABLE support_tickets ("
                    " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    " user_id INTEGER NOT NULL REFERENCES users(id),"
                    " username VARCHAR(100),"
                    " subject VARCHAR(200) NOT NULL,"
                    " message TEXT NOT NULL,"
                    " status VARCHAR(20) NOT NULL DEFAULT 'open',"
                    " created_at VARCHAR(30) NOT NULL,"
                    " updated_at VARCHAR(30) NOT NULL"
                    ")"
                ))
                sync_conn.execute(text(
                    "CREATE INDEX ix_support_tickets_user_id ON support_tickets(user_id)"
                ))
                sync_conn.execute(text(
                    "CREATE INDEX ix_support_tickets_status ON support_tickets(status)"
                ))
                logging.info("Migration: created support_tickets table")
            if 'support_messages' not in existing_tables:
                sync_conn.execute(text(
                    "CREATE TABLE support_messages ("
                    " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    " ticket_id INTEGER NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,"
                    " sender VARCHAR(20) NOT NULL,"
                    " text TEXT NOT NULL,"
                    " created_at VARCHAR(30) NOT NULL"
                    ")"
                ))
                sync_conn.execute(text(
                    "CREATE INDEX ix_support_messages_ticket_id ON support_messages(ticket_id)"
                ))
                logging.info("Migration: created support_messages table")

        await conn.run_sync(_check_and_migrate)

    # Seed cache_version row and tariff/menu data if empty
    await _seed_cache_version()
    await _seed_tariffs_and_menus()
    await _backfill_screen_texts()
    await _seed_telemt_free_params()
    await _seed_promo_settings()


async def _seed_cache_version():
    """Ensure cache_version row exists."""
    from sqlalchemy import select, func
    async with async_session() as session:
        count = await session.scalar(select(func.count()).select_from(CacheVersion))
        if not count:
            session.add(CacheVersion(id=1, version=0))
            await session.commit()


async def _seed_tariffs_and_menus():
    """Seed default tariffs and menu screens if tables are empty."""
    from datetime import datetime
    from sqlalchemy import select, func
    import app.locale.lang_ru as lang_ru
    import app.locale.lang_en as lang_en

    async with async_session() as session:
        count = await session.scalar(select(func.count()).select_from(TariffPlan))
        if count and count > 0:
            return

        now = datetime.now().isoformat()

        # Seed tariff plans
        tariffs = [
            TariffPlan(slug="month_30", name_ru="1 Месяц", name_en="1 Month", days=30,
                       sort_order=0, is_active=True, discount_percent=0, created_at=now),
            TariffPlan(slug="month_90", name_ru="3 Месяца", name_en="3 Months", days=90,
                       sort_order=1, is_active=True, discount_percent=0, created_at=now),
            TariffPlan(slug="month_360", name_ru="Год", name_en="1 Year", days=360,
                       sort_order=2, is_active=True, discount_percent=0, created_at=now),
        ]
        session.add_all(tariffs)
        await session.flush()

        # Seed tariff prices for each plan × payment method
        payment_methods = [
            ("stars", "⭐️"),
            ("crypto", "USDT"),
            ("SBP_APAY", "RUB"),
            ("CRYSTAL", "RUB"),
        ]
        for tariff in tariffs:
            for method, currency in payment_methods:
                session.add(TariffPrice(
                    tariff_id=tariff.id, payment_method=method,
                    price=0, currency=currency, is_active=True
                ))

        # Seed menu screens with buttons
        screens_data = [
            {
                "slug": "main_new", "name": "Main Menu (New User)",
                "message_text_ru": lang_ru.start_base + lang_ru.start_new + lang_ru.start_agreement,
                "message_text_en": lang_en.start_base + lang_en.start_new + lang_en.start_agreement,
                "is_system": True,
                "buttons": [
                    ("🔒 Купить Premium", "🔒 Buy Premium", "Premium", 0),
                    ("📱 Инструкция", "📱 Instructions", "Others", 1),
                    ("🆓 Бесплатная версия", "🆓 Free Version", "Free", 2),
                    ("👥 Пригласить друзей", "👥 Invite Friends", "Invite_Friends", 3),
                    ("⚙️ Настройки", "⚙️ Settings", "Settings", 4),
                ]
            },
            {
                "slug": "main_pro", "name": "Main Menu (Pro User)",
                "message_text_ru": lang_ru.start_pro + "{sub_info}" + lang_ru.start_agreement,
                "message_text_en": lang_en.start_pro + "{sub_info}" + lang_en.start_agreement,
                "is_system": True,
                "buttons": [
                    ("🔄 Продлить подписку", "🔄 Extend Subscription", "Extend_Month", 0),
                    ("📱 Инструкция", "📱 Instructions", "Others", 1),
                    ("📊 Моя подписка", "📊 My Subscription", "Sub_Info", 2),
                    ("📲 Устройства", "📲 Devices", "Devices", 3),
                    ("👥 Пригласить друзей", "👥 Invite Friends", "Invite_Friends", 4),
                    ("⚙️ Настройки", "⚙️ Settings", "Settings", 5),
                ]
            },
            {
                "slug": "main_free", "name": "Main Menu (Free User)",
                "message_text_ru": lang_ru.start_free + "{sub_info}" + lang_ru.start_agreement,
                "message_text_en": lang_en.start_free + "{sub_info}" + lang_en.start_agreement,
                "is_system": True,
                "buttons": [
                    ("🔒 Купить Premium", "🔒 Buy Premium", "Premium", 0),
                    ("📱 Инструкция", "📱 Instructions", "Others", 1),
                    ("📊 Моя подписка", "📊 My Subscription", "Sub_Info", 2),
                    ("📲 Устройства", "📲 Devices", "Devices", 3),
                    ("👥 Пригласить друзей", "👥 Invite Friends", "Invite_Friends", 4),
                    ("⚙️ Настройки", "⚙️ Settings", "Settings", 5),
                ]
            },
            {
                "slug": "pay_methods", "name": "Payment Methods",
                "message_text_ru": lang_ru.text_pay_method,
                "message_text_en": lang_en.text_pay_method,
                "is_system": True,
                "buttons": [
                    ("⭐️ Telegram Stars", "⭐️ Telegram Stars", "Stars_Plans", 0),
                    ("💎 Криптовалюта", "💎 Cryptocurrency", "Crypto_Plans", 1),
                    ("💳 Crystal Pay", "💳 Crystal Pay", "Crystal_plans", 2),
                    ("💳 СБП / Apple Pay", "💳 SBP / Apple Pay", "SBP_Apay", 3),
                    ("🎁 У меня есть промокод", "🎁 I have a promo code", "Enter_Promo", 4, "show_promo"),
                    ("◀️ Назад", "◀️ Back", "Main", 5),
                ]
            },
            {
                "slug": "settings", "name": "Settings",
                "message_text_ru": "⚙️ Настройки",
                "message_text_en": "⚙️ Settings",
                "is_system": True,
                "buttons": [
                    ("🌐 Язык", "🌐 Language", "Change_Language", 0),
                    ("📄 Пользовательское соглашение", "📄 User Agreement", "Agreement", 1),
                    ("🔒 Политика конфиденциальности", "🔒 Privacy Policy", "Privacy", 2),
                    ("◀️ На главную", "◀️ Main Menu", "Main", 3),
                ]
            },
        ]

        for screen_data in screens_data:
            screen = MenuScreen(
                slug=screen_data["slug"],
                name=screen_data["name"],
                message_text_ru=screen_data["message_text_ru"],
                message_text_en=screen_data["message_text_en"],
                is_system=screen_data["is_system"],
                is_active=True,
            )
            session.add(screen)
            await session.flush()

            for btn_data in screen_data["buttons"]:
                text_ru, text_en, callback, sort = btn_data[0], btn_data[1], btn_data[2], btn_data[3]
                visibility = btn_data[4] if len(btn_data) > 4 else "always"
                session.add(MenuButton(
                    screen_id=screen.id, text_ru=text_ru, text_en=text_en,
                    callback_data=callback, row=sort, col=0, sort_order=sort,
                    button_type="callback", is_active=True, visibility_condition=visibility,
                ))

        await session.commit()
        logging.info("Seed: tariff plans, prices, and menu screens created")


async def _backfill_screen_texts():
    """Backfill empty message_text_ru/en for existing screens."""
    from sqlalchemy import select
    import app.locale.lang_ru as lang_ru
    import app.locale.lang_en as lang_en

    texts = {
        "main_new": {
            "ru": lang_ru.start_base + lang_ru.start_new + lang_ru.start_agreement,
            "en": lang_en.start_base + lang_en.start_new + lang_en.start_agreement,
        },
        "main_pro": {
            "ru": lang_ru.start_pro + "{sub_info}" + lang_ru.start_agreement,
            "en": lang_en.start_pro + "{sub_info}" + lang_en.start_agreement,
        },
        "main_free": {
            "ru": lang_ru.start_free + "{sub_info}" + lang_ru.start_agreement,
            "en": lang_en.start_free + "{sub_info}" + lang_en.start_agreement,
        },
        "pay_methods": {
            "ru": lang_ru.text_pay_method,
            "en": lang_en.text_pay_method,
        },
        "settings": {
            "ru": "⚙️ Настройки",
            "en": "⚙️ Settings",
        },
    }

    async with async_session() as session:
        result = await session.execute(
            select(MenuScreen).where(MenuScreen.slug.in_(texts.keys()))
        )
        screens = result.scalars().all()
        updated = 0
        for screen in screens:
            t = texts.get(screen.slug)
            if not t:
                continue
            if not screen.message_text_ru:
                screen.message_text_ru = t["ru"]
                updated += 1
            if not screen.message_text_en:
                screen.message_text_en = t["en"]
                updated += 1
        if updated:
            await session.commit()
            logging.info("Backfill: updated %d screen text fields", updated)


async def _seed_telemt_free_params():
    """Ensure telemt_free_params has a default row."""
    from sqlalchemy import select, func
    async with async_session() as session:
        count = await session.scalar(select(func.count()).select_from(TelmtFreeParams))
        if not count:
            session.add(TelmtFreeParams(id=1, max_tcp_conns=None, max_unique_ips=None,
                                        data_quota_bytes=None, expire_days=30))
            await session.commit()
            logging.info("Seed: telemt_free_params default row created")


async def _seed_promo_settings():
    """Ensure promo_settings has a default row."""
    from sqlalchemy import select, func
    async with async_session() as session:
        count = await session.scalar(select(func.count()).select_from(PromoSettings))
        if not count:
            session.add(PromoSettings(id=1, default_discount_percent=20))
            await session.commit()
            logging.info("Seed: promo_settings default row created")
