"""
Unified subscription delivery service for both paid and free subscriptions.
Handles all subscription activation scenarios with localized messages.
"""

import logging
from enum import Enum
from typing import Optional, Union

from aiogram.types import Message, CallbackQuery

import app.keyboards as kb
# import app.marzban.templates as templates  # DISABLED: Marzban removed
from app.locale.lang_ru import admin_transaction_message, admin_migration_message
from app.locale.utils import get_user_lang
from app.settings import bot, admin_bot, secrets

_notify = admin_bot or bot


class SubscriptionType(Enum):
    """Enum для типов подписок"""
    FREE = "free"
    PAID = "paid"


class SubscriptionScenario(Enum):
    """Enum для сценариев выдачи подписки"""
    NEW_USER = "new_user"
    EXTEND = "extend"
    UPDATE = "update"
    ALREADY_ACTIVE = "already_active"
    MIGRATION = "migration"
    LIMITED = "limited"


def _parse_squad_slug(slug: str) -> Optional[dict]:
    """Parse "sid:<squad_id>:esid:<external_squad_id>" produced by the
    WebApp Tariff Constructor. Returns None if the slug is not in this format.
    """
    if not slug or not slug.startswith("sid:"):
        return None
    try:
        _, sid, marker, esid = slug.split(":", 3)
    except ValueError:
        return None
    if marker != "esid" or not sid or not esid:
        return None
    return {"squad_id": sid, "external_squad_id": esid}


async def get_subscription_scenario(
    user_id: int,
    user_info: dict,
    username: str,
    subscription_type: SubscriptionType,
    current_days: Optional[int] = None,
) -> SubscriptionScenario:
    """Определяет сценарий выдачи подписки"""
    if user_info == 404:
        return SubscriptionScenario.NEW_USER


    status = user_info.get("status")
    limit = user_info.get("data_limit")
    # PRO = активная подписка без лимита трафика (платная)
    # FREE = есть лимит трафика (data_limit не None и >= 0)
    is_paid_subscription = status == "active" and limit is None

    if subscription_type == SubscriptionType.FREE:
        if status == "limited":
            return SubscriptionScenario.LIMITED
        if user_info.get("expire") == 0 or status != "active":
            return SubscriptionScenario.UPDATE
        else:
            return SubscriptionScenario.ALREADY_ACTIVE
    else:
        # При покупке платной подписки:
        # - если текущая подписка платная (PRO) → складываем дни (EXTEND)
        # - если текущая подписка бесплатная (FREE) → заменяем, не складывая дни (UPDATE)
        if is_paid_subscription:
            return SubscriptionScenario.EXTEND
        else:
            return SubscriptionScenario.UPDATE


