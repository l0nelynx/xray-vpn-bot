import app.database.requests as rq
import app.keyboards as kb

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from app.handlers.events import userlist
from app.handlers.tools import startup_user_dialog, free_sub_handler, subscription_info
from app.locale.lang_ru import text_help
from app.settings import Secrets


router = Router()


@router.message(Command("start"))   # Start command handler
async def cmd_start(message: Message):
    await rq.set_user(message.from_user.id)
    await startup_user_dialog(message)


@router.callback_query(F.data == 'Main')
async def others(callback: CallbackQuery):
    await callback.answer('Вы в главном меню')
    await startup_user_dialog(callback)


@router.message(Command("users"), F.from_user.id == Secrets.admin_id)   # List of users in db (admin only)
async def user_db_check(message: Message):
    await message.answer('Making a user list from db')
    await userlist()


@router.callback_query(F.data == 'Others')
async def others(callback: CallbackQuery):
    await callback.answer('Раздел инструкций')
    await callback.message.edit_text('Выберите свою платформу:', reply_markup=kb.others)


@router.callback_query(F.data == 'Android_Help')
async def others(callback: CallbackQuery):
    await callback.answer('Инструкция для Android')
    await callback.message.edit_text(text=text_help, parse_mode='HTML', disable_web_page_preview=True,
                                     reply_markup=kb.others)


@router.callback_query(F.data == 'Free')
async def free_buy(callback: CallbackQuery):
    await free_sub_handler(callback, Secrets.free_days, Secrets.free_traffic)


@router.callback_query(F.data == 'Sub_Info')
async def get_subscription_info(callback: CallbackQuery):
    await subscription_info(callback)
