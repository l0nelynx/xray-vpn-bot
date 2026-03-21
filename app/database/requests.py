from datetime import datetime, timedelta

from sqlalchemy import select, update, func, delete, exists
from sqlalchemy.orm import aliased
import string
import random
from app.database.models import User, Transaction, Promo
from app.database.models import async_session


async def set_user(tg_id, username=None):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))

        if not user:
            session.add(User(tg_id=tg_id, username=username))
            await session.commit()
        elif username and user.username != username:
            user.username = username
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


async def set_user_language(tg_id: int, language: str) -> bool:
    """Устанавливает язык интерфейса пользователя"""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return False
        user.language = language
        await session.commit()
        return True


async def get_user_language(tg_id: int) -> str | None:
    """Получает язык интерфейса пользователя (None если не выбран)"""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            return None
        return user.language


async def get_user_full_context(tg_id: int) -> dict | None:
    """
    Получает все данные пользователя одним запросом к БД:
    user info + email + api_provider + language + promo.
    Заменяет цепочку get_full_username_info + get_user_email + get_user_api_provider + get_user_language.
    """
    async with async_session() as session:
        result = await session.execute(
            select(User, Promo)
            .outerjoin(Promo, Promo.tg_id == User.tg_id)
            .where(User.tg_id == tg_id)
        )
        row = result.first()
        if not row:
            return None

        user, promo = row
        return {
            "id": user.id,
            "tg_id": user.tg_id,
            "username": user.username,
            "vless_uuid": user.vless_uuid,
            "api_provider": user.api_provider,
            "email": user.email,
            "is_banned": bool(user.is_banned),
            "language": user.language,
            "promo": {
                "promo_code": promo.promo_code,
                "used_promo": promo.used_promo,
                "days_purchased": promo.days_purchased,
                "days_rewarded": promo.days_rewarded,
            } if promo else None,
        }


# Пример создания новой транзакции
async def create_transaction(user_tg_id: int, user_transaction: str, username: str, days: int,
                             uuid: str = 'None', payment_method: str = None, amount: float = None):
    async with async_session() as session:
        # Находим пользователя по tg_id
        user = await session.scalar(
            select(User).where(User.tg_id == user_tg_id)
        )

        if user:
            # Создаем новую транзакцию
            new_transaction = Transaction(
                transaction_id=user_transaction,
                vless_uuid=uuid,
                username=username or f"id_{user_tg_id}",
                order_status='created',
                delivery_status=0,
                days_ordered=days,
                user_id=user.id,
                payment_method=payment_method,
                amount=amount,
                created_at=datetime.now().isoformat(timespec='seconds'),
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
                "days_ordered": transaction.days_ordered,
                "payment_method": transaction.payment_method,
                "amount": transaction.amount,
                "created_at": transaction.created_at,
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
                "days_ordered": transaction.days_ordered,
                "payment_method": transaction.payment_method,
                "amount": transaction.amount,
                "created_at": transaction.created_at,
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
        transaction = await session.scalar(
            select(Transaction).where(
                Transaction.transaction_id == transaction_id,
                Transaction.order_status == "created"
            )
        )
        if not transaction:
            return False

        expire_date = None
        if transaction.created_at and transaction.days_ordered:
            created = datetime.fromisoformat(transaction.created_at)
            expire_date = (created + timedelta(days=transaction.days_ordered)).isoformat(timespec='seconds')

        transaction.order_status = "confirmed"
        transaction.expire_date = expire_date
        await session.commit()
        return True


async def update_delivery_status(transaction_id: str, new_delivery_status: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            update(Transaction)
            .where(Transaction.transaction_id == transaction_id)
            .values(delivery_status=new_delivery_status)
        )
        await session.commit()
        return result.rowcount > 0


async def cleanup_stale_transactions(hours: int = 24) -> int:
    """Удаляет транзакции со статусом 'created', у которых created_at старше hours часов или отсутствует."""
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat(timespec='seconds')
    async with async_session() as session:
        result = await session.execute(
            delete(Transaction).where(
                Transaction.order_status == 'created',
                (Transaction.created_at == None) | (Transaction.created_at < cutoff),  # noqa: E711
            )
        )
        await session.commit()
        return result.rowcount


async def get_user_transactions_detailed(tg_id: int) -> list[dict]:
    """Получает детальную информацию о транзакциях пользователя."""
    async with async_session() as session:
        query = (
            select(Transaction)
            .join(User, User.id == Transaction.user_id)
            .where(User.tg_id == tg_id)
            .order_by(Transaction.created_at.desc())
        )
        result = await session.execute(query)
        transactions = result.scalars().all()
        return [
            {
                "transaction_id": t.transaction_id,
                "payment_method": t.payment_method,
                "amount": t.amount,
                "created_at": t.created_at,
                "order_status": t.order_status,
                "delivery_status": t.delivery_status,
                "days_ordered": t.days_ordered,
                "expire_date": t.expire_date,
            }
            for t in transactions
        ]


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
    now_iso = datetime.now().isoformat(timespec='seconds')
    async with async_session() as session:
        result = await session.scalar(
            select(func.count(func.distinct(Transaction.user_id))).select_from(Transaction).where(
                Transaction.order_status.in_(["confirmed", "delivered"]),
                Transaction.expire_date > now_iso,
            )
        )
        return result or 0


async def get_free_users_count() -> int:
    now_iso = datetime.now().isoformat(timespec='seconds')
    active_paid_sq = select(func.distinct(Transaction.user_id)).where(
        Transaction.order_status.in_(["confirmed", "delivered"]),
        Transaction.expire_date > now_iso,
    )
    async with async_session() as session:
        result = await session.scalar(
            select(func.count()).select_from(User).where(
                ~User.id.in_(active_paid_sq)
            )
        )
        return result or 0


async def get_users_paginated(page: int, per_page: int = 10,
                              sort: str = "id", search: str = ""):
    now_iso = datetime.now().isoformat(timespec='seconds')
    async with async_session() as session:
        has_tx = exists(
            select(Transaction.user_id).where(
                Transaction.user_id == User.id,
                Transaction.order_status.in_(["confirmed", "delivered"]),
                Transaction.expire_date > now_iso,
            )
        ).correlate(User).label("is_paid")

        base = select(User, has_tx)

        # Фильтр по поиску
        if search:
            if search.isdigit():
                base = base.where(
                    (User.username.ilike(f"%{search}%")) | (User.tg_id == int(search))
                )
            else:
                base = base.where(User.username.ilike(f"%{search}%"))

        # Фильтр по платным/бесплатным
        active_paid_sq = select(Transaction.user_id).where(
            Transaction.order_status.in_(["confirmed", "delivered"]),
            Transaction.expire_date > now_iso,
        ).distinct()
        if sort == "paid":
            base = base.where(User.id.in_(active_paid_sq))
        elif sort == "free":
            base = base.where(~User.id.in_(active_paid_sq))

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


async def get_all_users_by_username(username: str) -> list[dict]:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(func.lower(User.username) == username.lower())
        )
        users = result.scalars().all()
        return [
            {"tg_id": u.tg_id, "username": u.username, "is_banned": bool(u.is_banned)}
            for u in users
        ]