async def deliver_subscription(
    message: Union[Message, CallbackQuery, None],
    username: str,
    user_id: int,
    days: int,
    subscription_type: SubscriptionType = SubscriptionType.PAID,
    payment_method: str = "TG_STARS",
    data_limit_gb: Optional[int] = None,
    reset_strategy: str = "no_reset",
    transaction_id: Optional[str] = None,
    amount: Optional[float] = None,
    tariff_slug: Optional[str] = None,
) -> dict:
    """
    Unified function to deliver subscription to user.
    Handles both paid and free subscriptions with proper message templates.

    Args:
        message: Message, CallbackQuery object, or None for background tasks
        username: Telegram username
        user_id: Telegram user ID
        days: Number of days for subscription
        subscription_type: Type of subscription (FREE or PAID)
        payment_method: Payment method for admin notification
        data_limit_gb: Data limit in GB (None for unlimited)
        reset_strategy: Traffic reset strategy

    Returns:
        dict: Result of subscription delivery with status and details
    """
    try:
        # Lazy import to avoid circular dependency
        from app.handlers.tools import get_user_info, detect_user_api_provider, get_user_days, add_new_user_info
        import app.database.requests as rq

        # Get user's language for localized messages
        lang = await get_user_lang(user_id)

        # DISABLED: Marzban auto-migration removed — Remnawave is the only API
        # api_provider = await detect_user_api_provider(user_id, username)
        # if api_provider == "marzban":
        #     marzban_info = await get_user_info(username, api="marzban")
        #     if marzban_info != 404:
        #         expire_days = await get_user_days(marzban_info)
        #         marzban_data_limit = marzban_info.get("data_limit", 0)
        #         is_pro = marzban_info.get("status") == "active" and marzban_data_limit is None
        #         migration_squad_id = secrets.get("rw_pro_id") if is_pro else secrets.get("rw_free_id")
        #         external_squad_migration_id = secrets.get("rw_ext_pro_id") if is_pro else secrets.get("rw_ext_free_id")
        #         migration_limit = 0 if (marzban_data_limit == 0 or marzban_data_limit is None) else marzban_data_limit // (1024 * 1024 * 1024)
        #         new_user_info = await add_new_user_info(
        #             name=username, userid=user_id, limit=migration_limit,
        #             expire_days=expire_days, api="remnawave",
        #             email=f"{username}@marzban.ru",
        #             description=f"Auto-migrated from Marzban ({'Pro' if is_pro else 'Free'})",
        #             squad_id=migration_squad_id, external_squad_id=external_squad_migration_id
        #         )
        #         if new_user_info:
        #             logging.info(f"Auto-migrated {username} from Marzban to RemnaWave")
        #         else:
        #             logging.error(f"Auto-migration failed for {username}")

        # Стандартная логика — RemnaWave is the only API
        user_info = await get_user_info(username)

        scenario = await get_subscription_scenario(
            user_id, user_info, username, subscription_type, days
        )

        data_limit = data_limit_gb if data_limit_gb else 0

        await log_transaction_to_admin(
            username=username,
            user_id=user_id,
            days=days,
            payment_method=payment_method,
            transaction_id=transaction_id,
            amount=amount,
        )

        # Resolve squad from tariff (for PAID subscriptions).
        # Two formats are supported for `tariff_slug`:
        #  1) Existing tariff slug -> looked up via tariff_repository.
        #  2) Ad-hoc squad encoded by the WebApp tariff constructor as
        #     "sid:<squad_id>:esid:<external_squad_id>".
        tariff_squad = None
        if subscription_type == SubscriptionType.PAID and tariff_slug:
            tariff_squad = _parse_squad_slug(tariff_slug)
            if tariff_squad is None:
                from app.database.tariff_repository import get_squad_for_tariff_slug
                tariff_squad = await get_squad_for_tariff_slug(tariff_slug)

        if scenario == SubscriptionScenario.NEW_USER:
            result = await _handle_new_user(
                message, username, user_id, days, data_limit, reset_strategy, subscription_type, lang,
                tariff_squad=tariff_squad,
            )
        elif scenario == SubscriptionScenario.EXTEND:
            result = await _handle_extend_subscription(
                message, username, user_id, days, subscription_type, lang, user_info=user_info,
                tariff_squad=tariff_squad,
            )
        elif scenario == SubscriptionScenario.UPDATE:
            result = await _handle_update_subscription(
                message, username, user_id, days, data_limit, reset_strategy, subscription_type, lang,
                tariff_squad=tariff_squad,
            )
        elif scenario == SubscriptionScenario.LIMITED:
            result = await _handle_limited(message, username, subscription_type, lang, user_info=user_info)
        elif scenario == SubscriptionScenario.ALREADY_ACTIVE:
            result = await _handle_already_active(message, username, subscription_type, lang, user_info=user_info)

        # Referral reward: check if buyer used a promo code
        if subscription_type == SubscriptionType.PAID:
            try:
                buyer_promo = await rq.get_promo_by_tg_id(user_id)
                if buyer_promo and buyer_promo['used_promo']:
                    referral_data = await rq.add_referral_days(buyer_promo['used_promo'], days)
                    if referral_data:
                        promo_days_reward = secrets.get('promo_days_reward', 3)
                        total_purchased = referral_data['days_purchased']
                        already_rewarded = referral_data['days_rewarded']
                        reward_days = (total_purchased // 30) * promo_days_reward - already_rewarded

                        if reward_days > 0:
                            owner_tg_id = referral_data['tg_id']
                            # Get owner username to extend subscription
                            owner_info = await rq.get_user_full_info_by_tg_id(owner_tg_id)
                            if owner_info and owner_info.get('username'):
                                from app.handlers.tools import get_user_info, set_user_info, get_user_days
                                owner_user_info = await get_user_info(owner_info['username'])
                                if owner_user_info != 404:
                                    owner_status = owner_user_info.get("status")
                                    owner_limit = owner_user_info.get("data_limit")
                                    is_owner_pro = owner_status == "active" and owner_limit is None

                                    if is_owner_pro:
                                        # PRO — просто добавляем дни
                                        owner_days = await get_user_days(owner_user_info)
                                        new_days = (owner_days if isinstance(owner_days, int) else 0) + reward_days
                                        await set_user_info(
                                            name=owner_info['username'],
                                            limit=0,
                                            res_strat="no_reset",
                                            expire_days=new_days,
                                            # template=templates.vless_france,  # DISABLED: Marzban templates removed
                                            api="remnawave"
                                        )
                                    else:
                                        # FREE — апгрейд до PRO на reward_days дней (без лимита трафика)
                                        await set_user_info(
                                            name=owner_info['username'],
                                            limit=0,
                                            res_strat="no_reset",
                                            expire_days=reward_days,
                                            # template=templates.vless_france,  # DISABLED: Marzban templates removed
                                            api="remnawave",
                                            squad_id=secrets.get("rw_pro_id")
                                        )

                            await rq.update_promo_days_rewarded(owner_tg_id, already_rewarded + reward_days)

                            # Notify promo owner (in their language)
                            try:
                                owner_lang = await get_user_lang(owner_tg_id)
                                await bot.send_message(
                                    chat_id=owner_tg_id,
                                    text=owner_lang.promo_reward_notification.format(
                                        reward_days=reward_days,
                                        total_days=total_purchased,
                                        total_rewarded=already_rewarded + reward_days
                                    ),
                                    parse_mode='HTML'
                                )
                            except Exception as notify_err:
                                logging.warning(f"Failed to notify promo owner {owner_tg_id}: {notify_err}")
            except Exception as promo_err:
                logging.error(f"Error processing referral reward: {promo_err}")

            # Mark the buyer's activated promo as consumed so the discount only
            # applies once. Referral chain above already used `used_promo`, so
            # we keep that field and only flip the consumed flag.
            try:
                if buyer_promo and buyer_promo.get('used_promo') and not buyer_promo.get('used_promo_consumed'):
                    await rq.mark_promo_consumed(user_id)
            except Exception as consume_err:
                logging.warning(f"Failed to mark promo consumed: {consume_err}")

        # Обновляем delivery_status после успешной доставки
        if transaction_id:
            await rq.update_delivery_status(transaction_id, 1)

        return {"status": "success", "scenario": scenario.value, **result}

    except Exception as e:
        logging.error(f"Error delivering subscription: {e}")
        return {"status": "error", "message": str(e)}


async def _handle_new_user(
    message: Union[Message, CallbackQuery, None],
    username: str,
    user_id: int,
    days: int,
    data_limit: int,
    reset_strategy: str,
    subscription_type: SubscriptionType,
    lang=None,
    tariff_squad: Optional[dict] = None,
) -> dict:
    """Handle new user subscription creation"""
    # Lazy import to avoid circular dependency
    from app.handlers.tools import add_new_user_info, get_user_days
    if subscription_type == SubscriptionType.FREE:
        squad_id = secrets.get("rw_free_id")
        external_squad_id = secrets.get("rw_ext_free_id")
    else:
        squad_id = tariff_squad["squad_id"] if tariff_squad else secrets.get("rw_pro_id")
        external_squad_id = tariff_squad["external_squad_id"] if tariff_squad else secrets.get("rw_ext_pro_id")
    print("Days:", days)
    print("Data Limit (GB):", data_limit)
    buyer_info = await add_new_user_info(
        name=username,
        userid=user_id,
        limit=data_limit,
        #res_strat=reset_strategy,
        expire_days=days,
        # template=templates.vless_france,  # DISABLED: Marzban templates removed
        email=f"{username}@marzban.ru",
        description="Telegram subscription",
        squad_id=squad_id,
        external_squad_id=external_squad_id,
        api="remnawave"
    )

    expire_day = await get_user_days(buyer_info)
    sub_link = buyer_info["subscription_url"]

    if lang is None:
        lang = await get_user_lang(user_id)
    template_key = "new_paid" if subscription_type == SubscriptionType.PAID else "new_free"
    response_text = lang.subscription_response_templates[template_key].format(
        days=expire_day, link=sub_link
    )

    await _send_response(message, response_text, sub_link, user_id, lang)

    return {"days": expire_day, "link": sub_link}


async def _handle_extend_subscription(
    message: Union[Message, CallbackQuery, None],
    username: str,
    user_id: int,
    days: int,
    subscription_type: SubscriptionType,
    lang=None,
    user_info: dict = None,
    tariff_squad: Optional[dict] = None,
) -> dict:
    """Handle existing subscription extension"""
    # Lazy import to avoid circular dependency
    from app.handlers.tools import get_user_info, get_user_days, set_user_info
    if user_info is None:
        user_info = await get_user_info(username)
    sub_link = user_info["subscription_url"]
    expire_day = await get_user_days(user_info)
    if subscription_type == SubscriptionType.FREE:
        squad_id = secrets.get("rw_free_id")
        external_squad_id = secrets.get("rw_ext_free_id")
        new_expire_days = days
    else:
        squad_id = tariff_squad["squad_id"] if tariff_squad else secrets.get("rw_pro_id")
        external_squad_id = tariff_squad["external_squad_id"] if tariff_squad else secrets.get("rw_ext_pro_id")
        new_expire_days = expire_day + days if isinstance(expire_day, int) else days

    buyer_info = await set_user_info(
        name=username,
        limit=0,
        res_strat="no_reset",
        expire_days=new_expire_days,
        # template=templates.vless_france,  # DISABLED: Marzban templates removed
        api="remnawave",
        squad_id=squad_id,
        external_squad_id=external_squad_id
    )

    final_expire_day = await get_user_days(buyer_info)

    if lang is None:
        lang = await get_user_lang(user_id)
    template_key = (
        "extended_paid" if subscription_type == SubscriptionType.PAID else "updated_free"
    )
    response_text = lang.subscription_response_templates[template_key].format(
        days=final_expire_day, link=sub_link
    )

    await _send_response(message, response_text, sub_link, user_id, lang)

    return {"days": final_expire_day, "link": sub_link}


async def _handle_update_subscription(
    message: Union[Message, CallbackQuery, None],
    username: str,
    user_id: int,
    days: int,
    data_limit: int,
    reset_strategy: str,
    subscription_type: SubscriptionType,
    lang=None,
    tariff_squad: Optional[dict] = None,
) -> dict:
    """Handle subscription update (replacement)"""
    # Lazy import to avoid circular dependency
    from app.handlers.tools import set_user_info, get_user_days, get_user_info
    from app.api.remnawave.api import reset_user_traffic
    import app.database.requests as rq_update

    # При переходе с FREE на PAID — ставим PRO squad, при FREE — FREE squad
    if subscription_type == SubscriptionType.PAID:
        squad_id = tariff_squad["squad_id"] if tariff_squad else secrets.get("rw_pro_id")
        external_squad_id = tariff_squad["external_squad_id"] if tariff_squad else secrets.get("rw_ext_pro_id")
    else:
        squad_id = secrets.get("rw_free_id")
        external_squad_id = secrets.get("rw_ext_free_id")
    # Сброс трафика при выдаче FREE подписки (чтобы limited пользователь мог снова пользоваться)
    if subscription_type == SubscriptionType.FREE and data_limit > 0:
        try:
            db_user = await rq_update.get_full_username_info(username)
            if db_user and db_user.get("vless_uuid"):
                await reset_user_traffic(db_user["vless_uuid"])
                logging.info(f"Reset traffic for {username} before FREE subscription update")
        except Exception as e:
            logging.warning(f"Failed to reset traffic for {username}: {e}")

    buyer_info = await set_user_info(
        name=username,
        limit=data_limit,
        res_strat=reset_strategy,
        expire_days=days,
        # template=templates.vless_france,  # DISABLED: Marzban templates removed
        api="remnawave",
        squad_id=squad_id,
        external_squad_id=external_squad_id
    )

    expire_day = await get_user_days(buyer_info)
    sub_link = buyer_info["subscription_url"]

    if lang is None:
        lang = await get_user_lang(user_id)
    template_key = (
        "updated_paid" if subscription_type == SubscriptionType.PAID else "updated_free"
    )
    response_text = lang.subscription_response_templates[template_key].format(
        days=expire_day, link=sub_link
    )

    await _send_response(message, response_text, sub_link, user_id, lang)

    return {"days": expire_day, "link": sub_link}


async def _handle_limited(
    message: Union[Message, CallbackQuery, None],
    username: str,
    subscription_type: SubscriptionType,
    lang=None,
    user_info: dict = None,
) -> dict:
    """Handle case when free subscription traffic is exhausted (LIMITED status)"""
    from app.handlers.tools import get_user_info, get_user_days
    from app.keyboards.localized import get_limited_menu_localized

    if user_info is None:
        user_info = await get_user_info(username)
    expire_day = await get_user_days(user_info)

    if lang is None:
        from app.locale import lang_ru
        lang = lang_ru
    response_text = lang.free_traffic_exhausted.format(days=expire_day)

    keyboard = get_limited_menu_localized(lang)

    if isinstance(message, Message):
        await message.answer(text=response_text, parse_mode="HTML", reply_markup=keyboard)
    elif isinstance(message, CallbackQuery):
        await message.message.edit_text(text=response_text, parse_mode="HTML", reply_markup=keyboard)
    elif message is None:
        user_id = None
        logging.warning(f"Cannot send limited message: message={message}")

    return {"days": expire_day, "limited": True}


async def _handle_already_active(
    message: Union[Message, CallbackQuery, None], username: str, subscription_type: SubscriptionType,
    lang=None, user_info: dict = None,
) -> dict:
    """Handle case when free subscription is already active"""
    # Lazy import to avoid circular dependency
    from app.handlers.tools import get_user_info, get_user_days

    if user_info is None:
        user_info = await get_user_info(username)
    sub_link = user_info["subscription_url"]
    expire_day = await get_user_days(user_info)

    user_id = None
    if isinstance(message, Message):
        user_id = message.from_user.id
    elif isinstance(message, CallbackQuery):
        user_id = message.from_user.id

    if lang is None:
        if user_id:
            lang = await get_user_lang(user_id)
        else:
            from app.locale import lang_ru
            lang = lang_ru

    response_text = lang.subscription_response_templates["already_active_free"].format(
        days=expire_day, link=sub_link
    )

    await _send_response(message, response_text, sub_link, user_id, lang)

    return {"days": expire_day, "link": sub_link, "already_active": True}


async def _send_response(
    message: Union[Message, CallbackQuery, None], text: str, sub_link: str, user_id: Optional[int] = None, lang=None
) -> None:
    """Send response message to user with subscription details"""
    from app.keyboards.localized import get_connect_localized
    if lang is None:
        from app.locale import lang_ru
        lang = lang_ru
    keyboard = get_connect_localized(lang, sub_link)

    if isinstance(message, Message):
        # Прямой ответ на сообщение пользователя
        await message.answer(text=text, parse_mode="HTML", reply_markup=keyboard)
    elif isinstance(message, CallbackQuery):
        # Редактирование сообщения из callback query
        await message.message.edit_text(text=text, parse_mode="HTML", reply_markup=keyboard)
    elif message is None and user_id is not None:
        # Отправка сообщения напрямую при background task (например, от вебхука)
        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        # Если нет способа отправить сообщение, логируем ошибку
        logging.warning(f"Cannot send subscription message: message={message}, user_id={user_id}")


async def log_transaction_to_admin(
    username: str, user_id: int, days: int, payment_method: str = "TG_STARS",
    transaction_id: str = None, amount: float = None,
) -> None:
    """Log transaction details to admin"""
    admin_message = admin_transaction_message.format(
        transaction_id=transaction_id or "—",
        payment_method=payment_method,
        amount=amount if amount is not None else "—",
        username=username,
        user_id=user_id,
        days=days,
    )

    await _notify.send_message(chat_id=secrets.get("admin_id"), text=admin_message)
