from datetime import datetime, timedelta

from sqlalchemy import select, update, func, delete, exists
from sqlalchemy.orm import aliased
import string
import random
from app.database.models import User, Transaction, Promo, PromoRedemption, DisabledUser
from app.database.models import async_session

# Shared query helpers — see packages/common_db/common_db/repo/. These take
# an explicit session and never commit; the wrappers in this file keep
# their existing "open a session, maybe commit" shape but delegate the
# actual SELECT to the canonical helper so the predicate (e.g. "paid
# user") is defined in exactly one place.
from common_db.repo import balance as _repo_balance
from common_db.repo import users as _repo_users
from common_db.repo import promos as _repo_promos
from common_db.repo import system as _repo_system


async def set_user(tg_id, username=None):
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)

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
    # NOTE: this returns a status code (404/200), not a User. Confusing
    # name — handlers use it as a "does this user exist" probe. For the
    # actual User row, use common_db.repo.users.get_user_by_tg_id directly.
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
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
        return await _repo_users.get_user_by_username(session, username)


async def get_user_by_vless_uuid(vless_uuid: str) -> dict | None:
    """Lookup local user by Remnawave VLESS UUID (for inbound panel webhooks)."""
    if not vless_uuid:
        return None
    async with async_session() as session:
        user = await _repo_users.get_user_by_vless_uuid(session, vless_uuid)
        if not user:
            return None
        return {
            "tg_id": user.tg_id,
            "is_banned": bool(user.is_banned),
        }


async def create_user_with_info(tg_id: int, username: str, vless_uuid: str = None, api_provider: str = "remnawave"):
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


async def update_user_api_info(
    tg_id: int = 0,
    username: str = 0,
    vless_uuid: str = None,
    api_provider: str = None,
    rw_id: int | None = None,
):
    """
    Обновляет информацию пользователя об API провайдере

    Args:
        tg_id: Telegram ID пользователя
        username (str): Telegram username
        vless_uuid (str): UUID для VLESS конфигурации
        api_provider (str): Провайдер API (marzban или remnawave)
        rw_id: Remnawave panel numeric user id

    Returns:
        bool: True если успешно, False если пользователь не найден
    """
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)

        if not user:
            return False
        if username is not None:
            user.username = username
        if vless_uuid is not None:
            user.vless_uuid = f"{vless_uuid}"
        if api_provider is not None:
            user.api_provider = api_provider
        if rw_id is not None:
            user.rw_id = rw_id

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
        user = await _repo_users.get_user_by_username(session, username)
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
        user = await _repo_users.get_user_by_username(session, username)

        if not user:
            return None

        return {
            "id": user.id,
            "tg_id": user.tg_id,
            "username": user.username,
            "vless_uuid": user.vless_uuid,
            "api_provider": user.api_provider,
            "vip": user.vip,
        }


async def set_user_language(tg_id: int, language: str) -> bool:
    """Устанавливает язык интерфейса пользователя"""
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            return False
        user.language = language
        await session.commit()
        return True


async def get_user_language(tg_id: int) -> str | None:
    """Получает язык интерфейса пользователя (None если не выбран)"""
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
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
        user = await _repo_users.get_user_by_tg_id(session, user_tg_id)

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
        user = await _repo_users.get_user_by_tg_id(session, user_tg_id)

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
                "user_email": user.email,
                "android_user_id": transaction.android_user_id,
                "days_ordered": transaction.days_ordered,
                "payment_method": transaction.payment_method,
                "amount": transaction.amount,
                "created_at": transaction.created_at,
                "tariff_slug": transaction.tariff_slug,
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
    from common_db.repo import transactions as _repo_transactions

    async with async_session() as session:
        deleted = await _repo_transactions.cleanup_stale_transactions(session, hours=hours)
        await session.commit()
        return deleted


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
        return await _repo_users.count_users(session)


async def get_users_count_by_api() -> dict:
    async with async_session() as session:
        result = await session.execute(
            select(User.api_provider, func.count()).group_by(User.api_provider)
        )
        return {row[0] or "unknown": row[1] for row in result.all()}


async def get_paid_users_count() -> int:
    async with async_session() as session:
        return await _repo_users.count_paid_users(session)


async def get_free_users_count() -> int:
    # Free = total - paid. We re-use the canonical "paid" subquery so the
    # predicate stays in one place (see common_db.repo.users).
    async with async_session() as session:
        active_paid_sq = _repo_users.active_paid_user_ids_subquery()
        result = await session.scalar(
            select(func.count()).select_from(User).where(
                ~User.id.in_(active_paid_sq)
            )
        )
        return result or 0


