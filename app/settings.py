from pathlib import Path

import uvicorn
import yaml
from aiogram import Bot
from aiosend import CryptoPay
from fastapi import FastAPI

app_uvi = FastAPI()


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

async def run_webserver():
    config = uvicorn.Config(app_uvi, host=secrets.get('uvicorn_host'), port=secrets.get('uvicorn_port'),
                            ssl_keyfile=secrets.get('uvicorn_ssl_key'), ssl_certfile=secrets.get('uvicorn_ssl_cert'))
    server = uvicorn.Server(config)
    await server.serve()

# Загрузка конфигурации при импорте модуля
try:
    secrets = load_config()
    print(f"✓ Config loaded successfully. Token: {secrets.get('token')[:10] if secrets.get('token') else 'NOT FOUND'}...")
except Exception as e:
    print(f"❌ Error loading secrets: {e}")
    import traceback
    traceback.print_exc()
    secrets = {}  # Fallback to empty dict

# Убедитесь, что токен существует перед созданием бота
if not secrets.get('token'):
    raise ValueError("❌ CRITICAL: 'token' is not set in config.yml!")

if not secrets.get('ggsel_bot_token'):
    print("⚠️ Warning: 'ggsel_bot_token' is not set in config.yml")

if not secrets.get('crypto_bot_token'):
    print("⚠️ Warning: 'crypto_bot_token' is not set in config.yml")

bot = Bot(token=secrets.get('token'))
# ggsel_bot = Bot(token=secrets.get('ggsel_bot_token')) if secrets.get('ggsel_bot_token') else None
cp = CryptoPay(secrets.get('crypto_bot_token')) if secrets.get('crypto_bot_token') else None
