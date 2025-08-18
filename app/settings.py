import yaml
import os
import asyncio
import uvicorn
from fastapi import FastAPI
from pathlib import Path

from aiogram import Bot
from aiosend import CryptoPay

app_uvi = FastAPI()


async def run_webserver():
    config = uvicorn.Config(app_uvi, host=secrets.get('uvicorn_host'), port=secrets.get('uvicorn_port'))
    server = uvicorn.Server(config)
    await server.serve()


def load_config(file_path="config.yml"):
    # Получаем абсолютный путь к файлу
    config_path = Path(__file__).parent.parent / file_path

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, 'r') as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise ValueError(f"Error parsing YAML: {exc}")


# Загрузка конфигурации при импорте модуля
try:
    secrets = load_config()
except Exception as e:
    print(f"⚠️ Error loading secrets: {e}")
    secrets = {}  # Fallback to empty dict


bot = Bot(token=secrets.get('token'))
cp = CryptoPay(secrets.get('crypto_bot_token'))


