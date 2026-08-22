from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import logging
import app.database.requests as rq
import app.keyboards as kb
from app.keyboards.localized import (
    get_language_select_keyboard, get_others_localized, get_subcheck_free_localized,
    get_agreement_menu_localized, get_policy_menu_localized, get_to_main_localized,
    # get_migration_confirm_localized, get_connect_localized,  # DISABLED: Marzban migration removed
    get_connect_localized,
    get_settings_menu_localized, get_language_change_keyboard,
    get_subcheck_telemt_localized,
)
from app.locale.utils import get_user_lang
from app.handlers.events import userlist
from app.handlers.tools import startup_user_dialog, free_sub_handler, subscription_info, check_tg_subscription, \
    get_user_days

from app.settings import secrets, bot, admin_bot
from common_db.repo import promos as rq_promos
import string
import random

router = Router()


_ANDROID_LINK_MESSAGES = {
    "ok": {
        "ru": "✅ Ваш аккаунт Android-приложения связан с этим Telegram.",
        "en": "✅ Your Android-app account is now linked to this Telegram.",
    },
    "invalid": {
        "ru": "❌ Код связывания недействителен. Откройте приложение и попробуйте снова.",
        "en": "❌ Invalid link code. Open the app and try again.",
    },
    "expired": {
        "ru": "⌛ Срок действия кода истёк. Запросите новый в приложении.",
        "en": "⌛ Link code expired. Request a new one from the app.",
    },
    "exhausted": {
        "ru": "🚫 Слишком много попыток. Запросите новый код в приложении.",
        "en": "🚫 Too many attempts. Request a new code from the app.",
    },
    "user_already_linked": {
        "ru": "⚠️ Этот аккаунт приложения уже связан с Telegram.",
        "en": "⚠️ This app account is already linked to a Telegram.",
    },
    "merged_pro": {
        "ru": "✅ Аккаунты объединены. Сохранена PRO-подписка.",
        "en": "✅ Accounts merged. PRO subscription preserved.",
    },
    "merged_free": {
        "ru": "✅ Аккаунты объединены.",
        "en": "✅ Accounts merged.",
    },
    "both_pro_support_needed": {
        "ru": (
            "⚠️ Обнаружены две активные PRO-подписки на разных аккаунтах. "
            "Свяжитесь с поддержкой для объединения."
        ),
        "en": (
            "⚠️ Two active PRO subscriptions found on different accounts. "
            "Contact support to merge."
        ),
    },
}


def _android_link_reply(result: str, lang_code: str) -> str:
    bucket = _ANDROID_LINK_MESSAGES.get(result, _ANDROID_LINK_MESSAGES["invalid"])
    return bucket.get(lang_code) or bucket["en"]


