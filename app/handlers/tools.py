import time
import uuid

import app.api.remnawave.api as rem
import app.marzban.marzban as mz
import app.database.requests as rq

from aiogram.types import Message, CallbackQuery

from app.settings import bot, secrets
import app.keyboards as kb

import app.marzban.templates as templates
from app.handlers.events import main_menu
from app.handlers.subscription_service import deliver_subscription, SubscriptionType
from app.locale.utils import get_user_lang
from app.keyboards.localized import (
    get_main_marzban_pro_localized, get_main_marzban_free_localized,
    get_connect_localized,
)
from aiogram import Bot
from aiogram.enums.chat_member_status import ChatMemberStatus

import logging

logger = logging.getLogger(__name__)


def time_to_unix(days: int):
    return int(days * 24 * 60 * 60)


async def resolve_user(tg_id: int, username: str) -> tuple[str, dict | int]:
    """
    Определяет API-провайдер пользователя и получает его данные за минимум запросов.
    Объединяет логику detect_user_api_provider + get_user_info.

    Returns:
        (api_provider, user_info) — где user_info = dict с данными или 404
    """
    # 1. Проверяем БД
    api_provider = await rq.get_user_api_provider(username)

    if api_provider == "remnawave":
        info = await get_user_info(username, api="remnawave")
        if info != 404:
            return "remnawave", info

    if api_provider == "marzban" or api_provider is None:
        # Пробуем Marzban
        try:
            async with mz.MarzbanAsync() as marz:
                marz_info = await marz.get_user(name=username)
                if marz_info and marz_info != 404 and not isinstance(marz_info, int):
                    if not api_provider:
                        await rq.update_user_api_info(tg_id, username, api_provider="marzban")
                    return "marzban", marz_info
        except Exception:
            pass

    if api_provider is None:
        # Пробуем RemnaWave (по email, потом по username)
        info = await get_user_info(username, api="remnawave")
        if info != 404:
            await rq.update_user_api_info(tg_id, username, api_provider="remnawave")
            return "remnawave", info

    return "none", 404


async def get_user_days(user_nfo):
    """
    Получает количество оставшихся дней подписки

    Args:
        user_nfo (dict): Информация о пользователе с полем 'expire' (UNIX timestamp)

    Returns:
        int: Количество оставшихся дней (минимум 0)
    """
    expire = user_nfo.get("expire")

    # Если expire это None, значит подписка бесконечна или нет данных
    if expire is None:
        return 999999  # Возвращаем очень большое число для бесконечной подписки

    # Если expire это число, вычисляем дни
    try:
        days_left = round((expire - time.time()) / (24 * 60 * 60))
        return max(0, days_left)  # Не возвращаем отрицательное значение
    except (TypeError, ValueError) as e:
        logger.error(f"Error calculating days from expire value: {expire}, error: {e}")
        return 0


async def get_user_info(username, api: str = "remnawave"):
    """
    Получает информацию о пользователе из указанного API

    Args:
        username (str): Имя пользователя
        api (str): API провайдер (marzban или remnawave)

    Returns:
        dict: Информация о пользователе или 404 если пользователь не найден
    """
    try:
        if api == "marzban":
            async with mz.MarzbanAsync() as marz:
                user_info = await marz.get_user(name=username)
            return user_info
        elif api == "remnawave":
            # REMNAWAVE INTEGRATION — fallback на email если есть
            user_info = None
            db_user = await rq.get_full_username_info(username)
            if db_user and db_user.get("tg_id"):
                email = await rq.get_user_email(db_user["tg_id"])
                if email:
                    user_info = await rem.get_user_from_email(email)
            if not user_info:
                user_info = await rem.get_user_from_username(username)
            if user_info:
                # Преобразуем expire в UNIX timestamp если это datetime объект
                expire = user_info.get("expire")
                if expire is not None:
                    # Если это datetime объект, преобразуем в UNIX timestamp
                    if hasattr(expire, 'timestamp'):
                        expire = int(expire.timestamp())
                    else:
                        # Если это уже число, оставляем как есть
                        expire = int(expire) if expire else None

                # Нормализуем ответ для совместимости
                return {
                    "status": user_info.get("status", "active"),
                    "expire": expire,
                    "subscription_url": user_info.get("subscription_url"),
                    "data_limit": user_info.get("data_limit"),
                }
            return 404
        else:
            logger.warning(f"Unknown API provider: {api}")
            return 404
    except Exception as e:
        logger.error(f"Error getting user info from {api}: {e}")
        return 404


