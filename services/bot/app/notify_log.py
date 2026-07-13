"""Telegram event-log notifications (bot side).

Mirrors miniapp.backend.notify_log but uses the in-process aiogram
admin bot instance (`app.settings.admin_bot`) so we don't pay for
extra HTTP sessions in the bot process.

Silent no-op when admin_bot is None or logs_id is unset. All exceptions
are swallowed and logged at WARNING — log delivery must never block a
payment, delivery, or auth flow.
"""
from __future__ import annotations

import html
import logging

from app.settings import admin_bot, secrets

logger = logging.getLogger(__name__)


def esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def _logs_chat_id() -> int | None:
    raw = secrets.get("logs_id")
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


async def notify_log(text: str, *, parse_mode: str = "HTML") -> None:
    if admin_bot is None:
        return
    chat_id = _logs_chat_id()
    if chat_id is None:
        return
    try:
        await admin_bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            disable_web_page_preview=True,
        )
    except Exception as exc:
        logger.warning("notify_log: send failed: %s", exc)