@router.message(Command("start"))  # Start command handler
async def cmd_start(message: Message, command: CommandObject = None):
    if await rq.is_user_banned(message.from_user.id):
        lang = await get_user_lang(message.from_user.id)
        await message.answer(lang.msg_account_banned, disable_web_page_preview=True)
        return
    await rq.set_user(message.from_user.id, message.from_user.username)

    # Check if user has already chosen a language
    user_language = await rq.get_user_language(message.from_user.id)
    if user_language is None:
        # First time — show language selection
        from app.locale import lang_ru
        await message.answer(
            text=lang_ru.lang_choose,
            parse_mode='HTML',
            disable_web_page_preview=True,
            reply_markup=get_language_select_keyboard()
        )
        return

    # Deep-link payloads from MiniApp (?start=buy|extend|trial) and
    # Android link flow (?start=link_<code>). Keep `link_<code>` as the
    # original-case payload — base64url codes are case-sensitive.
    raw_payload = (command.args or "").strip() if command else ""
    if raw_payload.startswith("link_"):
        from app.handlers.android_link import consume_android_link_code
        code = raw_payload[5:].strip()
        result = await consume_android_link_code(message.from_user.id, code)
        lang_code = (await rq.get_user_language(message.from_user.id)) or "en"
        await message.answer(
            _android_link_reply(result, lang_code),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return

    # Giveaway deeplink: t.me/<bot>?start=gw_<id>
    if raw_payload.lower().startswith("gw_"):
        try:
            giveaway_id = int(raw_payload[3:])
        except ValueError:
            giveaway_id = 0
        if giveaway_id > 0:
            from app.handlers.giveaways import handle_giveaway_join
            await handle_giveaway_join(message, giveaway_id)
            return

    payload = raw_payload.lower()
    if payload in ("buy", "extend", "trial"):
        lang = await get_user_lang(message.from_user.id)
        if payload == "trial":
            await message.answer(
                text=lang.free_menu, parse_mode='HTML',
                disable_web_page_preview=True,
                reply_markup=get_subcheck_free_localized(lang),
            )
            return
        # buy / extend — when bot constructor is disabled, open the MiniApp directly
        # instead of showing inline payment method buttons (those callbacks have no handler)
        from app.bot_constructor.feature import is_enabled
        if not await is_enabled():
            miniapp_url = secrets.get('miniapp_url')
            if miniapp_url:
                from aiogram.types import WebAppInfo
                text = lang.text_extend_pay_method if payload == "extend" else lang.text_pay_method
                await message.answer(
                    text=text, parse_mode='HTML',
                    disable_web_page_preview=True,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text=lang.btn_buy_premium, web_app=WebAppInfo(url=miniapp_url))],
                    ]),
                )
                return
        await message.answer(
            text=lang.text_extend_pay_method if payload == "extend" else lang.text_pay_method,
            parse_mode='HTML',
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=lang.btn_buy_premium, callback_data="tariff:root")
            ]]),
        )
        return

    # Referral/promo deeplink: t.me/<bot>?start=<CODE>. Auto-activate it; rules
    # are enforced in the repo (referral codes only for users with no
    # transactions, one active promo at a time, no re-use). A bad deeplink must
    # not block /start — on failure we fall through to the main menu, only
    # surfacing the "referral is for new users" case which is worth explaining.
    if raw_payload and raw_payload.isalnum():
        lang = await get_user_lang(message.from_user.id)
        result = await rq.redeem_promo_for_user(message.from_user.id, raw_payload.upper())
        if result.ok:
            await message.answer(
                text=lang.promo_deeplink_applied_text.format(points=result.credit_grant or 0),
                parse_mode='HTML', disable_web_page_preview=True,
            )
        elif result.reason == rq_promos.REASON_REFERRAL_NOT_NEW:
            await message.answer(
                text=lang.promo_referral_new_only_text,
                parse_mode='HTML', disable_web_page_preview=True,
            )
        await startup_user_dialog(message)
        return

    # Language already chosen — go straight to main menu
    await startup_user_dialog(message)


@router.message(Command("lang"))  # Language change command
async def cmd_lang(message: Message):
    lang = await get_user_lang(message.from_user.id)
    await message.answer(
        text=lang.msg_lang_current,
        parse_mode='HTML',
        disable_web_page_preview=True,
        reply_markup=get_language_change_keyboard(lang)
    )


@router.callback_query(F.data.in_({'set_lang_ru', 'set_lang_en'}))
async def set_language(callback: CallbackQuery):
    from app.locale.utils import invalidate_lang_cache
    lang_code = callback.data.replace('set_lang_', '')
    await rq.set_user_language(callback.from_user.id, lang_code)
    invalidate_lang_cache(callback.from_user.id)
    await callback.answer("✅")
    await startup_user_dialog(callback)


