"""Telegram event-log notifications.

Sends short HTML messages to the chat configured as `logs_id` via the
admin bot (`admin_bot_token`). Used for high-signal events: Android user
registration, invoice creation, subscription delivery, email verification,
Telegram-account linking.

Failure modes are intentionally swallowed and only logged at WARNING:
a Telegram outage must NEVER block a payment flow or an auth handler.
If `admin_bot_token` or `logs_id` is missing the call is a silent no-op.
"""
from __future__ import annotations

import html
import logging

import httpx

from .config import get_admin_bot_token, get_logs_id

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(5.0, connect=3.0)


def esc(value: object) -> str:
    """HTML-escape any value for safe embedding in <b>/<code> spans."""
    return html.escape(str(value), quote=False)


async def notify_log(text: str, *, parse_mode: str = "HTML") -> None:
    token = get_admin_bot_token()
    chat_id = get_logs_id()
    if not token or chat_id is None:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(url, json=payload)
        if r.status_code >= 400:
            logger.warning(
                "notify_log: telegram returned %s: %s", r.status_code, r.text[:200]
            )
    except Exception as exc:  # network, timeout, json — anything
        logger.warning("notify_log: send failed: %s", exc)
