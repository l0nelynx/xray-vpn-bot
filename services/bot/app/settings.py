import copy
from pathlib import Path

import uvicorn
import yaml
from aiogram import Bot
from aiosend import CryptoPay
from fastapi import FastAPI
from slowapi import Limiter
from slowapi.util import get_remote_address

app_uvi = FastAPI()
limiter = Limiter(key_func=get_remote_address)
app_uvi.state.limiter = limiter


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
    config = uvicorn.Config(app_uvi, host=secrets.get('uvicorn_host'), port=secrets.get('uvicorn_port'))
#                            ssl_keyfile=secrets.get('uvicorn_ssl_key'), ssl_certfile=secrets.get('uvicorn_ssl_cert'))
    server = uvicorn.Server(config)
    await server.serve()

# Загрузка конфигурации при импорте модуля
try:
    secrets = load_config()
except Exception as e:
    import traceback
    traceback.print_exc()
    raise SystemExit(f"CRITICAL: failed to load config.yml — {e}") from e

# Сохраняем оригинальные значения config.yml (для config_manager)
_original_config = copy.deepcopy(secrets)

# Убедитесь, что токен существует перед созданием бота
if not secrets.get('token'):
    raise ValueError("❌ CRITICAL: 'token' is not set in config.yml!")


bot = Bot(token=secrets.get('token'))
cp = CryptoPay(secrets.get('crypto_bot_token')) if secrets.get('crypto_bot_token') else None

# Admin bot (отдельный бот для админ-панели)
if secrets.get('admin_bot_token'):
    admin_bot = Bot(token=secrets.get('admin_bot_token'))
else:
    admin_bot = None

# Wire the shared Remnawave client to this service's settings. The module-level
# helpers in `remnawave_client.api` lazily configure the default client from
# this provider on first use (replaces the old app.api.remnawave.api shim).
import remnawave_client as _remna

_remna.set_config_provider(lambda: {
    "base_url": secrets.get("remnawave_url"),
    "token": secrets.get("remnawave_token"),
    "free_squad_id": secrets.get("rw_free_id"),
})

# Wire the shared payments package to this service's settings (replaces the
# per-gateway invoice-creation classes that used to live in app/api/*.py).
import payments as _payments


def _payments_config() -> "_payments.PaymentsConfig":
    try:
        platega_method = int(secrets.get("platega_payment_method", 2))
    except (TypeError, ValueError):
        platega_method = 2
    return _payments.PaymentsConfig(
        apay_id=secrets.get("apay_id"),
        apay_secret=secrets.get("apay_secret", ""),
        apay_api_url=secrets.get("apay_api_url", ""),
        crypto_bot_token=secrets.get("crypto_bot_token", ""),
        crystal_login=secrets.get("crystal_login", ""),
        crystal_secret=secrets.get("crystal_secret", ""),
        crystal_salt=secrets.get("crystal_salt", ""),
        crystal_webhook=secrets.get("crystal_webhook", ""),
        platega_merchant_id=secrets.get("platega_merchant_id", "") or "",
        platega_api_key=secrets.get("platega_api_key", "") or "",
        platega_url=secrets.get("platega_url", "https://app.platega.io"),
        platega_payment_method=platega_method,
    )


_payments.set_config_provider(_payments_config)
