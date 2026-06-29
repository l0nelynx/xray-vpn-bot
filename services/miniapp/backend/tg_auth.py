import hmac
import hashlib
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException, status

from .config import get_bot_token

INIT_DATA_TTL = 24 * 3600
FUTURE_DRIFT_TOLERANCE = 60


@dataclass
class TgUser:
    tg_id: int
    username: str | None
    language_code: str | None
    auth_date: int


def _check_signature(init_data: str, bot_token: str) -> dict:
    parsed = dict(parse_qsl(init_data, strict_parsing=False))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing hash")

    data_check = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad signature")
    return parsed


async def get_tg_user(
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
) -> TgUser:
    bot_token = get_bot_token()
    if not bot_token:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "bot token not configured")

    parsed = _check_signature(x_telegram_init_data, bot_token)

    auth_date = int(parsed.get("auth_date", "0"))
    now = time.time()
    if now - auth_date > INIT_DATA_TTL:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "initData expired")
    if auth_date - now > FUTURE_DRIFT_TOLERANCE:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "initData from the future")

    user_raw = parsed.get("user")
    if not user_raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "no user")
    try:
        user = json.loads(user_raw)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "malformed user")

    if not user.get("id"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "no user id")
    if not user.get("username"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "username required")

    return TgUser(
        tg_id=int(user["id"]),
        username=user.get("username"),
        language_code=user.get("language_code"),
        auth_date=auth_date,
    )
