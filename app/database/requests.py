from sqlalchemy import select, update, func, delete, exists

from app.database.models import User, Transaction
from app.database.models import async_session


async def set_user(tg_id):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))

        if not user:
            session.add(User(tg_id=tg_id))
            await session.commit()


async def get_users():
    async with async_session() as session:
        return await session.scalars(select(User))

async def get_user_by_tg_id(tg_id):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return 404
        else:
            return 200


async def get_user_by_username(username: str):
    """
    Получает пользователя по Telegram username

    Args:
        username (str): Telegram username пользователя

    Returns:
        User: Объект пользователя или None
    """
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.username == username))
        return user


async def create_user_with_info(tg_id: int, username: str, vless_uuid: str = None, api_provider: str = "marzban"):
    """
    Создает нового пользователя с полной информацией

    Args:
        tg_id (int): Telegram ID пользователя
        username (str): Telegram username
        vless_uuid (str): UUID для VLESS конфигурации
        api_provider (str): Провайдер API (marzban или remnawave)

    Returns:
        User: Созданный объект пользователя
    """
    async with async_session() as session:
        new_user = User(
            tg_id=tg_id,
            username=username,
            vless_uuid=f"{vless_uuid}",
            api_provider=api_provider
        )
        session.add(new_user)
        await session.commit()
        return new_user


async def update_user_api_info(tg_id: int = 0, username: str = 0, vless_uuid: str = None, api_provider: str = None):
    """
    Обновляет информацию пользователя об API провайдере

    Args:
        tg_id: Telegram ID пользователя
        username (str): Telegram username
        vless_uuid (str): UUID для VLESS конфигурации
        api_provider (str): Провайдер API (marzban или remnawave)

    Returns:
        bool: True если успешно, False если пользователь не найден
    """
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))

        if not user:
            return False
        if username is not None:
            user.username = username
        if vless_uuid is not None:
            user.vless_uuid = f"{vless_uuid}"
        if api_provider is not None:
            user.api_provider = api_provider

        await session.commit()
        return True


async def update_user_vless_uuid(tg_id: int, username: str, vless_uuid: str):
    """
    Обновляет UUID пользователя

    Args:
        tg_id:
        username (str): Telegram username
        vless_uuid (str): Новый UUID для VLESS конфигурации

    Returns:
        bool: True если успешно, False если пользователь не найден
    """
    return await update_user_api_info(tg_id=tg_id, username=username, vless_uuid=vless_uuid)


async def get_user_api_provider(username: str) -> str:
    """
    Получает API провайдера пользователя

    Args:
        username (str): Telegram username

    Returns:
        str: Имя API провайдера (marzban/remnawave) или None
    """
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.username == username))
        return user.api_provider if user else None


async def get_full_username_info(username: str) -> dict:
    """
    Получает полную информацию пользователя по username

    Args:
        username (str): Telegram username

    Returns:
        dict: Словарь с информацией пользователя или None
    """
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.username == username))

        if not user:
            return None

        return {
            "id": user.id,
            "tg_id": user.tg_id,
            "username": user.username,
            "vless_uuid": user.vless_uuid,
            "api_provider": user.api_provider
        }


# Пример создания новой транзакции
async def create_transaction(user_tg_id: int, user_transaction: str, username: str, days: int, uuid: str = 'None'):
    async with async_session() as session:
        # Находим пользователя по tg_id
        user = await session.scalar(
            select(User).where(User.tg_id == user_tg_id)
        )

        if user:
            # Создаем новую транзакцию
            new_transaction = Transaction(
                transaction_id=user_transaction,
                vless_uuid = uuid,
                username=username,
                order_status='created',
                delivery_status=0,
                days_ordered=days,
                user_id=user.id  # Используем id пользователя из таблицы users
            )

            session.add(new_transaction)
            await session.commit()
            return new_transaction
        return None


# Пример получения всех транзакций пользователя
async def get_user_transactions(user_tg_id: int):
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.tg_id == user_tg_id)
        )

        if user:
            # Благодаря отношениям мы можем получить все транзакции пользователя
            return user.transactions
        return []