# ==================== Promo functions ====================

def _promo_to_dict(promo: Promo) -> dict:
    return {
        "id": promo.id,
        "tg_id": promo.tg_id,
        "promo_code": promo.promo_code,
        "used_promo": promo.used_promo,
        "days_purchased": promo.days_purchased,
        "days_rewarded": promo.days_rewarded,
    }


async def get_promo_by_tg_id(tg_id: int) -> dict | None:
    async with async_session() as session:
        promo = await session.scalar(select(Promo).where(Promo.tg_id == tg_id))
        return _promo_to_dict(promo) if promo else None


async def get_promo_by_code(promo_code: str) -> dict | None:
    async with async_session() as session:
        promo = await session.scalar(select(Promo).where(Promo.promo_code == promo_code))
        return _promo_to_dict(promo) if promo else None


async def create_promo(tg_id: int, promo_code: str) -> Promo:
    async with async_session() as session:
        promo = Promo(tg_id=tg_id, promo_code=promo_code)
        session.add(promo)
        await session.commit()
        return promo


async def use_promo(tg_id: int, promo_code: str) -> bool:
    async with async_session() as session:
        promo = await session.scalar(select(Promo).where(Promo.tg_id == tg_id))
        if promo:
            promo.used_promo = promo_code
        else:
            # User hasn't created their own promo yet — create a record to store used_promo
            while True:
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                existing = await get_promo_by_code(code)
                if not existing:
                    break
            promo = Promo(tg_id=tg_id, promo_code=code, used_promo=promo_code)
            session.add(promo)
        await session.commit()
        return True


async def add_referral_days(promo_code: str, days: int) -> dict | None:
    async with async_session() as session:
        promo = await session.scalar(select(Promo).where(Promo.promo_code == promo_code))
        if not promo:
            return None
        promo.days_purchased += days
        # Capture values before commit (commit expires all attributes)
        tg_id = promo.tg_id
        new_days_purchased = promo.days_purchased
        days_rewarded = promo.days_rewarded
        await session.commit()
        return {
            "tg_id": tg_id,
            "days_purchased": new_days_purchased,
            "days_rewarded": days_rewarded,
        }


async def update_promo_days_rewarded(tg_id: int, days_rewarded: int) -> bool:
    async with async_session() as session:
        promo = await session.scalar(select(Promo).where(Promo.tg_id == tg_id))
        if not promo:
            return False
        promo.days_rewarded = days_rewarded
        await session.commit()
        return True


async def can_use_promo(tg_id: int) -> bool:
    """Возвращает True если пользователь ещё НЕ использовал чужой промокод."""
    async with async_session() as session:
        promo = await session.scalar(select(Promo).where(Promo.tg_id == tg_id))
        if not promo:
            return True
        # Если used_promo заполнен — промокод уже был активирован
        return promo.used_promo is None


async def get_promos_paginated(page: int, per_page: int = 10):
    async with async_session() as session:
        # Subquery: кол-во использований промокода
        UsedPromo = aliased(Promo)
        usage_sq = (
            select(func.count())
            .where(UsedPromo.used_promo == Promo.promo_code)
            .correlate(Promo)
            .scalar_subquery()
            .label("usage_count")
        )

        base = (
            select(Promo, User.username, usage_sq)
            .outerjoin(User, Promo.tg_id == User.tg_id)
        )

        count_q = select(func.count()).select_from(Promo)
        total = await session.scalar(count_q) or 0

        result = await session.execute(
            base.order_by(Promo.id).offset(page * per_page).limit(per_page)
        )
        rows = result.all()

        promos = []
        for promo, owner_username, usage_count in rows:
            promos.append({
                "promo_code": promo.promo_code,
                "owner_username": owner_username,
                "owner_tg_id": promo.tg_id,
                "usage_count": usage_count or 0,
                "days_purchased": promo.days_purchased,
                "days_rewarded": promo.days_rewarded,
            })

        return promos, total


async def get_promo_usage_users(promo_code: str) -> list[dict]:
    async with async_session() as session:
        result = await session.execute(
            select(Promo.tg_id, User.username)
            .outerjoin(User, Promo.tg_id == User.tg_id)
            .where(Promo.used_promo == promo_code)
        )
        return [{"tg_id": row[0], "username": row[1]} for row in result.all()]