@router.callback_query(F.data == 'Agreement')
async def user_agreement(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    await callback.message.edit_text(text=lang.user_agreement, parse_mode='HTML',
                                     disable_web_page_preview=True,
                                     reply_markup=get_agreement_menu_localized(lang))


@router.callback_query(F.data == 'Privacy')
async def privacy_policy(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    await callback.message.edit_text(text=lang.privacy_policy, parse_mode='HTML',
                                     disable_web_page_preview=True,
                                     reply_markup=get_policy_menu_localized(lang))


@router.callback_query(F.data == 'Settings')
async def settings_menu(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    lang_code = await rq.get_user_language(callback.from_user.id) or "ru"
    from app.bot_constructor.keyboards.dynamic import get_dynamic_keyboard
    from app.database.tariff_repository import get_screen_text
    text = await get_screen_text("settings", lang_code) or lang.msg_settings
    keyboard = await get_dynamic_keyboard("settings", lang_code)
    await callback.message.edit_text(
        text=text,
        parse_mode='HTML',
        disable_web_page_preview=True,
        reply_markup=keyboard or get_settings_menu_localized(lang)
    )


@router.callback_query(F.data == 'Change_Language')
async def change_language_menu(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    await callback.message.edit_text(
        text=lang.msg_lang_current,
        parse_mode='HTML',
        disable_web_page_preview=True,
        reply_markup=get_language_change_keyboard(lang)
    )


@router.callback_query(F.data == 'Main')
async def others(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    await callback.answer(lang.text_answers['main_menu_greetings'])
    await startup_user_dialog(callback)


@router.message(Command("users"), F.from_user.id == secrets.get('admin_id'))
async def user_db_check(message: Message):
    await message.answer('Making a user list from db')
    await userlist()


@router.callback_query(F.data == 'Others')
async def others_menu(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    await callback.answer(lang.text_answers['instruction_greetings'])
    await callback.message.edit_text(lang.text_answers['instruction_platform_choose'], parse_mode='HTML',
                                     disable_web_page_preview=True, reply_markup=get_others_localized(lang))


@router.callback_query(F.data == 'Android_Help')
async def android_help(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    await callback.answer(lang.text_answers['instruction_android'])
    await callback.message.edit_text(text=lang.text_help, parse_mode='HTML', disable_web_page_preview=True,
                                     reply_markup=get_others_localized(lang))


@router.callback_query(F.data == 'Windows_Help')
async def windows_help(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    await callback.answer(lang.text_answers['instruction_windows'])
    await callback.message.edit_text(text=lang.text_help_windows, parse_mode='HTML', disable_web_page_preview=True,
                                     reply_markup=get_others_localized(lang))


@router.callback_query(F.data == 'Free')
async def free_version_menu(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    await callback.message.edit_text(text=lang.free_menu, parse_mode='HTML', disable_web_page_preview=True,
                                     reply_markup=get_subcheck_free_localized(lang))


@router.callback_query(F.data == 'subcheck_free')
async def free_buy(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)

    if await rq.is_user_banned(callback.from_user.id):
        await callback.message.edit_text(text=lang.msg_account_banned, parse_mode='HTML',
                                         disable_web_page_preview=True,
                                         reply_markup=get_to_main_localized(lang))
        return

    username = callback.from_user.username
    if not username or username == "None":
        await callback.message.edit_text(text=lang.msg_username_required, parse_mode='HTML',
                                         disable_web_page_preview=True,
                                         reply_markup=get_to_main_localized(lang))
        return

    sub_status = await check_tg_subscription(bot=bot, chat_id=secrets.get('news_id'), user_id=callback.from_user.id)
    if sub_status:
        await free_sub_handler(callback, secrets.get('free_days'), secrets.get('free_traffic'))
    else:
        await callback.message.edit_text(text=lang.free_menu_notsub, parse_mode='HTML', disable_web_page_preview=True,
                                         reply_markup=get_subcheck_free_localized(lang))


@router.callback_query(F.data == 'Telemt_Free')
async def telemt_free_menu(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    await callback.message.edit_text(text=lang.telemt_free_menu, parse_mode='HTML', disable_web_page_preview=True,
                                     reply_markup=get_subcheck_telemt_localized(lang))


@router.callback_query(F.data == 'subcheck_telemt')
async def telemt_free_buy(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)

    if await rq.is_user_banned(callback.from_user.id):
        await callback.message.edit_text(text=lang.msg_account_banned, parse_mode='HTML',
                                         disable_web_page_preview=True,
                                         reply_markup=get_to_main_localized(lang))
        return

    username = callback.from_user.username
    if not username or username == "None":
        await callback.message.edit_text(text=lang.msg_username_required, parse_mode='HTML',
                                         disable_web_page_preview=True,
                                         reply_markup=get_to_main_localized(lang))
        return

    sub_status = await check_tg_subscription(bot=bot, chat_id=secrets.get('news_id'), user_id=callback.from_user.id)
    if not sub_status:
        await callback.message.edit_text(text=lang.telemt_free_menu_notsub, parse_mode='HTML',
                                         disable_web_page_preview=True,
                                         reply_markup=get_subcheck_telemt_localized(lang))
        return

    from app.api.telemt import get_telemt_user, create_telemt_user, format_telemt_links

    # Check if user already exists in Telemt
    existing = await get_telemt_user(username)
    if existing:
        links_text = format_telemt_links(existing.get("links", {}))
        await callback.message.edit_text(
            text=lang.telemt_free_already_exists.format(links=links_text),
            parse_mode='HTML',
            disable_web_page_preview=True,
            reply_markup=get_to_main_localized(lang),
        )
        return

    # Read free params from DB and create user
    params = await rq.get_telemt_free_params()
    result = await create_telemt_user(
        username=username,
        expire_days=params.get("expire_days", 30),
        max_tcp_conns=params.get("max_tcp_conns"),
        max_unique_ips=params.get("max_unique_ips"),
        data_quota_bytes=params.get("data_quota_bytes"),
        rate_limit_up_bps=params.get("rate_limit_up_bps"),
        rate_limit_down_bps=params.get("rate_limit_down_bps"),
    )

    if not result:
        await callback.message.edit_text(text=lang.telemt_free_error, parse_mode='HTML',
                                         disable_web_page_preview=True,
                                         reply_markup=get_to_main_localized(lang))
        return

    links_text = format_telemt_links(result.get("links", {}))
    await callback.message.edit_text(
        text=lang.telemt_free_success.format(links=links_text),
        parse_mode='HTML',
        disable_web_page_preview=True,
        reply_markup=get_to_main_localized(lang),
    )


@router.callback_query(F.data == 'Sub_Info')
async def get_subscription_info(callback: CallbackQuery):
    await subscription_info(callback)


@router.message(Command("subcheck"), F.from_user.id == secrets.get('admin_id'))
async def broadcast_make(message: Message):
    await message.answer('Making a test of sub check handler', reply_markup=kb.subcheck)


@router.callback_query(F.data == 'sub_check')
async def sub_check(callback: CallbackQuery):
    sub_status = await check_tg_subscription(bot=bot, chat_id=secrets.get('news_id'), user_id=callback.from_user.id)
    if sub_status:
        await free_sub_handler(callback, secrets.get('free_days'), secrets.get('free_traffic'), True)


@router.callback_query(F.data == 'Invite_Friends')
async def invite_friends(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)

    tg_id = callback.from_user.id
    # Ensure the user has a referral code (creates one on first open).
    code = await rq.get_or_create_referral_code(tg_id)
    promo = await rq.get_promo_by_tg_id(tg_id)

    # Discount + reward tunables now come from promo_settings (single source
    # of truth) rather than config.yml.
    promo_grant = await rq.get_default_promo_credit_grant()
    promo_points_reward, _reward_cap = await rq.get_promo_reward_settings()

    text = lang.promo_invite_text.format(
        promo_code=code,
        invite_grant=promo_grant,
        reward_points=promo_points_reward,
        days_purchased=promo['days_purchased'] if promo else 0,
        points_rewarded=promo['points_rewarded'] if promo else 0,
    )

    await callback.message.edit_text(text=text, parse_mode='HTML', disable_web_page_preview=True,
                                     reply_markup=get_to_main_localized(lang))


@router.callback_query(F.data == 'subcheck_reactivate')
async def subcheck_reactivate(callback: CallbackQuery):
    """Handle re-subscription check after Sub Clean disabled the user."""
    lang = await get_user_lang(callback.from_user.id)
    tg_id = callback.from_user.id

    # Check if user is in disabled_users table
    disabled_info = await rq.get_disabled_user(tg_id)
    if not disabled_info:
        await callback.answer(lang.msg_sub_clean_not_disabled, show_alert=True)
        return

    # Check channel subscription
    is_subscribed = await check_tg_subscription(
        bot=bot, chat_id=secrets.get('news_id'), user_id=tg_id
    )

    if not is_subscribed:
        news_url = secrets.get('news_url', '')
        kb_retry = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=lang.btn_sub_channel, url=news_url)],
            [InlineKeyboardButton(text=lang.btn_i_resubscribed, callback_data="subcheck_reactivate")],
        ])
        await callback.message.edit_text(
            text=lang.msg_sub_clean_still_not_subscribed,
            parse_mode='HTML',
            disable_web_page_preview=True,
            reply_markup=kb_retry,
        )
        return

    # User is subscribed again — restore original status
    from remnawave_client import api as rem

    user_ctx = await rq.get_user_full_context(tg_id)
    if not user_ctx or user_ctx.get("rw_id") is None:
        await callback.message.edit_text(
            text=lang.msg_sub_clean_reactivation_error,
            parse_mode='HTML',
            disable_web_page_preview=True,
        )
        return

    original_status = disabled_info["original_status"]
    result = await rem.update_user_by_id(int(user_ctx["rw_id"]), status=original_status)

    if result:
        await rq.delete_disabled_user(tg_id)
        await callback.message.edit_text(
            text=lang.msg_sub_clean_reactivated,
            parse_mode='HTML',
            disable_web_page_preview=True,
        )
    else:
        await callback.message.edit_text(
            text=lang.msg_sub_clean_reactivation_error,
            parse_mode='HTML',
            disable_web_page_preview=True,
        )


# DISABLED: Marzban migration handlers removed — Remnawave is the only API
# @router.callback_query(F.data == 'Migrate_RemnaWave')
# async def migrate_to_remnawave_confirm(callback: CallbackQuery):
#     ...
#
# @router.callback_query(F.data == 'confirm_migrate')
# async def process_migration(callback: CallbackQuery):
#     ...
