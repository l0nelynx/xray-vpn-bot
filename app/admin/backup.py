import logging
import os
import shutil
import subprocess
import zipfile
from datetime import datetime

from aiogram import F, Router
from aiogram.types import Message, FSInputFile

from app.settings import secrets
from .router import BTN_BACKUP

backup_router = Router()

DB_PATH = os.environ.get("DB_PATH", "db.sqlite3")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
MAX_BACKUP_SIZE_MB = 500


def _is_postgres() -> bool:
    return DATABASE_URL.startswith("postgresql")


def _dump_postgres(out_path: str) -> None:
    """Run pg_dump and write a plain-text SQL dump."""
    url = DATABASE_URL
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://"):]
    if url.startswith("postgresql+psycopg2://"):
        url = "postgresql://" + url[len("postgresql+psycopg2://"):]
    cmd = ["pg_dump", "--no-owner", "--no-acl", url]
    with open(out_path, "wb") as fh:
        subprocess.run(cmd, stdout=fh, check=True)


@backup_router.message(F.text == BTN_BACKUP, F.from_user.id == secrets.get('admin_id'))
async def admin_backup(message: Message):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = f"backup_{timestamp}.zip"
    payload_path: str | None = None

    try:
        if _is_postgres():
            if not shutil.which("pg_dump"):
                await message.answer("pg_dump не найден в контейнере. Проверьте Dockerfile.")
                return
            payload_path = f"backup_{timestamp}.sql"
            _dump_postgres(payload_path)
            arcname = "db.sql"
        else:
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
            payload_path = DB_PATH
            arcname = "db.sqlite3"

        await message.answer("Создание бекапа...")

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(payload_path, arcname)

        zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
        await message.answer_document(
            document=FSInputFile(zip_path, filename=f"backup_{timestamp}.zip"),
            caption=f"Бекап БД\nРазмер архива: {zip_size_mb:.1f} МБ",
        )
    except subprocess.CalledProcessError as exc:
        logging.error(f"pg_dump failed: {exc}")
        await message.answer(f"Ошибка pg_dump: код {exc.returncode}")
    except Exception as e:
        logging.error(f"Backup error: {e}")
        await message.answer(f"Ошибка создания бекапа: {e}")
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
        if _is_postgres() and payload_path and os.path.exists(payload_path):
            os.remove(payload_path)
