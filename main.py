import logging
from aiogram import Dispatcher, F
from app.settings import bot
from app.handlers.events import start_bot, stop_bot, userlist
from app.handlers.base import router

# import subprocess
# Инициализация бота
dp = Dispatcher()
dp.include_router(router)
dp.startup.register(start_bot)
dp.shutdown.register(stop_bot)



if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    dp.run_polling(bot)
