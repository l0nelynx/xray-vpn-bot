from aiogram import F, Router
from aiogram.types import Message

from app.settings import secrets
from .router import BTN_LOGS

logs_router = Router()


# ==================== Логи ошибок (reply-кнопка) ====================

@logs_router.message(F.text == BTN_LOGS, F.from_user.id == secrets.get('admin_id'))
async def admin_error_logs(message: Message):
    from app.log_buffer import error_log_handler

    if not error_log_handler or not error_log_handler.get_entries():
        await message.answer("Логи ошибок пусты.")
        return

    full_text = error_log_handler.format_entries_for_display()

    if len(full_text) <= 4096:
        await message.answer(full_text, parse_mode='HTML')
        return

    # Слишком длинный текст — отправляем по одной записи
    for entry in error_log_handler.get_entries():
        ts = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        msg = entry.message[:500] if len(entry.message) > 500 else entry.message
        text = f"<b>[{entry.level}]</b> {ts}\n<b>{entry.logger_name}</b>\n<code>{msg}</code>"
        if entry.traceback:
            tr = entry.traceback[:300] if len(entry.traceback) > 300 else entry.traceback
            text += f"\n<pre>{tr}</pre>"
        if len(text) > 4096:
            text = text[:4093] + "..."
        await message.answer(text, parse_mode='HTML')
