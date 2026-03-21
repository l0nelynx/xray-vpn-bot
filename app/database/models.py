import logging

from sqlalchemy import BigInteger, String, ForeignKey, Index, Integer, Boolean, text, inspect
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

engine = create_async_engine(url='sqlite+aiosqlite:///db.sqlite3')

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

    # API провайдер, на котором зарегистрирован пользователь (marzban/remnawave)
    api_provider: Mapped[str] = mapped_column(String(50), default="marzban")

    # Email пользователя (для поиска в RemnaWave)
    email: Mapped[str] = mapped_column(String(100), nullable=True)

    # Флаг бана пользователя
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=True)

    # Язык интерфейса пользователя (ru/en), None = не выбран
    language: Mapped[str] = mapped_column(String(5), default=None, nullable=True)

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

    # Внешний ключ к таблице users
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # Отношение многие-к-одному с таблицей users
    user: Mapped["User"] = relationship(back_populates="transactions")

    # Добавляем индекс для user_id для ускорения JOIN-запросов
    __table_args__ = (
        Index('ix_transaction_user_id', 'user_id'),
    )


async def async_main():
    async with engine.begin() as conn:
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

            # Миграция: добавляем индекс на username если его ещё нет
            indexes = [idx['name'] for idx in insp.get_indexes('users')]
            if 'ix_user_username' not in indexes:
                sync_conn.execute(text(
                    "CREATE INDEX ix_user_username ON users (username)"
                ))
                logging.info("Migration: added ix_user_username index to users table")

        await conn.run_sync(_check_and_migrate)
