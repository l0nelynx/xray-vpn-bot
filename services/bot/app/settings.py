import copy
from pathlib import Path

import uvicorn
import yaml
from aiogram import Bot
from fastapi import FastAPI, Request
from slowapi import Limiter


def _real_client_ip(request: Request) -> str:
    """Rate-limit key on the real client IP behind the trusted edge nginx.

    The edge overwrites ``X-Real-IP`` with its ``$remote_addr``; trusting the
    socket peer instead would collapse every webhook caller into one bucket
    (the nginx container), so a flood from one provider could rate-limit
    another's callbacks. Falls back to the rightmost XFF hop, then the peer.
    """
    xri = request.headers.get("x-real-ip")
    if xri and xri.strip():
        return xri.strip()
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        hops = [p.strip() for p in fwd.split(",") if p.strip()]
        if hops:
            return hops[-1]
    return request.client.host if request.client else "unknown"


app_uvi = FastAPI()
limiter = Limiter(key_func=_real_client_ip)
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
    _yaml_secrets = load_config()
except Exception as e:
    import traceback
    traceback.print_exc()
    raise SystemExit(f"CRITICAL: failed to load config.yml — {e}") from e

from common_db.runtime_config import DualSourceConfig, set_crypto_secret

set_crypto_secret(str(_yaml_secrets.get("payments_secrets_key") or _yaml_secrets.get("dashboard_secret") or ""))
secrets = DualSourceConfig(_yaml_secrets)

# Сохраняем оригинальные значения config.yml (для config_manager)
_original_config = copy.deepcopy(_yaml_secrets)

# Убедитесь, что токен существует перед созданием бота
if not secrets.get('token'):
    raise ValueError("❌ CRITICAL: 'token' is not set in config.yml!")


bot = Bot(token=secrets.get('token'))
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
from common_db.runtime_config import payments_config_kwargs


def _payments_config() -> "_payments.PaymentsConfig":
    return _payments.PaymentsConfig(**payments_config_kwargs(secrets))


_payments.set_config_provider(_payments_config)