async def add_new_user_info(
    name: str,
    userid: int,
    limit: int = 0,
    res_strat: str = "no_reset",
    expire_days: int = 30,
    template: dict = templates.vless_template,
    api: str = "remnawave",
    email: str = None,
    description: str = "created by backend v2",
    squad_id: str = secrets.get('rw_free_id'),
    external_squad_id: str = None
):
    """
    Добавляет нового пользователя в указанный API провайдер

    Args:
        name (str): Имя пользователя
        userid (int): ID пользователя (Telegram ID)
        limit (int): Лимит трафика в GB (0 = без лимита)
        res_strat (str): Стратегия сброса трафика (для Marzban: no_reset, day, week, month, year)
        expire_days (int): Количество дней действия подписки
        template (dict): Шаблон конфигурации (для Marзban)
        api (str): API провайдер (marzban или remnawave)
        email (str): Email пользователя (для RemnaWave)
        description (str): Описание пользователя
        squad_id (str): ID группы пользователей в RemnaWave
        external_squad_id (str): ID внешней группы для отображения в RemnaWave (опционально)

    Returns:
        dict: Информация о созданном пользователе
    """
    try:
        # Защита от передачи UNIX timestamp вместо дней
        # Если значение больше чем разумное количество дней (10 лет = 3650 дней),
        # то это вероятно UNIX timestamp
        if expire_days > 10000:
            # Это UNIX timestamp, преобразуем обратно в дни
            current_time = time.time()
            expire_days = max(1, round((expire_days - current_time) / (24 * 60 * 60)))
            logger.warning(f"Warning: expire_days was UNIX timestamp, converted to {expire_days} days")

        if api == "marzban":
            async with mz.MarzbanAsync() as marz:
                buyer_nfo = await marz.add_user(
                    template=template,
                    name=f"{name}",
                    usrid=f"{userid}",
                    limit=limit,
                    res_strat=res_strat,
                    expire=(int(time.time() + time_to_unix(expire_days)))
                )

            # Сохраняем информацию об API провайдере в БД
            await rq.update_user_api_info(
                username=name,
                api_provider="marzban"
            )
            return buyer_nfo

        elif api == "remnawave":
            # REMNAWAVE INTEGRATION с расширенными параметрами
            if email is None:
                email = f"{name}@marzban.ru"

            buyer_nfo = await rem.create_user(
                username=name,
                days=expire_days,
                limit_gb=limit,
                descr=description,
                email=email,
                squad_id=squad_id,
                telegram_id=userid,
                external_squad_id=external_squad_id
            )

            if buyer_nfo and buyer_nfo.get("uuid"):
                # Сохраняем информацию об API провайдере и UUID в БД
                await rq.update_user_api_info(
                    tg_id=userid,
                    username=name,
                    vless_uuid=buyer_nfo.get("uuid"),
                    api_provider="remnawave"
                )
                logger.info(f"DB updated with RemnaWave user info for {name}")

            return buyer_nfo
        else:
            logger.warning(f"Unknown API provider: {api}")
            return None

    except Exception as e:
        logger.error(f"Error adding new user to {api}: {e}")
        return None


