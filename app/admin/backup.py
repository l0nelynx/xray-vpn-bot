import asyncio
import logging
import os
import shutil
import subprocess
import zipfile
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
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


async def _run_backup(bot: Bot, admin_id: int) -> None:
    """Core backup logic — usable both from the bot command and the scheduler."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = f"backup_{timestamp}.zip"
    payload_path: str | None = None

    try:
        if _is_postgres():
            if not shutil.which("pg_dump"):
                await bot.send_message(admin_id, "pg_dump не найден в контейнере. Проверьте Dockerfile.")
                return
            payload_path = f"backup_{timestamp}.sql"
            _dump_postgres(payload_path)
            arcname = "db.sql"
        else:
            if not os.path.exists(DB_PATH):
                await bot.send_message(admin_id, "Файл БД не найден.")
                return
            db_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
            if db_size_mb > MAX_BACKUP_SIZE_MB:
                await bot.send_message(
                    admin_id,
                    f"Размер БД: <b>{db_size_mb:.1f} МБ</b>\n"
                    f"Превышает лимит {MAX_BACKUP_SIZE_MB} МБ, отправка невозможна.",
                    parse_mode="HTML",
                )
                return
            payload_path = DB_PATH
            arcname = "db.sqlite3"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(payload_path, arcname)

        zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
        await bot.send_document(
            chat_id=admin_id,
            document=FSInputFile(zip_path, filename=f"backup_{timestamp}.zip"),
            caption=f"Бекап БД\nРазмер архива: {zip_size_mb:.1f} МБ",
        )
    except subprocess.CalledProcessError as exc:
        logging.error("pg_dump failed: %s", exc)
        await bot.send_message(admin_id, f"Ошибка pg_dump: код {exc.returncode}")
    except Exception as e:
        logging.error("Backup error: %s", e)
        await bot.send_message(admin_id, f"Ошибка создания бекапа: {e}")
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
        if _is_postgres() and payload_path and os.path.exists(payload_path):
            os.remove(payload_path)


async def scheduled_backup_loop(bot: Bot, admin_id: int) -> None:
    """Daily backup at 01:00 local time. Runs as a background asyncio task."""
    while True:
        now = datetime.now()
        target = now.replace(hour=1, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        delay = (target - now).total_seconds()
        logging.info("Next scheduled backup in %.0f s (at %s)", delay, target.strftime("%Y-%m-%d %H:%M"))
        await asyncio.sleep(delay)
        logging.info("Running scheduled daily backup")
        await _run_backup(bot, admin_id)


@backup_router.message(F.text == BTN_BACKUP, F.from_user.id == secrets.get("admin_id"))
async def admin_backup(message: Message, bot: Bot):
    await message.answer("Создание бекапа...")
    await _run_backup(bot, message.from_user.id)
