import math

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from app.settings import secrets, _original_config
from .router import AdminState, is_admin, BTN_CONFIG

config_router = Router()

PER_PAGE = 10

# Ключи, значения которых маскируются в интерфейсе
SENSITIVE_KEYS = {
    "token", "support_token", "admin_bot_token", "crypto_bot_token",
    "auth_pass", "crystal_secret", "crystal_salt", "apay_secret",
    "platega_api_key", "remnawave_token", "dig_pass",
}


def _mask_value(key: str, value) -> str:
    """Маскирует значение чувствительных ключей."""
    if key in SENSITIVE_KEYS:
        s = str(value)
        if len(s) <= 4:
            return "****"
        return s[:4] + "****"
    return str(value)


def _type_label(value) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "str"


def _is_modified(key: str) -> bool:
    """Проверяет, было ли значение изменено относительно оригинала."""
    return secrets.get(key) != _original_config.get(key)


def _build_config_list(page: int):
    keys = sorted(secrets.keys())
    total = len(keys)
    total_pages = max(1, math.ceil(total / PER_PAGE))
    page = max(0, min(page, total_pages - 1))

    page_keys = keys[page * PER_PAGE:(page + 1) * PER_PAGE]

    buttons = []
    for key in page_keys:
        value = secrets[key]
        modified = " *" if _is_modified(key) else ""
        type_label = _type_label(value)
        buttons.append([
            InlineKeyboardButton(
                text=f"{key} [{type_label}]{modified}",
                callback_data=f"cfg_param:{key}"
            )
        ])

    # Навигация
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀", callback_data=f"cfg_list:{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="▶", callback_data=f"cfg_list:{page + 1}"))
    buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(text="Назад", callback_data="admin_back")])

    text = (
        f"<b>Конфигурация</b> (стр. {page + 1}/{total_pages}, всего: {total})\n"
        f"<i>* = изменено в runtime</i>"
    )
    return text, InlineKeyboardMarkup(inline_keyboard=buttons)


def _build_param_card(key: str):
    value = secrets.get(key)
    original = _original_config.get(key)
    modified = _is_modified(key)

    display_value = _mask_value(key, value)
    display_original = _mask_value(key, original)
    type_label = _type_label(original if original is not None else value)
    status = "Изменено" if modified else "Оригинал"

    text = (
        f"<b>Параметр:</b> <code>{key}</code>\n"
        f"<b>Тип:</b> {type_label}\n"
        f"<b>Текущее значение:</b> <code>{display_value}</code>\n"
        f"<b>Статус:</b> {status}"
    )
    if modified:
        text += f"\n<b>Оригинал:</b> <code>{display_original}</code>"

    buttons = [
        [InlineKeyboardButton(text="Изменить", callback_data=f"cfg_edit:{key}")],
    ]
    if modified:
        buttons.append([InlineKeyboardButton(text="Сбросить", callback_data=f"cfg_reset:{key}")])
    buttons.append([InlineKeyboardButton(text="Назад", callback_data="cfg_list:0")])

    return text, InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== Конфигурация (reply-кнопка) ====================

@config_router.message(F.text == BTN_CONFIG, F.from_user.id == secrets.get('admin_id'))
async def admin_config_btn(message: Message):
    text, kb = _build_config_list(0)
    await message.answer(text, parse_mode='HTML', reply_markup=kb)


# ==================== Пагинация списка параметров ====================

@config_router.callback_query(F.data.startswith("cfg_list:"))
async def config_list_page(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    page = int(callback.data.split(":")[1])
    text, kb = _build_config_list(page)
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=kb)


# ==================== Карточка параметра ====================

@config_router.callback_query(F.data.startswith("cfg_param:"))
async def config_param_card(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    key = callback.data.split(":", 1)[1]
    if key not in secrets:
        await callback.answer("Параметр не найден", show_alert=True)
        return
    text, kb = _build_param_card(key)
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=kb)


# ==================== Редактирование параметра ====================

@config_router.callback_query(F.data.startswith("cfg_edit:"))
async def config_edit_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    key = callback.data.split(":", 1)[1]
    if key not in secrets:
        await callback.answer("Параметр не найден", show_alert=True)
        return

    await state.set_state(AdminState.config_param_edit)
    await state.update_data(config_edit_key=key)

    original = _original_config.get(key)
    type_label = _type_label(original if original is not None else secrets[key])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data=f"cfg_param:{key}")]
    ])

    await callback.message.edit_text(
        f"Введите новое значение для <code>{key}</code>\n"
        f"Ожидаемый тип: <b>{type_label}</b>",
        parse_mode='HTML',
        reply_markup=kb,
    )


@config_router.message(AdminState.config_param_edit, F.from_user.id == secrets.get('admin_id'))
async def config_edit_save(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data.get("config_edit_key")
    await state.set_state(AdminState.in_admin)

    if not key or key not in secrets:
        await message.answer("Параметр не найден.")
        return

    raw = message.text.strip()
    original = _original_config.get(key)
    ref_value = original if original is not None else secrets[key]

    # Валидация и приведение типа
    try:
        if isinstance(ref_value, bool):
            if raw.lower() in ("true", "1", "yes", "да"):
                new_value = True
            elif raw.lower() in ("false", "0", "no", "нет"):
                new_value = False
            else:
                await message.answer(
                    f"Ожидался тип <b>bool</b> (true/false).\nВведено: <code>{raw}</code>",
                    parse_mode='HTML',
                )
                return
        elif isinstance(ref_value, int):
            new_value = int(raw)
        elif isinstance(ref_value, float):
            new_value = float(raw)
        else:
            new_value = raw
    except (ValueError, TypeError):
        expected = _type_label(ref_value)
        await message.answer(
            f"Ошибка: невозможно привести <code>{raw}</code> к типу <b>{expected}</b>.",
            parse_mode='HTML',
        )
        return

    secrets[key] = new_value

    display = _mask_value(key, new_value)
    await message.answer(
        f"Параметр <code>{key}</code> обновлён.\n"
        f"Новое значение: <code>{display}</code>\n\n"
        f"<i>Изменение действует до перезапуска бота.</i>",
        parse_mode='HTML',
    )


# ==================== Сброс параметра ====================

@config_router.callback_query(F.data.startswith("cfg_reset:"))
async def config_reset_param(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    key = callback.data.split(":", 1)[1]

    if key not in _original_config:
        await callback.answer("Оригинальное значение не найдено", show_alert=True)
        return

    secrets[key] = _original_config[key]
    await callback.answer(f"Параметр {key} сброшен к оригиналу", show_alert=True)

    text, kb = _build_param_card(key)
    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=kb)
