import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import app.database.requests as rq
import app.api.remnawave.api as rem
from app.locale.utils import get_user_lang

logger = logging.getLogger(__name__)

router = Router()

DEVICES_PER_PAGE = 5


async def _get_user_uuid(tg_id: int, username: str) -> str | None:
    """Получает vless_uuid пользователя из БД, при отсутствии пытается найти по email в RemnaWave."""
    user_info = await rq.get_full_username_info(username)
    if user_info and user_info.get("vless_uuid"):
        return user_info["vless_uuid"]

    # uuid нет — пробуем найти пользователя в RemnaWave по email, затем по username
    rw_user = None
    email = await rq.get_user_email(tg_id)
    if email:
        rw_user = await rem.get_user_from_email(email)
    if not rw_user:
        rw_user = await rem.get_user_from_username(username)

    if rw_user and rw_user.get("uuid"):
        await rq.update_user_api_info(
            tg_id=tg_id,
            username=username,
            vless_uuid=rw_user["uuid"],
            api_provider="remnawave",
        )
        logger.info("Resolved and saved uuid for user %s (tg_id=%s)", username, tg_id)
        return rw_user["uuid"]

    return None


def _build_devices_keyboard(devices: list, lang, page: int = 0) -> InlineKeyboardMarkup:
    """Строит клавиатуру со списком устройств с пагинацией."""
    total = len(devices)
    total_pages = max(1, (total + DEVICES_PER_PAGE - 1) // DEVICES_PER_PAGE)
    page = max(0, min(page, total_pages - 1))

    start = page * DEVICES_PER_PAGE
    end = min(start + DEVICES_PER_PAGE, total)
    page_devices = devices[start:end]

    buttons = []
    for i, device in enumerate(page_devices, start=start + 1):
        platform = device.platform or "Unknown"
        agent = device.user_agent or "—"
        label = f"{i}. {platform} [{agent}]"
        if len(label) > 60:
            label = label[:57] + "..."
        buttons.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"hwid_device:{i-1}"
            )
        ])

    # Навигация по страницам
    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"hwid_page:{page-1}"))
        nav_row.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"hwid_page:{page+1}"))
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(text=lang.btn_to_main, callback_data='Main')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _build_device_info_keyboard(device_index: int, page: int, lang) -> InlineKeyboardMarkup:
    """Строит клавиатуру для конкретного устройства."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lang.btn_delete_device, callback_data=f"hwid_delete:{device_index}")],
        [InlineKeyboardButton(text=lang.btn_back_to_devices, callback_data=f"hwid_page:{page}")],
        [InlineKeyboardButton(text=lang.btn_to_main, callback_data='Main')],
    ])


def _format_datetime(dt) -> str:
    """Форматирует datetime для отображения."""
    if dt is None:
        return "—"
    if hasattr(dt, 'strftime'):
        return dt.strftime("%d.%m.%Y %H:%M")
    return str(dt)


# ============================================================================
# /devices command and "Devices" / "hwid_page:" callbacks — show list
# ============================================================================

async def _show_devices(message_func, tg_id: int, username: str, lang, page: int = 0):
    """Общая логика показа списка устройств."""
    user_uuid = await _get_user_uuid(tg_id, username)
    if not user_uuid:
        await message_func(
            text=lang.msg_devices_no_subscription,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=lang.btn_to_main, callback_data='Main')]
            ])
        )
        return

    response = await rem.get_user_hwid_devices(user_uuid)
    if response is None:
        await message_func(
            text=lang.msg_devices_error,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=lang.btn_to_main, callback_data='Main')]
            ])
        )
        return

    if response.total == 0 or not response.devices:
        await message_func(
            text=lang.msg_devices_empty,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=lang.btn_to_main, callback_data='Main')]
            ])
        )
        return

    keyboard = _build_devices_keyboard(response.devices, lang, page)
    await message_func(
        text=lang.msg_devices_title.format(total=response.total),
        parse_mode='HTML',
        reply_markup=keyboard
    )


@router.message(Command("devices"))
async def cmd_devices(message: Message):
    lang = await get_user_lang(message.from_user.id)
    await _show_devices(message.answer, message.from_user.id, message.from_user.username, lang)


@router.callback_query(F.data == 'Devices')
async def cb_devices(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    await _show_devices(callback.message.edit_text, callback.from_user.id, callback.from_user.username, lang)


@router.callback_query(F.data.startswith('hwid_page:'))
async def cb_devices_page(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    page = int(callback.data.split(':')[1])
    await _show_devices(callback.message.edit_text, callback.from_user.id, callback.from_user.username, lang, page)


@router.callback_query(F.data == 'noop')
async def cb_noop(callback: CallbackQuery):
    await callback.answer()


# ============================================================================
# Device info — show details for a specific device
# ============================================================================

@router.callback_query(F.data.startswith('hwid_device:'))
async def cb_device_info(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    device_index = int(callback.data.split(':')[1])

    user_uuid = await _get_user_uuid(callback.from_user.id, callback.from_user.username)
    if not user_uuid:
        await callback.answer(lang.msg_devices_no_subscription, show_alert=True)
        return

    response = await rem.get_user_hwid_devices(user_uuid)
    if response is None or not response.devices or device_index >= len(response.devices):
        await callback.answer(lang.msg_devices_error, show_alert=True)
        return

    device = response.devices[device_index]
    page = device_index // DEVICES_PER_PAGE
    text = lang.msg_device_info.format(
        num=device_index + 1,
        model=device.device_model or "—",
        platform=device.platform or "—",
        os_version=device.os_version or "—",
        user_agent=device.user_agent or "—",
        created_at=_format_datetime(device.created_at),
        updated_at=_format_datetime(device.updated_at),
    )

    await callback.message.edit_text(
        text=text,
        parse_mode='HTML',
        reply_markup=_build_device_info_keyboard(device_index, page, lang)
    )


# ============================================================================
# Delete device
# ============================================================================

@router.callback_query(F.data.startswith('hwid_delete:'))
async def cb_device_delete(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    device_index = int(callback.data.split(':')[1])

    user_uuid = await _get_user_uuid(callback.from_user.id, callback.from_user.username)
    if not user_uuid:
        await callback.answer(lang.msg_devices_no_subscription, show_alert=True)
        return

    response = await rem.get_user_hwid_devices(user_uuid)
    if response is None or not response.devices or device_index >= len(response.devices):
        await callback.answer(lang.msg_devices_error, show_alert=True)
        return

    device = response.devices[device_index]
    result = await rem.delete_user_hwid_device(user_uuid, device.hwid)

    if result is not None:
        await callback.answer(lang.msg_device_deleted, show_alert=True)
        # Возвращаем на страницу, корректируя если она стала пустой
        page = device_index // DEVICES_PER_PAGE
        remaining = len(response.devices) - 1
        max_page = max(0, (remaining + DEVICES_PER_PAGE - 1) // DEVICES_PER_PAGE - 1)
        page = min(page, max_page)
        await _show_devices(callback.message.edit_text, callback.from_user.id, callback.from_user.username, lang, page)
    else:
        await callback.answer(lang.msg_device_delete_error, show_alert=True)
