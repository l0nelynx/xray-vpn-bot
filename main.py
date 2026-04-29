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
from app.admin import router as router_admin
from app.handlers.base import router as router_base
from app.handlers.devices import router as router_devices
from app.handlers.events import start_bot, stop_bot
from app.handlers.payments import router as router_payments
from app.handlers.dynamic_menus import router as router_dynamic_menus
from app.settings import bot, admin_bot, cp, run_webserver, app_uvi, limiter

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
dp.callback_query.middleware(UsernameRequiredMiddleware())
dp.include_router(router_base)
dp.include_router(router_devices)
dp.include_router(router_payments)
dp.include_router(router_dynamic_menus)
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


async def on_startup(dispatcher, **kwargs):
    """Действия при запуске бота"""
    asyncio.create_task(run_webserver())


async def main():
    dp.startup.register(on_startup)
    tasks = [
        dp.start_polling(bot),
        cp.start_polling(),
    ]
    if admin_bot:
        tasks.append(admin_dp.start_polling(admin_bot))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    from app.log_buffer import init_error_log_handler
    from app.settings import secrets
    init_error_log_handler(maxlen=secrets.get('admin_logs_length', 20))
    asyncio.run(main())
