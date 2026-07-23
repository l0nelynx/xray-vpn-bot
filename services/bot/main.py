import logging

import asyncio

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, ErrorEvent
from fastapi import Request, BackgroundTasks, Response, HTTPException
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.api.a_pay import payment_webhook_handler as apays_webhook_handler
from app.api.crystal_pay import payment_webhook_handler as crystal_webhook_handler
from app.api.crypto_pay import cryptopay_webhook_handler
from app.api.platega import payment_webhook_handler as platega_webhook_handler
from app.api.paritypay import payment_webhook_handler as paritypay_webhook_handler
from app.api.remnawave_webhook import remnawave_webhook_handler
from app.admin import router as router_admin
from app.handlers.base import router as router_base
from app.handlers.giveaways import giveaway_router
from app.handlers.devices import router as router_devices
from app.handlers.events import start_bot, stop_bot
from app.middlewares import MaintenanceMiddleware
from app.settings import bot, admin_bot, run_webserver, app_uvi, limiter, secrets, _yaml_secrets
from app.bot_constructor import get_router as get_bot_constructor_router

app_uvi.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

class UsernameRequiredMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[CallbackQuery, dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        if not event.from_user.username:
            await event.answer(
                "Для использования бота установите username в настройках Telegram.",
                show_alert=True,
            )
            return
        return await handler(event, data)


# Инициализация основного бота
dp = Dispatcher()
_admin_id = secrets.get("admin_id")
try:
    _admin_id_int = int(_admin_id) if _admin_id is not None else None
except (TypeError, ValueError):
    _admin_id_int = None
dp.message.middleware(MaintenanceMiddleware(_admin_id_int))
dp.callback_query.middleware(MaintenanceMiddleware(_admin_id_int))
dp.callback_query.middleware(UsernameRequiredMiddleware())
dp.include_router(router_base)
dp.include_router(giveaway_router)
dp.include_router(router_devices)
dp.include_router(get_bot_constructor_router())
dp.startup.register(start_bot)
dp.shutdown.register(stop_bot)


@dp.errors()
async def error_handler(event: ErrorEvent):
    if isinstance(event.exception, TelegramBadRequest) and "message is not modified" in str(event.exception):
        logging.debug("Suppressed 'message is not modified' error")
        return True
    raise event.exception


# Инициализация admin бота
admin_dp = Dispatcher()
admin_dp.include_router(router_admin)


@app_uvi.get("/health")
async def health_check():
    """Health check endpoint для docker healthcheck"""
    return {"status": "healthy", "message": "Bot is running"}


@app_uvi.post("/bot/apays_webhook")
@limiter.limit("30/minute")
async def payment_webhook_apays(request: Request, background_tasks: BackgroundTasks):
    await apays_webhook_handler(request, background_tasks)


@app_uvi.post("/bot/crystal_webhook")
@limiter.limit("30/minute")
async def payment_webhook_crystal(request: Request, background_tasks: BackgroundTasks):
    await crystal_webhook_handler(request, background_tasks)


@app_uvi.post("/bot/cryptopay_webhook")
@limiter.limit("60/minute")
async def payment_webhook_cryptopay(request: Request, background_tasks: BackgroundTasks):
    return await cryptopay_webhook_handler(request, background_tasks)


@app_uvi.post("/bot/platega_webhook")
@limiter.limit("60/minute")
async def payment_webhook_platega(request: Request, background_tasks: BackgroundTasks):
    return await platega_webhook_handler(request, background_tasks)


@app_uvi.post("/bot/paritypay_webhook")
@limiter.limit("60/minute")
async def payment_webhook_paritypay(request: Request, background_tasks: BackgroundTasks):
    return await paritypay_webhook_handler(request, background_tasks)


@app_uvi.post("/bot/remnawave_webhook")
@limiter.limit("120/minute")
async def remnawave_webhook(request: Request, background_tasks: BackgroundTasks):
    return await remnawave_webhook_handler(request, background_tasks)


async def on_startup(dispatcher, **kwargs):
    asyncio.create_task(run_webserver())
    from app.database.models import async_session
    from common_db.runtime_config import bootstrap_runtime_overlay, runtime_overlay_poll_loop
    from app.admin.backup import scheduled_backup_loop
    from app.settings import _yaml_secrets

    crypto_secret = str(
        _yaml_secrets.get("payments_secrets_key")
        or _yaml_secrets.get("dashboard_secret")
        or ""
    )
    await bootstrap_runtime_overlay(async_session, _yaml_secrets, crypto_secret=crypto_secret)
    asyncio.create_task(runtime_overlay_poll_loop(async_session))

    admin_id = secrets.get("admin_id")
    if admin_id:
        asyncio.create_task(scheduled_backup_loop(bot, int(admin_id)))
        logging.info("Scheduled daily backup at 01:00 for admin_id=%s", admin_id)


async def main():
    dp.startup.register(on_startup)

    tasks = [dp.start_polling(bot)]
    if admin_bot:
        tasks.append(admin_dp.start_polling(admin_bot))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    from app.log_buffer import init_error_log_handler
    init_error_log_handler(maxlen=secrets.get('admin_logs_length', 20))
    asyncio.run(main())
