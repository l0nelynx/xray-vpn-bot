
import app.database.requests as rq
import app.keyboards as kb
import app.locale.lang_ru as ru

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from app.handlers.events import userlist
from app.handlers.tools import startup_user_dialog, free_sub_handler, subscription_info
# from app.locale.lang_ru import text_help
from app.settings import secrets
# from app.utils import create_smart_invoice

router = Router()
lang = eval(f"{secrets.get('language')}")


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


@router.message(Command("pay"), F.from_user.id == secrets.get('admin_id'))  # Testing ground
async def cmd_buy(message: Message):
    await message.answer('Testing only')
    await message.answer(
        "Интеграция платежной системы",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="КУПИТЬ", callback_data="SBP_Plans")]
            ]
        )
    )


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
    await callback.message.edit_text(lang.text_answers['instruction_platform_choose'], reply_markup=kb.others)


@router.callback_query(F.data == 'Android_Help')
async def others(callback: CallbackQuery):
    await callback.answer(lang.text_answers['instruction_android'])
    await callback.message.edit_text(text=ru.text_help, parse_mode='HTML', disable_web_page_preview=True,
                                     reply_markup=kb.others)


@router.callback_query(F.data == 'Free')
async def free_buy(callback: CallbackQuery):
    await free_sub_handler(callback, secrets.get('free_days'), secrets.get('free_traffic'))


@router.callback_query(F.data == 'Sub_Info')
async def get_subscription_info(callback: CallbackQuery):
    await subscription_info(callback)