async def set_user_info(
    name: str,
    limit: int = 0,
    res_strat: str = "no_reset",
    expire_days: int = 30,
    template: dict = templates.vless_template,
    api: str = "remnawave",
    description: str = "updated by backend v2",
    squad_id: str = secrets.get('rw_free_id'),
    external_squad_id: str = None
):
    """
    Обновляет информацию существующего пользователя

    Args:
        name (str): Имя пользователя
        limit (int): Лимит трафика в GB (0 = без лимита)
        res_strat (str): Стратегия сброса трафика (для Marzban)
        expire_days (int): Количество дней действия подписки
        template (dict): Шаблон конфигурации (для Marzban)
        api (str): API провайдер (marzban или remnawave)
        description (str): Описание пользователя
        squad_id (str): ID внутреннего squad пользователей в RemnaWave
        external_squad_id (str): ID внешнего squad для отображения в RemnaWave (опционально)

    Returns:
        dict: Обновленная информация о пользователе
    """
    try:
        # Защита от передачи UNIX timestamp вместо дней
        # Если значение больше чем разумное количество дней (10 лет = 3650 дней),
        # то это вероятно UNIX timestamp
        if expire_days > 10000:
            # Это UNIX timestamp, преобразуем обратно в дни
            current_time = time.time()
            expire_days = max(1, round((expire_days - current_time) / (24 * 60 * 60)))
            logger.warning(f"Warning: expire_days was UNIX timestamp, converted to {expire_days} days")

        if api == "marzban":
            async with mz.MarzbanAsync() as marz:
                buyer_nfo = await marz.set_user(
                    template=template,
                    name=f"{name}",
                    limit=limit,
                    res_strat=res_strat,
                    expire=(int(time.time() + time_to_unix(expire_days)))
                )
            return buyer_nfo

        elif api == "remnawave":
            # REMNAWAVE INTEGRATION
            db_userdata = await rq.get_full_username_info(name)

            if not db_userdata or not db_userdata.get("vless_uuid"):
                logger.warning(f"User {name} not found in database or missing UUID")
                return None

            useruid = db_userdata["vless_uuid"]
            logger.debug(f"Updating RemnaWave user - uuid from db: {useruid}")

            buyer_nfo = await rem.update_user(
                user_uuid=useruid,
                days=expire_days,
                limit_gb=limit,
                username=name,
                descr=description,
                squad_id=squad_id,
                external_squad_id=external_squad_id
            )
            return buyer_nfo
        else:
            logger.warning(f"Unknown API provider: {api}")
            return None

    except Exception as e:
        logger.error(f"Error updating user in {api}: {e}")
        return None


async def detect_user_api_provider(tg_id: int,username: str) -> str:
    """
    Определяет, в каком API провайдере зарегистрирован пользователь

    Args:
        username (str): Имя пользователя

    Returns:
        str: Имя API провайдера (marzban, remnawave) или None
    """
    # Сначала проверяем базу данных
    api_provider = await rq.get_user_api_provider(username)
    if api_provider:
        return api_provider

    # Если в БД нет информации, пытаемся определить по API
    try:
        # Проверяем Marzban
        async with mz.MarzbanAsync() as marz:
            user_info = await marz.get_user(name=username)
            if user_info and user_info != 404:
                await rq.update_user_api_info(tg_id, username, api_provider="marzban")
                return "marzban"
    except:
        pass

    try:
        # Проверяем RemnaWave — сначала по email, потом по username
        user_info = None
        email = await rq.get_user_email(tg_id)
        if email:
            user_info = await rem.get_user_from_email(email)
        if not user_info:
            user_info = await rem.get_user_from_username(username)
        if user_info:
            await rq.update_user_api_info(tg_id, username, api_provider="remnawave")
            return "remnawave"
    except:
        pass

    # По умолчанию возвращаем Marzban
    return "none"


async def startup_user_dialog(message):
    username = message.from_user.username
    user_id = message.from_user.id

    lang = await get_user_lang(user_id)

    # Определяем API провайдер и получаем данные за один проход
    api_provider, user_info = await resolve_user(user_id, username)
    logger.debug("handler_type:%s, api_provider: %s", type(message).__name__, api_provider)

    if type(message).__name__ != "Message":
        message_func = message.message.edit_text
    else:
        message_func = message.answer

    if user_info == 404:
        logger.debug("User not found - starting main menu for newby")
        await main_menu(message_func, menu_type="new", user_id=user_id)
    else:
        logger.debug("User has been found - decide whats next")
        status = user_info.get("status")
        data_limit = user_info.get("data_limit")
        expire = user_info.get("expire")
        is_pro = status == "active" and data_limit is None

        # Если пользователь на Marzban, показываем специальное меню с опцией миграции
        if api_provider == "marzban":
            if is_pro:
                logger.debug("User has an active Pro subscription on Marzban")
                text = lang.marzban_user_with_upgrade_option + lang.start_agreement
                await message_func(text, reply_markup=get_main_marzban_pro_localized(lang), parse_mode="HTML")
            else:
                logger.debug("User has an active Free subscription on Marzban")
                text = lang.marzban_user_with_upgrade_option + lang.start_free + lang.start_agreement
                await message_func(text, reply_markup=get_main_marzban_free_localized(lang), parse_mode="HTML")
        else:
            # Получаем оставшиеся дни для отображения в меню
            expire_days = await get_user_days(user_info)
            raw_data_limit = user_info.get("data_limit")

            # Для RemnaWave пользователей используем стандартное меню
            if is_pro:
                logger.debug("User has an active Pro subscription on RemnaWave")
                await main_menu(message_func, menu_type="pro", user_id=user_id,
                                days=expire_days, data_limit=raw_data_limit, link=user_info.get("subscription_url"))
            else:
                if status == "active":
                    logger.debug("User has an active Free subscription on RemnaWave")
                    await main_menu(message_func, menu_type="free", user_id=user_id,
                                    days=expire_days, data_limit=raw_data_limit, link=user_info.get("subscription_url"))
                else:
                    logger.debug("User has no active subscription on RemnaWave")
                    await main_menu(message_func, menu_type="new", user_id=user_id)