async def get_full_transaction_info(transaction_id: str):
    """
    Получает полную информацию о транзакции и связанном пользователе

    Args:
        transaction_id (str): Идентификатор транзакции

    Returns:
        dict: Словарь с информацией о транзакции и пользователе или None
    """
    async with async_session() as session:
        query = (
            select(Transaction, User)
            .join(User, User.id == Transaction.user_id)
            .where(Transaction.transaction_id == transaction_id)
        )

        result = await session.execute(query)
        row = result.first()

        if row:
            transaction, user = row
            return {
                "transaction_id": transaction.transaction_id,
                "vless_uuid": transaction.vless_uuid,
                "username": transaction.username,
                "status": transaction.order_status,
                "user_tg_id": user.tg_id,
                "user_db_id": user.id,
                "days_ordered": transaction.days_ordered
                # Добавьте другие поля по необходимости
            }
        else:
            return None


async def get_full_transaction_info_by_id(user_id: int):
    """
    Получает полную информацию о транзакции и связанном пользователе

    Args:
        user_id (int): Идентификатор пользователя

    Returns:
        dict: Словарь с информацией о транзакции и пользователе или None
    """
    async with async_session() as session:
        query = (
            select(Transaction, User)
            .join(User, User.id == Transaction.user_id)
            .where(User.tg_id == user_id)
        )

        result = await session.execute(query)
        row = result.first()

        if row:
            transaction, user = row
            return {
                "transaction_id": transaction.transaction_id,
                "vless_uuid": transaction.vless_uuid,
                "username": transaction.username,
                "status": transaction.order_status,
                "delivery_status": transaction.delivery_status,
                "user_tg_id": user.tg_id,
                "user_db_id": user.id,
                "days_ordered": transaction.days_ordered
                # Добавьте другие поля по необходимости
            }
        else:
            return 404


async def update_order_status(transaction_id: str, new_status: str) -> bool:
    """
    Обновляет статус заказа по идентификатору транзакции с предварительной проверкой

    Args:
        transaction_id: Идентификатор транзакции
        new_status: Новый статус заказа

    Returns:
        bool: True если обновление прошло успешно, False если транзакция не найдена
    """
    async with async_session() as session:
        # Сначала проверяем существование транзакции
        result = await session.execute(
            select(Transaction).where(Transaction.transaction_id == transaction_id)
        )
        transaction = result.scalar_one_or_none()

        if transaction is None:
            return False

        # Обновляем статус
        transaction.order_status = new_status
        await session.commit()
        return True


async def claim_order_for_processing(transaction_id: str) -> bool:
    """
    Атомарно проверяет статус заказа и переводит его в 'confirmed'.
    Возвращает True только если статус БЫЛ 'created' — гарантирует,
    что только один обработчик получит право на доставку подписки.

    Args:
        transaction_id: Идентификатор транзакции

    Returns:
        bool: True если заказ успешно захвачен для обработки, False если уже обработан
    """
    async with async_session() as session:
        result = await session.execute(
            update(Transaction)
            .where(
                Transaction.transaction_id == transaction_id,
                Transaction.order_status == "created"
            )
            .values(order_status="confirmed")
        )
        await session.commit()
        return result.rowcount > 0


async def update_delivery_status(tg_id: int, new_delivery_status: int):
    async with async_session() as session:
        # Находим пользователя по tg_id
        user = await session.scalar(
            select(User).where(User.tg_id == tg_id)
        )

        if user:
            # Обновляем все транзакции пользователя
            await session.execute(
                update(Transaction)
                .where(Transaction.user_id == user.id)
                .values(delivery_status=new_delivery_status)
            )
            await session.commit()
            print(f"Updated delivery_status to {new_delivery_status} for user {tg_id}")
        else:
            print(f"User with tg_id {tg_id} not found")


# ==================== Admin panel functions ====================

async def get_users_count() -> int:
    async with async_session() as session:
        result = await session.scalar(select(func.count()).select_from(User))
        return result or 0


