"""Shared Telegram Bot API helpers for dashboard services."""

from __future__ import annotations

import json
from urllib.parse import quote

import httpx

from .config import get_bot_token


def tg_url(method: str) -> str:
    return f"https://api.telegram.org/bot{get_bot_token()}/{method}"


def tg_bot_open_url(username: str) -> str:
    """Deep link that re-triggers /start when opened from an existing bot chat."""
    return f"https://t.me/{username}?start="


def tg_bot_deeplink(username: str, start_payload: str) -> str:
    """Deep link that opens the bot with a /start payload (e.g. referral code)."""
    return f"https://t.me/{username}?start={start_payload}"


def tg_share_url(url: str, text: str = "") -> str:
    """Telegram share sheet URL prefilled with link + message."""
    return (
        "https://t.me/share/url?url="
        + quote(url, safe="")
        + "&text="
        + quote(text or "", safe="")
    )


async def tg_send(chat_id: int, text: str, reply_markup: dict | None = None) -> bool:
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(tg_url("sendMessage"), json=payload)
            return r.status_code == 200
    except Exception:
        return False


async def tg_bot_username() -> str:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(tg_url("getMe"))
        if r.status_code == 200:
            return r.json().get("result", {}).get("username", "") or ""
    except Exception:
        pass
    return ""
