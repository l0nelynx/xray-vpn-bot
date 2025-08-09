import logging
import asyncio
from aiogram import Dispatcher
from app.settings import bot, cp
from app.handlers.events import start_bot, stop_bot
from app.handlers.base import router as router_base
from app.handlers.payments import router as router_payments

# import subprocess
# Инициализация бота
dp = Dispatcher()
dp.include_router(router_base)
dp.include_router(router_payments)
dp.startup.register(start_bot)
dp.shutdown.register(stop_bot)


async def main():
    await asyncio.gather(
        dp.start_polling(bot),
        cp.start_polling(),
    )


if __name__ == "__main__":
    asyncio.run(main())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
