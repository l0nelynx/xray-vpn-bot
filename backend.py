import logging

import asyncio

import app.api.aio_ggsel as aio_gg

from aiogram import Dispatcher

# from app.handlers.events import start_bot, stop_bot

from aiogram import Bot
from app.settings import load_config

secrets = load_config()
bot = Bot(token=secrets.get('ggsel_bot_token'))

# Инициализация бота
dp = Dispatcher()
# dp.include_router(router_base)
# dp.include_router(router_payments)
# dp.startup.register(start_bot)
# dp.shutdown.register(stop_bot)


async def on_startup(dispatcher, **kwargs):
    """Действия при запуске бота"""
    # asyncio.create_task(run_webserver())  # Запуск Uvicorn в фоне
    # asyncio.create_task(gg.order_delivery_loop())
    # asyncio.create_task(aio_gg.order_delivery_loop())


async def main():
    dp.startup.register(on_startup)
    #asyncio.run(dp.start_polling(bot))
    await asyncio.gather(dp.start_polling(bot),
                         aio_gg.order_delivery_loop())
# #        cp.start_polling(),


# if __name__ == "__main__":
#     asyncio.run(main())
#     logging.basicConfig(
#         level=logging.INFO,
#         format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
#     )
if __name__ == '__main__':
    asyncio.run(main())
    logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )