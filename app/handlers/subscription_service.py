"""
Unified subscription delivery service for both paid and free subscriptions.
Handles all subscription activation scenarios with localized messages.
"""

import logging
from enum import Enum
from typing import Optional, Union

from aiogram.types import Message, CallbackQuery

import app.keyboards as kb
import app.marzban.templates as templates
from app.locale.lang_ru import subscription_response_templates, admin_transaction_message
from app.settings import bot, secrets


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


async def get_subscription_scenario(
    user_info: dict,
    subscription_type: SubscriptionType,
    current_days: Optional[int] = None,
) -> SubscriptionScenario:
    """Определяет сценарий выдачи подписки"""
    if user_info == 404:
        return SubscriptionScenario.NEW_USER

    status = user_info.get("status")
    limit = user_info.get("data_limit")
    is_pro = status == "active" and limit is None

    if subscription_type == SubscriptionType.FREE:
        if user_info.get("expire") == 0 or status != "active":
            return SubscriptionScenario.UPDATE
        else:
            return SubscriptionScenario.ALREADY_ACTIVE
    else:
        if is_pro:
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
        from app.handlers.tools import get_user_info

        user_info = await get_user_info(username)

        scenario = await get_subscription_scenario(
            user_info, subscription_type, days
        )

        data_limit = data_limit_gb * 1024 * 1024 * 1024 if data_limit_gb else 0

        await log_transaction_to_admin(
            username=username,
            user_id=user_id,
            days=days,
            payment_method=payment_method,
        )

        if scenario == SubscriptionScenario.NEW_USER:
            result = await _handle_new_user(
                message, username, user_id, days, data_limit, reset_strategy, subscription_type
            )
        elif scenario == SubscriptionScenario.EXTEND:
            result = await _handle_extend_subscription(
                message, username, user_id, days, subscription_type
            )
        elif scenario == SubscriptionScenario.UPDATE:
            result = await _handle_update_subscription(
                message, username, user_id, days, data_limit, reset_strategy, subscription_type
            )
        elif scenario == SubscriptionScenario.ALREADY_ACTIVE:
            result = await _handle_already_active(message, username, subscription_type)

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
) -> dict:
    """Handle new user subscription creation"""
    # Lazy import to avoid circular dependency
    from app.handlers.tools import add_new_user_info, get_user_days

    buyer_info = await add_new_user_info(
        name=username,
        userid=user_id,
        limit=data_limit,
        res_strat=reset_strategy,
        expire_days=days,
        template=templates.vless_france,
    )

    expire_day = await get_user_days(buyer_info)
    sub_link = buyer_info["subscription_url"]

    template_key = "new_paid" if subscription_type == SubscriptionType.PAID else "new_free"
    response_text = subscription_response_templates[template_key].format(
        days=expire_day, link=sub_link
    )

    await _send_response(message, response_text, sub_link, user_id)

    return {"days": expire_day, "link": sub_link}


async def _handle_extend_subscription(
    message: Union[Message, CallbackQuery, None],
    username: str,
    user_id: int,
    days: int,
    subscription_type: SubscriptionType,
) -> dict:
    """Handle existing subscription extension"""
    # Lazy import to avoid circular dependency
    from app.handlers.tools import get_user_info, get_user_days, set_user_info

    user_info = await get_user_info(username)
    sub_link = user_info["subscription_url"]
    expire_day = await get_user_days(user_info)

    new_expire_days = expire_day + days if isinstance(expire_day, int) else days

    buyer_info = await set_user_info(
        name=username,
        limit=0,
        res_strat="no_reset",
        expire_days=new_expire_days,
        template=templates.vless_france,
    )

    final_expire_day = await get_user_days(buyer_info)

    template_key = (
        "extended_paid" if subscription_type == SubscriptionType.PAID else "updated_free"
    )
    response_text = subscription_response_templates[template_key].format(
        days=final_expire_day, link=sub_link
    )

    await _send_response(message, response_text, sub_link, user_id)

    return {"days": final_expire_day, "link": sub_link}


async def _handle_update_subscription(
    message: Union[Message, CallbackQuery, None],
    username: str,
    user_id: int,
    days: int,
    data_limit: int,
    reset_strategy: str,
    subscription_type: SubscriptionType,
) -> dict:
    """Handle subscription update (replacement)"""
    # Lazy import to avoid circular dependency
    from app.handlers.tools import set_user_info, get_user_days

    buyer_info = await set_user_info(
        name=username,
        limit=data_limit,
        res_strat=reset_strategy,
        expire_days=days,
        template=templates.vless_france,
    )

    expire_day = await get_user_days(buyer_info)
    sub_link = buyer_info["subscription_url"]

    template_key = (
        "updated_paid" if subscription_type == SubscriptionType.PAID else "updated_free"
    )
    response_text = subscription_response_templates[template_key].format(
        days=expire_day, link=sub_link
    )

    await _send_response(message, response_text, sub_link, user_id)

    return {"days": expire_day, "link": sub_link}


async def _handle_already_active(
    message: Union[Message, CallbackQuery, None], username: str, subscription_type: SubscriptionType
) -> dict:
    """Handle case when free subscription is already active"""
    # Lazy import to avoid circular dependency
    from app.handlers.tools import get_user_info, get_user_days

    user_info = await get_user_info(username)
    sub_link = user_info["subscription_url"]
    expire_day = await get_user_days(user_info)

    response_text = subscription_response_templates["already_active_free"].format(
        days=expire_day, link=sub_link
    )

    # Get user_id from message or use a placeholder for background tasks
    user_id = None
    if isinstance(message, Message):
        user_id = message.from_user.id
    elif isinstance(message, CallbackQuery):
        user_id = message.from_user.id

    await _send_response(message, response_text, sub_link, user_id)

    return {"days": expire_day, "link": sub_link, "already_active": True}


async def _send_response(
    message: Union[Message, CallbackQuery, None], text: str, sub_link: str, user_id: Optional[int] = None
) -> None:
    """Send response message to user with subscription details"""
    keyboard = kb.connect(sub_link)

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
    username: str, user_id: int, days: int, payment_method: str = "TG_STARS"
) -> None:
    """Log transaction details to admin"""
    admin_message = admin_transaction_message.format(
        payment_method=payment_method, username=username, user_id=user_id, days=days
    )

    await bot.send_message(chat_id=secrets.get("admin_id"), text=admin_message)
