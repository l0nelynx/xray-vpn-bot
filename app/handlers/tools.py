import time

import app.api.remnawave.api as rem
import app.marzban.marzban as mz
import app.database.requests as rq

from aiogram.types import Message, CallbackQuery

from app.settings import bot, secrets
import app.keyboards as kb

import app.locale.lang_ru as ru
import app.marzban.templates as templates
from app.handlers.events import main_menu
from app.handlers.subscription_service import deliver_subscription, SubscriptionType
from aiogram import Bot
from aiogram.enums.chat_member_status import ChatMemberStatus


def time_to_unix(days: int):
    return int(days * 24 * 60 * 60)


async def get_user_days(user_nfo):
    return round((user_nfo["expire"] - time.time()) / (24 * 60 * 60))


async def get_user_info(username, api: str = "marzban"):
    if api == "marzban":
        async with mz.MarzbanAsync() as marz:
            user_info = await marz.get_user(name=username)
        return user_info
    else:
        # REMNAWAVE INTEGRATION
        user_info = await rem.get_user_from_username(username)
        return user_info


async def add_new_user_info(name, userid, limit, res_strat, expire_days: int, template: dict = templates.vless_template, api: str = "marzban"):
    if api == "marzban":
        async with mz.MarzbanAsync() as marz:
            buyer_nfo = await marz.add_user(
                template=template,
                name=f"{name}",
                usrid=f"{userid}",
                limit=limit,
                res_strat=res_strat,  # no_reset day week month year
                expire=(int(time.time() + time_to_unix(expire_days)))
            )
        return buyer_nfo
    else:
        # REMNAWAVE INTEGRATION
        buyer_nfo = await rem.create_user(
            username= name,
            days= expire_days,
            limit_gb= limit,
            descr='created by backend v2'
        )
        db_upd_status = await rq.update_user_vless_uuid(name, buyer_nfo["uuid"])
        print('db is updated: ', db_upd_status)
        return buyer_nfo


async def set_user_info(name, limit, res_strat, expire_days: int, template: dict = templates.vless_template, api: str = "marzban"):
    if api == "marzban":
        async with mz.MarzbanAsync() as marz:
            buyer_nfo = await marz.set_user(
                template=template,
                name=f"{name}",
                limit=limit,
                res_strat=res_strat,  # no_reset day week month year
                expire=(int(time.time() + time_to_unix(expire_days)))
            )
        return buyer_nfo
    else:
        # REMNAWAVE INTEGRATION
        db_userdata = await rq.get_full_username_info(name)
        useruid = db_userdata["vless_uuid"]
        print("reading from db - uuid by username is:")
        print(useruid)
        buyer_nfo = await rem.update_user(
            user_uuid= useruid,
            days= expire_days,
            limit_gb= limit,
            username= name,
            descr='updated by backend v2'
        )
        return buyer_nfo


async def startup_user_dialog(message):
    user_info = await get_user_info(message.from_user.username)
    print(f"handler_type:{type(message).__name__}")
    if type(message).__name__ != "Message":
        message = message.message.edit_text
    else:
        message = message.answer
    if user_info == 404:
        print("User not found - starting main menu for newby")
        await main_menu(message, menu_type="new")
    else:
        print("User has been found - decide whats next")
        if user_info["status"] == "active" and user_info["data_limit"] is None:
            print("User has an active Pro subscription")
            await main_menu(message, menu_type="pro")
        else:
            if user_info["status"] == "active":
                print("User has an active Free subscription")
                await main_menu(message, menu_type="free")
            else:
                print("User has no active subscription")
                await main_menu(message, menu_type="new")


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
    user_info = await get_user_info(callback.from_user.username)
    print(callback.from_user.username)
    print(user_info)
    sub_link = user_info["subscription_url"]
    status = user_info["status"]
    limit = user_info["data_limit"]
    if user_info["expire"] is None:
        expire_day = "Unlimited"
    else:
        expire_day = await get_user_days(user_info)
    if status == "active" and limit is None:
        await callback.message.edit_text(f"Pro подписка активна\n"
                                         f"Ссылка для подключения: {sub_link}\n"
                                         f"Осталось дней: {expire_day}\n", reply_markup=kb.connect(sub_link))
    else:
        await callback.message.edit_text("Free подписка активна\n"
                                         f"Ссылка для подключения: {sub_link}\n"
                                         f"Осталось дней: {expire_day}\n", reply_markup=kb.connect(sub_link))


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
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        # Статус 'member' означает, что пользователь подписан на канал.
        # Статус 'restricted' или 'left' означает, что пользователь не подписан.
        return (member.status == ChatMemberStatus.MEMBER
                or member.status == ChatMemberStatus.CREATOR
                or member.status == ChatMemberStatus.ADMINISTRATOR)
    except Exception as e:
        print(f"Ошибка при проверке подписки: {e}")
        return False
