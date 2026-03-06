from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
import aiohttp
import logging
import app.database.requests as rq
import app.keyboards as kb
import app.locale.lang_ru as ru
from app.handlers.broadcast import admin_broadcast
from app.handlers.events import userlist
from app.handlers.tools import startup_user_dialog, free_sub_handler, subscription_info, check_tg_subscription, \
    get_user_days

from app.settings import secrets
from app.settings import bot
from app.api.remnawave.api import create_user, get_user_from_username, update_user

router = Router()
lang = eval(f"{secrets.get('language')}")


# @router.message(Command("create"))  # Start command handler
# async def cmd_start(message: Message):
#     # response = await create_user(username=message.from_user.username, days=30, limit_gb=40, descr='TEST')
#     # await message.answer(response["subscription_url"])
#     response1 = await get_user_from_username(username=message.from_user.username)
#     await message.answer(response1["subscription_url"])
#     response2 = await update_user(user_uuid="e77c0e2d-be53-4ef7-8d04-e65daac72ffe", username=message.from_user.username, days=50, limit_gb=40, descr='TEST')
#     await message.answer(f"{response2['expire']}")


@router.message(Command("start"))  # Start command handler
async def cmd_start(message: Message):
    await rq.set_user(message.from_user.id)
    await startup_user_dialog(message)


@router.callback_query(F.data == 'Agreement')  # Start command handler
async def user_agreement(callback: CallbackQuery):
    await callback.message.edit_text(text=lang.user_agreement, parse_mode='HTML',
                                     reply_markup=kb.agreement_menu)


@router.callback_query(F.data == 'Privacy')  # Start command handler
async def user_agreement(callback: CallbackQuery):
    await callback.message.edit_text(text=lang.privacy_policy, parse_mode='HTML',
                                     reply_markup=kb.policy_menu)


@router.callback_query(F.data == 'Main')
async def others(callback: CallbackQuery):
    await callback.answer(lang.text_answers['main_menu_greetings'])
    await startup_user_dialog(callback)


@router.message(Command("users"), F.from_user.id == secrets.get('admin_id'))  # List of users in db (admin only)
async def user_db_check(message: Message):
    await message.answer('Making a user list from db')
    await userlist()


@router.callback_query(F.data == 'Others')
async def others(callback: CallbackQuery):
    await callback.answer(lang.text_answers['instruction_greetings'])
    await callback.message.edit_text(lang.text_answers['instruction_platform_choose'], parse_mode='HTML',
                                     disable_web_page_preview=True, reply_markup=kb.others)


@router.callback_query(F.data == 'Android_Help')
async def others(callback: CallbackQuery):
    await callback.answer(lang.text_answers['instruction_android'])
    await callback.message.edit_text(text=ru.text_help, parse_mode='HTML', disable_web_page_preview=True,
                                     reply_markup=kb.others)


@router.callback_query(F.data == 'Windows_Help')
async def others(callback: CallbackQuery):
    await callback.answer(lang.text_answers['instruction_windows'])
    await callback.message.edit_text(text=ru.text_help_windows, parse_mode='HTML', disable_web_page_preview=True,
                                     reply_markup=kb.others)


@router.callback_query(F.data == 'Free')
async def free_version_menu(callback: CallbackQuery):
    # await free_sub_handler(callback, secrets.get('free_days'), secrets.get('free_traffic'))
    await callback.message.edit_text(text=ru.free_menu, parse_mode='HTML', disable_web_page_preview=True,
                                     reply_markup=kb.subcheck_free)


@router.callback_query(F.data == 'subcheck_free')
async def free_buy(callback: CallbackQuery):
    sub_status = await check_tg_subscription(bot=bot, chat_id=secrets.get('news_id'), user_id=callback.from_user.id)
    if sub_status:
        await free_sub_handler(callback, secrets.get('free_days'), secrets.get('free_traffic'))
    else:
        await callback.message.edit_text(text=ru.free_menu_notsub, parse_mode='HTML', disable_web_page_preview=True,
                                         reply_markup=kb.subcheck_free)


@router.callback_query(F.data == 'Sub_Info')
async def get_subscription_info(callback: CallbackQuery):
    await subscription_info(callback)


@router.message(Command("broadcast"), F.from_user.id == secrets.get('admin_id'))  #
async def broadcast_make(message: Message):
    await message.answer('Making a broadcast')
    await admin_broadcast(message, test_flag='')


@router.message(Command("broadcast_test"), F.from_user.id == secrets.get('admin_id'))  #
async def broadcast_make(message: Message):
    await message.answer('Making a test broadcast to this chat')
    await admin_broadcast(message, test_flag='_test')


@router.message(Command("broadcast_news"), F.from_user.id == secrets.get('admin_id'))  #
async def broadcast_make(message: Message):
    await message.answer('Making a broadcast to a new channel')
    await admin_broadcast(message, test_flag='_news', post_id=secrets.get('news_id'))

# broadcast activity flag
broadcast_active = False


@router.callback_query(F.data == 'cancel_broadcast')
async def cancel_broadcast(callback_query: CallbackQuery):
    global broadcast_active
    broadcast_active = False
    await callback_query.answer("Рассылка будет остановлена после отправки текущего пакета сообщений",
                                reply_markup=kb.cancel_keyboard)


@router.message(Command("subcheck"), F.from_user.id == secrets.get('admin_id'))  #
async def broadcast_make(message: Message):
    await message.answer('Making a test of sub check handler', reply_markup=kb.subcheck)


