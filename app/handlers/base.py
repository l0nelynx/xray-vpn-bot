from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
import logging
import app.database.requests as rq
import app.keyboards as kb
from app.keyboards.localized import (
    get_language_select_keyboard, get_others_localized, get_subcheck_free_localized,
    get_agreement_menu_localized, get_policy_menu_localized, get_to_main_localized,
    get_migration_confirm_localized, get_connect_localized, get_pay_methods_localized,
    get_settings_menu_localized, get_language_change_keyboard,
)
from app.locale.utils import get_user_lang
from app.handlers.events import userlist
from app.handlers.tools import startup_user_dialog, free_sub_handler, subscription_info, check_tg_subscription, \
    get_user_days

from app.settings import secrets, bot, admin_bot
import string
import random

router = Router()


@router.message(Command("start"))  # Start command handler
async def cmd_start(message: Message):
    if await rq.is_user_banned(message.from_user.id):
        lang = await get_user_lang(message.from_user.id)
        await message.answer(lang.msg_account_banned)
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
            reply_markup=get_language_select_keyboard()
        )
    else:
        # Language already chosen — go straight to main menu
        await startup_user_dialog(message)


@router.message(Command("lang"))  # Language change command
async def cmd_lang(message: Message):
    lang = await get_user_lang(message.from_user.id)
    await message.answer(
        text=lang.msg_lang_current,
        parse_mode='HTML',
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
                                     reply_markup=get_agreement_menu_localized(lang))


