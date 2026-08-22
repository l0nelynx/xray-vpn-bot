"""Regression: miniapp auth must accept Telegram users without @username."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException

from services.miniapp.backend import tg_auth
from subscription_delivery import build_remnawave_username

BOT_TOKEN = "123456:ABC-DEF_test_token"


def _sign_init_data(user: dict, *, auth_date: int | None = None) -> str:
    fields = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "user": json.dumps(user, separators=(",", ":")),
    }
    data_check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def test_get_tg_user_accepts_missing_username(monkeypatch):
    monkeypatch.setattr(tg_auth, "get_bot_token", lambda: BOT_TOKEN)
    init_data = _sign_init_data({"id": 4242, "language_code": "ru"})

    user = asyncio.run(tg_auth.get_tg_user(x_telegram_init_data=init_data))

    assert user.tg_id == 4242
    assert user.username is None
    assert user.language_code == "ru"


def test_get_tg_user_accepts_empty_username(monkeypatch):
    monkeypatch.setattr(tg_auth, "get_bot_token", lambda: BOT_TOKEN)
    init_data = _sign_init_data({"id": 77, "username": ""})

    user = asyncio.run(tg_auth.get_tg_user(x_telegram_init_data=init_data))

    assert user.tg_id == 77
    assert user.username is None


def test_get_tg_user_still_requires_user_id(monkeypatch):
    monkeypatch.setattr(tg_auth, "get_bot_token", lambda: BOT_TOKEN)
    init_data = _sign_init_data({"username": "alice"})

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(tg_auth.get_tg_user(x_telegram_init_data=init_data))
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "no user id"


def test_remnawave_username_fallback_without_telegram_handle():
    assert build_remnawave_username(None, 1842) == "user_1842"
    assert build_remnawave_username("", 1842) == "user_1842"
    assert build_remnawave_username(None, 1842, 1) == "user_1842_1"