async def get_users_paginated(page: int, per_page: int = 10,
                              sort: str = "id", search: str = ""):
    now = datetime.now()
    now_iso = now.isoformat(timespec='seconds')
    async with async_session() as session:
        # The "is_paid" flag and the "paid|free" filter both use the same
        # canonical predicate (Transaction.order_status IN PAID + not expired).
        # See common_db.repo.users.PAID_ORDER_STATUSES.
        has_tx = exists(
            select(Transaction.user_id).where(
                Transaction.user_id == User.id,
                Transaction.order_status.in_(_repo_users.PAID_ORDER_STATUSES),
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
        active_paid_sq = _repo_users.active_paid_user_ids_subquery(now)
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
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
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
            "vip": bool(user.vip),
        }


async def ban_user(tg_id: int) -> bool:
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            return False
        user.is_banned = True
        await session.commit()
        return True


async def unban_user(tg_id: int) -> bool:
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            return False
        user.is_banned = False
        await session.commit()
        return True


async def delete_user_from_db(tg_id: int) -> bool:
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
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
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            return False
        return bool(user.is_banned)


async def get_all_user_tg_ids() -> list[int]:
    # Helper filters out NULL tg_ids (android-only users have no Telegram
    # account). Broadcast loops always want this — if they tried to send
    # to None they would crash. Behaviour change vs. pre-unification is
    # intentional: it removes a latent bug.
    async with async_session() as session:
        return await _repo_users.get_all_tg_ids(session)


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
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            return False
        user.email = email
        await session.commit()
        return True


async def get_user_email(tg_id: int) -> str | None:
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        return user.email if user else None


async def update_username(tg_id: int, username: str) -> bool:
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
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
        "discount_percent": promo.discount_percent,
        "credit_grant": promo.credit_grant,
        "used_promo_consumed": bool(promo.used_promo_consumed),
    }


async def get_promo_by_tg_id(tg_id: int) -> dict | None:
    async with async_session() as session:
        promo = await _repo_promos.get_promo_by_tg_id(session, tg_id)
        return _promo_to_dict(promo) if promo else None


async def get_promo_by_code(promo_code: str) -> dict | None:
    async with async_session() as session:
        promo = await _repo_promos.get_promo_by_code(session, promo_code)
        return _promo_to_dict(promo) if promo else None


async def get_or_create_referral_code(tg_id: int) -> str:
    """Return the user's own referral code, creating the promo row if absent."""
    async with async_session() as session:
        code = await _repo_promos.get_or_create_referral_code(session, tg_id)
        await session.commit()
        return code


async def redeem_promo_for_user(tg_id: int, promo_code: str):
    """Validate + record a promo redemption. Returns the repo RedeemResult
    (``.ok`` + ``.reason`` + resolved ``.discount_percent`` on success).

    Single entry point for both deeplink auto-activation and manual entry —
    enforces all rules (referral-new-only, one-active, no-duplicate) via
    common_db.repo.promos.
    """
    async with async_session() as session:
        result = await _repo_promos.redeem_promo(session, tg_id, promo_code)
        await session.commit()
        return result


async def get_default_promo_discount() -> int:
    """The default discount % a referral/promotional code grants when it has
    no per-code override. Reads promo_settings (auto-seeded)."""
    async with async_session() as session:
        pct = await _repo_system.get_default_discount_percent(session)
        await session.commit()
        return pct


async def get_promo_reward_settings() -> tuple[int, int]:
    """Return (days_reward_per_30, reward_cap_days) from promo_settings.

    Single source of truth for referral reward tunables — replaces the
    config.yml ``promo_days_reward`` constant. Auto-seeds the singleton.
    """
    async with async_session() as session:
        per_30 = await _repo_system.get_days_reward_per_30(session)
        cap = await _repo_system.get_reward_cap_days(session)
        await session.commit()  # persist auto-seeded PromoSettings
        return per_30, cap


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


async def get_user_bonus_credits(tg_id: int) -> int:
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            return 0
        return await _repo_balance.get_balance(session, user.id)


async def can_use_promo(tg_id: int) -> bool:
    """Users can always try to redeem promo codes (credits stack)."""
    return True


async def get_default_promo_credit_grant() -> int:
    async with async_session() as session:
        grant = await _repo_system.get_default_credit_grant(session)
        await session.commit()
        return grant


async def process_referral_reward_for_purchase(tg_id: int, days: int):
    """Compute referral owner reward after a paid purchase. Returns ReferralRewardInfo or None."""
    from common_db.repo import referral_rewards as _repo_referral

    async with async_session() as session:
        info = await _repo_referral.record_purchase_and_compute_reward(
            session, tg_id, days
        )
        await session.commit()
        return info


async def get_promos_paginated(page: int, per_page: int = 10):
    """Paginated promo catalog (bot admin). Delegates to the shared repo
    query. NOTE: page is now 1-based to match the dashboard."""
    async with async_session() as session:
        return await _repo_promos.list_promos_paginated(session, page, per_page)


