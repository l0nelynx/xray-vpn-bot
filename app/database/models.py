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

    # Добавляем отношение один-ко-многим с таблицей transactions
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")

    __table_args__ = (
        Index('ix_user_username', 'username'),
    )


class Transaction(Base):
    __tablename__ = 'transactions'

    # Уникальный идентификатор транзакции
    transaction_id: Mapped[str] = mapped_column(String(100), primary_key=True)

    # Уникальный идентификатор vless
    vless_uuid: Mapped[str] = mapped_column(String(100))

    # Имя пользователя
    username: Mapped[str] = mapped_column(String(50))

    # Статус заказа
    order_status: Mapped[str] = mapped_column(String(50))

    # Количество дней в заказе
    delivery_status: Mapped[int] = mapped_column(Integer)

    # Количество дней в заказе
    days_ordered: Mapped[int] = mapped_column(BigInteger)

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

            # Миграция: добавляем индекс на username если его ещё нет
            indexes = [idx['name'] for idx in insp.get_indexes('users')]
            if 'ix_user_username' not in indexes:
                sync_conn.execute(text(
                    "CREATE INDEX ix_user_username ON users (username)"
                ))
                logging.info("Migration: added ix_user_username index to users table")

        await conn.run_sync(_check_and_migrate)



# from sqlalchemy import BigInteger
# from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
# from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
# engine = create_async_engine(url='sqlite+aiosqlite:///db.sqlite3')
# async_session = async_sessionmaker(engine)
# class Base(AsyncAttrs, DeclarativeBase):
#     pass
# class User(Base):
#     __tablename__ = 'users'
#     id: Mapped[int] = mapped_column(primary_key=True)
#     tg_id = mapped_column(BigInteger)
# async def async_main():
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)