@router.callback_query(F.data == 'Privacy')
async def privacy_policy(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    await callback.message.edit_text(text=lang.privacy_policy, parse_mode='HTML',
                                     reply_markup=get_policy_menu_localized(lang))


@router.callback_query(F.data == 'Settings')
async def settings_menu(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    await callback.message.edit_text(
        text=lang.msg_settings,
        parse_mode='HTML',
        reply_markup=get_settings_menu_localized(lang)
    )


@router.callback_query(F.data == 'Change_Language')
async def change_language_menu(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    await callback.message.edit_text(
        text=lang.msg_lang_current,
        parse_mode='HTML',
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
                                         reply_markup=get_to_main_localized(lang))
        return

    username = callback.from_user.username
    if not username or username == "None":
        await callback.message.edit_text(text=lang.msg_username_required, parse_mode='HTML',
                                         reply_markup=get_to_main_localized(lang))
        return

    sub_status = await check_tg_subscription(bot=bot, chat_id=secrets.get('news_id'), user_id=callback.from_user.id)
    if sub_status:
        await free_sub_handler(callback, secrets.get('free_days'), secrets.get('free_traffic'))
    else:
        await callback.message.edit_text(text=lang.free_menu_notsub, parse_mode='HTML', disable_web_page_preview=True,
                                         reply_markup=get_subcheck_free_localized(lang))


@router.callback_query(F.data == 'Sub_Info')
async def get_subscription_info(callback: CallbackQuery):
    await subscription_info(callback)


@router.message(Command("subcheck"), F.from_user.id == secrets.get('admin_id'))
async def broadcast_make(message: Message):
    await message.answer('Making a test of sub check handler', reply_markup=kb.subcheck)


@router.callback_query(F.data == 'sub_check')
async def sub_check(callback: CallbackQuery):
    sub_status = await check_tg_subscription(bot=bot, chat_id=secrets.get('news_id'), user_id=callback.from_user.id)
    print(callback.from_user.id)
    print(secrets.get("admin_id"))
    print(sub_status)
    if sub_status:
        await free_sub_handler(callback, secrets.get('free_days'), secrets.get('free_traffic'), True)


@router.callback_query(F.data == 'Invite_Friends')
async def invite_friends(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)

    tg_id = callback.from_user.id
    promo = await rq.get_promo_by_tg_id(tg_id)

    if not promo:
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            existing = await rq.get_promo_by_code(code)
            if not existing:
                break
        await rq.create_promo(tg_id, code)
        promo = await rq.get_promo_by_tg_id(tg_id)

    promo_discount = secrets.get('promo_discount', 20)
    promo_days_reward = secrets.get('promo_days_reward', 3)

    text = lang.promo_invite_text.format(
        promo_code=promo['promo_code'],
        discount=promo_discount,
        reward_days=promo_days_reward,
        days_purchased=promo['days_purchased'],
        days_rewarded=promo['days_rewarded'],
    )

    await callback.message.edit_text(text=text, parse_mode='HTML', reply_markup=get_to_main_localized(lang))


@router.callback_query(F.data == 'Migrate_RemnaWave')
async def migrate_to_remnawave_confirm(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    await callback.message.edit_text(
        text=lang.marzban_user_with_upgrade_option,
        parse_mode='HTML',
        reply_markup=get_migration_confirm_localized(lang)
    )


@router.callback_query(F.data == 'confirm_migrate')
async def process_migration(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    from app.handlers.tools import detect_user_api_provider, get_user_info, add_new_user_info
    import app.database.requests as rq

    username = callback.from_user.username
    user_id = callback.from_user.id

    try:
        await callback.message.edit_text(
            text=lang.migration_in_progress,
            parse_mode='HTML'
        )

        api_provider = await detect_user_api_provider(user_id, username)

        if api_provider == "remnawave":
            await callback.message.edit_text(
                text=lang.msg_already_on_beta,
                parse_mode='HTML',
                reply_markup=get_to_main_localized(lang)
            )
            return

        user_info = await get_user_info(username, api="marzban")

        if user_info == 404:
            await callback.message.edit_text(
                text=lang.migration_error.format(support_bot=secrets.get('support_bot_id')),
                parse_mode='HTML',
                reply_markup=get_to_main_localized(lang)
            )
            return

        expire_days = await get_user_days(user_info)
        print(f"DAYS_{expire_days}")
        data_limit = user_info.get("data_limit", 0)

        is_pro = user_info.get("status") == "active" and data_limit is None

        if is_pro:
            squad_id = secrets.get("rw_pro_id")
            external_squad_id = secrets.get("rw_ext_pro_id")
            description = "Migrated from Marzban (Pro)"
        else:
            squad_id = secrets.get("rw_free_id")
            external_squad_id = secrets.get("rw_ext_free_id")
            description = "Migrated from Marzban (Free)"

        if data_limit == 0 or data_limit is None:
            data_limit = 0
        else:
            data_limit = data_limit // (1024 * 1024 * 1024)
        print(f"LIMIT_{data_limit}")

        new_user_info = await add_new_user_info(
            name=username,
            userid=user_id,
            limit=data_limit,
            res_strat="month",
            expire_days=expire_days,
            api="remnawave",
            email=f"{username}@marzban.ru",
            description=description,
            squad_id=squad_id,
            external_squad_id=external_squad_id,
        )

        if not new_user_info:
            await callback.message.edit_text(
                text=lang.migration_error.format(support_bot=secrets.get('support_bot_id')),
                parse_mode='HTML',
                reply_markup=get_to_main_localized(lang)
            )
            return

        print(f"{user_id}_USERID")
        await rq.update_user_api_info(tg_id=int(user_id),
                                      username=username,
                                      vless_uuid=new_user_info.get("uuid"),
                                      api_provider="remnawave")

        success_text = lang.migration_success.format(
            link=new_user_info.get("subscription_url"),
            days=expire_days,
            limit=data_limit if data_limit > 0 else "Без лимита"
        )

        await callback.message.edit_text(
            text=success_text,
            parse_mode='HTML',
            reply_markup=get_connect_localized(lang, new_user_info.get("subscription_url"))
        )

        # Admin message always in Russian
        from app.locale.lang_ru import admin_migration_message
        admin_message = admin_migration_message.format(
            username=username,
            user_id=user_id,
            expire_days=expire_days,
            data_limit=data_limit if data_limit > 0 else 'Без лимита',
            sub_type='Pro' if is_pro else 'Free'
        )

        _notify = admin_bot or bot
        await _notify.send_message(
            chat_id=secrets.get('admin_id'),
            text=admin_message,
            parse_mode='HTML'
        )

    except Exception as e:
        logging.error(f"Error during migration for {username}: {e}")
        await callback.message.edit_text(
            text=lang.migration_error.format(support_bot=secrets.get('support_bot_id')),
            parse_mode='HTML',
            reply_markup=get_to_main_localized(lang)
        )