async def get_users_count_by_api() -> dict:
    async with async_session() as session:
        result = await session.execute(
            select(User.api_provider, func.count()).group_by(User.api_provider)
        )
        return {row[0] or "unknown": row[1] for row in result.all()}


async def get_paid_users_count() -> int:
    async with async_session() as session:
        result = await session.scalar(
            select(func.count(func.distinct(Transaction.user_id))).select_from(Transaction)
        )
        return result or 0


async def get_free_users_count() -> int:
    total = await get_users_count()
    paid = await get_paid_users_count()
    return total - paid


async def get_users_paginated(page: int, per_page: int = 10,
                              sort: str = "id", search: str = ""):
    async with async_session() as session:
        has_tx = exists(
            select(Transaction.user_id).where(Transaction.user_id == User.id)
        ).correlate(User).label("is_paid")

        base = select(User, has_tx)

        # Фильтр по поиску
        if search:
            base = base.where(User.username.ilike(f"%{search}%"))

        # Фильтр по платным/бесплатным
        if sort == "paid":
            base = base.where(
                User.id.in_(
                    select(Transaction.user_id).distinct()
                )
            )
        elif sort == "free":
            base = base.where(
                ~User.id.in_(
                    select(Transaction.user_id).distinct()
                )
            )

        # Подсчёт после фильтрации
        count_q = select(func.count()).select_from(base.subquery())
        total = await session.scalar(count_q) or 0

        # Сортировка
        if sort == "alpha":
            base = base.order_by(User.username.asc())
        else:
            base = base.order_by(User.id)

        result = await session.execute(
            base.offset(page * per_page).limit(per_page)
        )
        rows = result.all()
        return [(row[0], row[1]) for row in rows], total


async def get_user_full_info_by_tg_id(tg_id: int) -> dict | None:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None
        return {
            "id": user.id,
            "tg_id": user.tg_id,
            "username": user.username,
            "vless_uuid": user.vless_uuid,
            "api_provider": user.api_provider,
            "is_banned": bool(user.is_banned),
            "email": user.email,
        }


async def ban_user(tg_id: int) -> bool:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return False
        user.is_banned = True
        await session.commit()
        return True


async def unban_user(tg_id: int) -> bool:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return False
        user.is_banned = False
        await session.commit()
        return True


async def delete_user_from_db(tg_id: int) -> bool:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return False
        # Удаляем связанные транзакции
        await session.execute(
            delete(Transaction).where(Transaction.user_id == user.id)
        )
        await session.execute(
            delete(User).where(User.id == user.id)
        )
        await session.commit()
        return True


async def is_user_banned(tg_id: int) -> bool:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return False
        return bool(user.is_banned)


async def get_all_user_tg_ids() -> list[int]:
    async with async_session() as session:
        result = await session.execute(select(User.tg_id))
        return [row[0] for row in result.all()]


async def delete_users_bulk(tg_ids: list[int]) -> int:
    if not tg_ids:
        return 0
    async with async_session() as session:
        # Получаем внутренние id пользователей
        result = await session.execute(
            select(User.id).where(User.tg_id.in_(tg_ids))
        )
        user_ids = [row[0] for row in result.all()]
        if not user_ids:
            return 0
        # Удаляем транзакции
        await session.execute(
            delete(Transaction).where(Transaction.user_id.in_(user_ids))
        )
        # Удаляем пользователей
        await session.execute(
            delete(User).where(User.id.in_(user_ids))
        )
        await session.commit()
        return len(user_ids)


async def get_users_without_username() -> list[int]:
    async with async_session() as session:
        result = await session.execute(
            select(User.tg_id).where(
                (User.username == None) | (User.username == "")  # noqa: E711
            )
        )
        return [row[0] for row in result.all()]


async def update_user_email(tg_id: int, email: str) -> bool:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return False
        user.email = email
        await session.commit()
        return True


async def get_user_email(tg_id: int) -> str | None:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        return user.email if user else None


async def update_username(tg_id: int, username: str) -> bool:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return False
        user.username = username
        await session.commit()
        return True