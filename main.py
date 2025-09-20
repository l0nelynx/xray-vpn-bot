import logging

import asyncio
from aiogram import Dispatcher
from fastapi import Request, BackgroundTasks, Response, HTTPException
from app.api.a_pay import payment_webhook_handler as apays_webhook_handler
from app.api.crystal_pay import payment_webhook_handler as crystal_webhook_handler
# from app.api.digiseller import payment_webhook_handler as digiseller_webhook_handler
from app.api.digiseller import payment_async_logic
from app.handlers.base import router as router_base
from app.handlers.events import start_bot, stop_bot
from app.handlers.payments import router as router_payments
from app.settings import bot, cp, run_webserver, app_uvi

# import subprocess
# Инициализация бота
dp = Dispatcher()
dp.include_router(router_base)
dp.include_router(router_payments)
dp.startup.register(start_bot)
dp.shutdown.register(stop_bot)


@app_uvi.post("/apays_webhook")
async def payment_webhook(request: Request, background_tasks: BackgroundTasks):
    await apays_webhook_handler(request, background_tasks)


@app_uvi.post("/crystal_webhook")
async def payment_webhook(request: Request, background_tasks: BackgroundTasks):
    await crystal_webhook_handler(request, background_tasks)


@app_uvi.post("/digiseller_webhook")
async def payment_webhook(request: Request, response: Response):
    try:
        payment_data = await request.json()
        link = await payment_async_logic(payment_data)
        content = {
                "id": f"{payment_data['id']}",
                "inv": f"{payment_data['inv']}",
                "goods": f"{link}",
                "error": ""
        }
        response.status_code = 200
        return content
    except Exception as e:
        logging.error(f"Ошибка обработки платежа: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "id": "",
                "inv": "0",
                "goods": "",
                "error": "Internal server error"
            }
        )


async def on_startup(dispatcher, **kwargs):
    """Действия при запуске бота"""
    asyncio.create_task(run_webserver())  # Запуск Uvicorn в фоне


async def main():
    dp.startup.register(on_startup)
    await asyncio.gather(
        dp.start_polling(bot),
        cp.start_polling()
    )


if __name__ == "__main__":
    asyncio.run(main())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