async def delete_promo(promo_code: str) -> bool:
    """Delete a promo code and its redemptions."""
    async with async_session() as session:
        promo = await _repo_promos.get_promo_by_code(session, promo_code)
        if not promo:
            return False
        await session.execute(
            delete(PromoRedemption).where(PromoRedemption.promo_code == promo_code)
        )
        await session.execute(
            delete(Promo).where(Promo.promo_code == promo_code)
        )
        await session.commit()
        return True


async def get_used_promo_with_discount(tg_id: int) -> dict | None:
    """Legacy shim — returns balance instead of discount."""
    balance = await get_user_bonus_credits(tg_id)
    if balance <= 0:
        return None
    return {"balance": balance}


async def get_promo_usage_users(promo_code: str) -> list[dict]:
    """Users who redeemed ``promo_code`` (tg_id + username)."""
    async with async_session() as session:
        return await _repo_promos.get_promo_redeemers(session, promo_code)


# ==================== Sub Clean / VIP functions ====================

async def get_free_non_vip_remnawave_users() -> list[dict]:
    """Получает пользователей RemnaWave без транзакций, без VIP, не забаненных."""
    async with async_session() as session:
        has_any_tx = exists(
            select(Transaction.user_id).where(Transaction.user_id == User.id)
        ).correlate(User)

        result = await session.execute(
            select(User).where(
                ~has_any_tx,
                (User.vip == 0) | (User.vip == None),  # noqa: E711
                User.api_provider == "remnawave",
                (User.is_banned == False) | (User.is_banned == None),  # noqa: E712
            )
        )
        users = result.scalars().all()
        return [
            {
                "tg_id": u.tg_id,
                "username": u.username,
                "vless_uuid": u.vless_uuid,
            }
            for u in users
        ]


async def create_disabled_user(tg_id: int, original_status: str) -> None:
    """Записывает пользователя в disabled_users перед отключением."""
    async with async_session() as session:
        existing = await session.scalar(
            select(DisabledUser).where(DisabledUser.tg_id == tg_id)
        )
        if existing:
            existing.original_status = original_status
            existing.disabled_at = datetime.now().isoformat(timespec='seconds')
        else:
            session.add(DisabledUser(
                tg_id=tg_id,
                original_status=original_status,
                disabled_at=datetime.now().isoformat(timespec='seconds'),
            ))
        await session.commit()


async def get_disabled_user(tg_id: int) -> dict | None:
    """Получает запись disabled_user для восстановления статуса."""
    async with async_session() as session:
        du = await session.scalar(
            select(DisabledUser).where(DisabledUser.tg_id == tg_id)
        )
        if not du:
            return None
        return {
            "tg_id": du.tg_id,
            "original_status": du.original_status,
            "disabled_at": du.disabled_at,
        }


async def delete_disabled_user(tg_id: int) -> bool:
    """Удаляет запись из disabled_users после восстановления."""
    async with async_session() as session:
        result = await session.execute(
            delete(DisabledUser).where(DisabledUser.tg_id == tg_id)
        )
        await session.commit()
        return result.rowcount > 0


async def set_user_vip(tg_id: int, vip: int) -> bool:
    """Устанавливает/снимает VIP флаг пользователя."""
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            return False
        user.vip = vip
        await session.commit()
        return True


async def user_has_transactions(tg_id: int) -> bool:
    """Проверяет, есть ли у пользователя хотя бы одна транзакция (платная подписка).

    NOTE: this is a *different* predicate from
    common_db.repo.users.user_has_active_paid_transaction — it returns
    True for any historical transaction, including expired/cancelled ones.
    Callers checking "is this user currently paid?" should use that helper.
    """
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            return False
        from sqlalchemy import exists as sa_exists
        has_tx = await session.scalar(
            select(sa_exists(
                select(Transaction.transaction_id).where(Transaction.user_id == user.id)
            ))
        )
        return bool(has_tx)


async def get_telemt_free_params() -> dict:
    """Возвращает параметры для создания бесплатного пользователя Telemt.

    Auto-seeds the singleton row on a fresh DB so callers always see the
    canonical defaults (expire_days=30, the rest NULL). See
    common_db.repo.system.get_telmt_free_params.
    """
    async with async_session() as session:
        row = await _repo_system.get_telmt_free_params(session)
        await session.commit()  # persist any auto-seeded row
        return {
            "max_tcp_conns": row.max_tcp_conns,
            "max_unique_ips": row.max_unique_ips,
            "data_quota_bytes": row.data_quota_bytes,
            "expire_days": row.expire_days,
        }


async def update_telemt_free_params(
    max_tcp_conns: int = None,
    max_unique_ips: int = None,
    data_quota_bytes: int = None,
    expire_days: int = 30,
) -> bool:
    """Обновляет параметры для создания бесплатного пользователя Telemt."""
    async with async_session() as session:
        row = await _repo_system.get_telmt_free_params(session)
        row.max_tcp_conns = max_tcp_conns
        row.max_unique_ips = max_unique_ips
        row.data_quota_bytes = data_quota_bytes
        row.expire_days = expire_days
        await session.commit()
        return True