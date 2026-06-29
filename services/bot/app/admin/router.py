from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)

import app.database.requests as rq
from app.settings import secrets

router = Router()

# Тексты кнопок главного меню
BTN_USERS = "Пользователи"
BTN_CLEANUP = "Очистка БД"
BTN_FILL_USERNAMES = "Заполнить username"
BTN_BACKUP = "Бекап БД"
BTN_ANNOUNCE = "Объявления"
BTN_PROMOS = "Промокоды"
BTN_BAN = "Бан/Разбан"
BTN_CLEANUP_TX = "Очистка транзакций"
BTN_LOGS = "Логи ошибок"
BTN_SUB_CLEAN = "Sub Clean"
BTN_TELEMT_CLEAN = "Telemt Clean"
BTN_CONFIG = "Конфигурация"
BTN_CLOSE = "Закрыть админку"


class AdminState(StatesGroup):
    waiting_message = State()
    in_admin = State()
    broadcast_text = State()
    channel_text = State()
    channel_attach_btn = State()
    user_search = State()
    email_input = State()
    ban_input = State()
    config_param_edit = State()


def is_admin(user_id: int) -> bool:
    return user_id == secrets.get('admin_id')


def admin_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_USERS), KeyboardButton(text=BTN_CLEANUP)],
            [KeyboardButton(text=BTN_FILL_USERNAMES), KeyboardButton(text=BTN_BACKUP)],
            [KeyboardButton(text=BTN_PROMOS), KeyboardButton(text=BTN_ANNOUNCE)],
            [KeyboardButton(text=BTN_CLEANUP_TX), KeyboardButton(text=BTN_BAN)],
            [KeyboardButton(text=BTN_LOGS), KeyboardButton(text=BTN_SUB_CLEAN)],
            [KeyboardButton(text=BTN_TELEMT_CLEAN), KeyboardButton(text=BTN_CONFIG)],
            [KeyboardButton(text=BTN_CLOSE)],
        ],
        resize_keyboard=True,
    )


async def _admin_stats_text() -> str:
    total = await rq.get_users_count()
    paid = await rq.get_paid_users_count()
    free = await rq.get_free_users_count()
    by_api = await rq.get_users_count_by_api()

    api_stats = "\n".join(f"  • {api}: {count}" for api, count in by_api.items())

    return (
        f"<b>Админ-панель</b>\n\n"
        f"Всего пользователей: <b>{total}</b>\n"
        f"Платных: <b>{paid}</b>\n"
        f"Бесплатных: <b>{free}</b>\n\n"
        f"По API провайдерам:\n{api_stats}"
    )


# ==================== /admin — Главное меню ====================

@router.message(Command("admin"), F.from_user.id == secrets.get('admin_id'))
async def cmd_admin(message: Message, state: FSMContext):
    await state.set_state(AdminState.in_admin)
    text = await _admin_stats_text()
    await message.answer(text, parse_mode='HTML', reply_markup=admin_menu_kb())


# ==================== Закрыть админку ====================

@router.message(F.text == BTN_CLOSE, F.from_user.id == secrets.get('admin_id'))
async def admin_close(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Админ-панель закрыта.", reply_markup=ReplyKeyboardRemove())


# ==================== Возврат в главное меню (inline) ====================

@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.in_admin)
    text = await _admin_stats_text()
    await callback.message.edit_text(text, parse_mode='HTML')


# noop для кнопки-счётчика страниц
@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()


# ==================== Подключение под-роутеров ====================

from .users import users_router
from .ban import ban_router
from .delete import delete_router
from .migrate import migrate_router
from .messaging import messaging_router
from .cleanup import cleanup_router
from .backup import backup_router
from .announce import announce_router
from .email import email_router
from .promos import promos_router
from .logs import logs_router
from .config_manager import config_router
from .sub_clean import sub_clean_router
from .telemt_clean import telemt_clean_router

router.include_router(users_router)
router.include_router(ban_router)
router.include_router(delete_router)
router.include_router(migrate_router)
router.include_router(messaging_router)
router.include_router(cleanup_router)
router.include_router(backup_router)
router.include_router(announce_router)
router.include_router(email_router)
router.include_router(promos_router)
router.include_router(logs_router)
router.include_router(config_router)
router.include_router(sub_clean_router)
router.include_router(telemt_clean_router)