async def success_payment_handler(message: Message, callback: Message, tariff_days: int):
    """
    Unified handler for successful payment from any payment method (Stars, Crypto, etc.)
    Uses the subscription service for consistent message formatting and logic.
    """
    await deliver_subscription(
        message=message,
        username=callback.from_user.username,
        user_id=callback.from_user.id,
        days=tariff_days,
        subscription_type=SubscriptionType.PAID,
        payment_method="TG_STARS",
        data_limit_gb=None,  # Unlimited for paid subscription
        reset_strategy="no_reset",
    )


async def free_sub_handler(callback: CallbackQuery, free_days: int, free_limit: int, override: bool = False):
    """
    Unified handler for free subscription delivery.
    Uses the subscription service for consistent message formatting and logic.

    Args:
        callback: Callback query object
        free_days: Number of days for free subscription
        free_limit: Data limit in GB for free subscription
        override: Force override existing subscription
    """
    await deliver_subscription(
        message=callback,
        username=callback.from_user.username,
        user_id=callback.from_user.id,
        days=free_days,
        subscription_type=SubscriptionType.FREE,
        payment_method="FREE",
        data_limit_gb=free_limit,
        reset_strategy="month",
    )


async def subscription_info(callback: CallbackQuery):
    username = callback.from_user.username
    usrid = callback.from_user.id
    lang = await get_user_lang(usrid)
    # Определяем API провайдер пользователя
    api_provider = await detect_user_api_provider(usrid, username)

    user_info = await get_user_info(username, api=api_provider)
    logger.debug("subscription_info for: %s", username)
    logger.debug("user_info: %s", user_info)
    sub_link = user_info["subscription_url"]
    status = user_info["status"]
    limit = user_info.get("data_limit")
    if user_info["expire"] is None:
        expire_day = "Unlimited"
    else:
        expire_day = await get_user_days(user_info)
    if status == "active" and limit is None:
        await callback.message.edit_text(
            lang.msg_pro_active.format(link=sub_link, days=expire_day),
            reply_markup=get_connect_localized(lang, sub_link))
    else:
        await callback.message.edit_text(
            lang.msg_free_active.format(link=sub_link, days=expire_day),
            reply_markup=get_connect_localized(lang, sub_link))


async def check_tg_subscription(bot: Bot, chat_id: int, user_id: int) -> bool:
    """
    Проверяет, подписан ли пользователь на канал.

    Args:
        bot: Экземпляр объекта Bot.
        chat_id: ID чата (канала), на который нужно проверить подписку.
        user_id: ID пользователя.

    Returns:
        True, если пользователь подписан, иначе False.
    """
    try:
        member = await bot.get_chat_member(chat_id=int(chat_id), user_id=user_id)
        # Статус 'member' означает, что пользователь подписан на канал.
        # Статус 'restricted' или 'left' означает, что пользователь не подписан.
        return (member.status == ChatMemberStatus.MEMBER
                or member.status == ChatMemberStatus.CREATOR
                or member.status == ChatMemberStatus.ADMINISTRATOR)
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки: {e}")
        return False