@router.callback_query(F.data == 'sub_check')  # Start command handler
async def sub_check(callback: CallbackQuery):
    sub_status = await check_tg_subscription(bot=bot, chat_id=secrets.get('news_id'), user_id=callback.from_user.id)
    print(callback.from_user.id)
    print(secrets.get("admin_id"))
    print(sub_status)
    if sub_status:
        await free_sub_handler(callback, secrets.get('free_days'), secrets.get('free_traffic'), True)


@router.callback_query(F.data == 'Migrate_RemnaWave')
async def migrate_to_remnawave_confirm(callback: CallbackQuery):
    """Показываем подтвержение миграции"""
    from app.locale.lang_ru import marzban_user_with_upgrade_option

    await callback.message.edit_text(
        text=marzban_user_with_upgrade_option,
        parse_mode='HTML',
        reply_markup=kb.get_migration_confirm()
    )


@router.callback_query(F.data == 'confirm_migrate')
async def process_migration(callback: CallbackQuery):
    """Обрабатывает миграцию пользователя из Marzban в RemnaWave"""
    from app.locale.lang_ru import migration_in_progress, migration_success, migration_error
    from app.handlers.tools import detect_user_api_provider, get_user_info, add_new_user_info
    import app.database.requests as rq

    username = callback.from_user.username
    user_id = callback.from_user.id

    try:
        # Показываем статус "в процессе"
        await callback.message.edit_text(
            text=migration_in_progress,
            parse_mode='HTML'
        )

        # Определяем API провайдер
        api_provider = await detect_user_api_provider(user_id, username)

        # Если пользователь уже на RemnaWave, отправляем ошибку
        if api_provider == "remnawave":
            await callback.message.edit_text(
                text="❌ <b>Вы уже зарегистрированы в Beta!</b>",
                parse_mode='HTML',
                reply_markup=kb.get_to_main()
            )
            return

        # Получаем текущую информацию пользователя из Marzban
        user_info = await get_user_info(username, api="marzban")

        if user_info == 404:
            await callback.message.edit_text(
                text=migration_error.format(support_bot=secrets.get('support_bot_id')),
                parse_mode='HTML',
                reply_markup=kb.get_to_main()
            )
            return

        # Определяем параметры подписки
        # expire_days = user_info.get("expire", 30)
        expire_days = await get_user_days(user_info)
        print(f"DAYS_{expire_days}")
        data_limit = user_info.get("data_limit", 0)

        # Определяем тип подписки (Pro или Free)
        is_pro = user_info.get("status") == "active" and data_limit is None

        # Выбираем squad_id в зависимости от типа подписки
        if is_pro:
            squad_id = secrets.get("rw_pro_id")
            description = "Migrated from Marzban (Pro)"
        else:
            squad_id = secrets.get("rw_free_id")
            description = "Migrated from Marzban (Free)"
            # Для Free подписки устанавливаем лимит 50GB если он был 0
        # Marzban возвращает data_limit в байтах, а RemnaWave принимает в GB
        if data_limit == 0 or data_limit is None:
                data_limit = 0
        else:
                data_limit = data_limit // (1024 * 1024 * 1024)
        print(f"LIMIT_{data_limit}")

        # Создаем пользователя в RemnaWave
        new_user_info = await add_new_user_info(
            name=username,
            userid=user_id,
            limit=data_limit,
            res_strat="month",
            expire_days=expire_days,
            api="remnawave",
            email=f"{username}@marzban.ru",
            description=description,
            squad_id=squad_id
        )

        if not new_user_info:
            await callback.message.edit_text(
                text=migration_error.format(support_bot=secrets.get('support_bot_id')),
                parse_mode='HTML',
                reply_markup=kb.get_to_main()
            )
            return

        # Обновляем информацию в БД
        print(f"{user_id}_USERID")
        # await rq.update_user_api_info(
        #     tg_id=user_id,
        #     username=username,
        #     vless_uuid=new_user_info.get("uuid"),
        #     api_provider="remnawave"
        # )
        await rq.update_user_api_info(tg_id=int(user_id),
                                      username=username,
                                      vless_uuid=new_user_info.get("uuid"),
                                      api_provider="remnawave")


        # Отправляем сообщение об успешной миграции
        success_text = migration_success.format(
            link=new_user_info.get("subscription_url"),
            days=expire_days,
            limit=data_limit if data_limit > 0 else "Без лимита"
        )

        await callback.message.edit_text(
            text=success_text,
            parse_mode='HTML',
            reply_markup=kb.connect(new_user_info.get("subscription_url"))
        )

        # Отправляем уведомление администратору
        admin_message = f"""✅ <b>Миграция пользователя успешна</b>

👤 Пользователь: @{username}
🆔 User ID: {user_id}
🔄 Источник: Marzban
📍 Назначение: RemnaWave
⏱️ Дней подписки: {expire_days}
💾 Лимит трафика: {data_limit if data_limit > 0 else 'Без лимита'} GB
🏷️ Тип: {'Pro' if is_pro else 'Free'}"""

        await bot.send_message(
            chat_id=secrets.get('admin_id'),
            text=admin_message,
            parse_mode='HTML'
        )

    except Exception as e:
        logging.error(f"Error during migration for {username}: {e}")
        await callback.message.edit_text(
            text=migration_error.format(support_bot=secrets.get('support_bot_id')),
            parse_mode='HTML',
            reply_markup=kb.get_to_main()
        )
