import logging
import os
import zipfile
from datetime import datetime

from aiogram import F, Router
from aiogram.types import Message, FSInputFile

from app.settings import secrets
from .router import BTN_BACKUP

backup_router = Router()

DB_PATH = "db.sqlite3"
MAX_BACKUP_SIZE_MB = 500


# ==================== Бекап БД (reply-кнопка) ====================

@backup_router.message(F.text == BTN_BACKUP, F.from_user.id == secrets.get('admin_id'))
async def admin_backup(message: Message):
    if not os.path.exists(DB_PATH):
        await message.answer("Файл БД не найден.")
        return

    db_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
    if db_size_mb > MAX_BACKUP_SIZE_MB:
        await message.answer(
            f"Размер БД: <b>{db_size_mb:.1f} МБ</b>\n"
            f"Превышает лимит {MAX_BACKUP_SIZE_MB} МБ, отправка невозможна.",
            parse_mode='HTML',
        )
        return

    await message.answer("Создание бекапа...")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = f"backup_{timestamp}.zip"

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(DB_PATH, "db.sqlite3")

        zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)

        await message.answer_document(
            document=FSInputFile(zip_path, filename=f"backup_{timestamp}.zip"),
            caption=(
                f"Бекап БД\n"
                f"Размер БД: {db_size_mb:.1f} МБ\n"
                f"Размер архива: {zip_size_mb:.1f} МБ"
            )
        )
    except Exception as e:
        logging.error(f"Backup error: {e}")
        await message.answer(f"Ошибка создания бекапа: {e}")
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
