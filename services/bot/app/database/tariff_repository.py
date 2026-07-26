"""Version-cached Telegram menu reads.

The historical module name is retained for import compatibility; tariffs now
come exclusively from ``webapp_menu_nodes``.
"""
import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.models import (
    CacheVersion,
    MenuScreen,
    async_session,
)

logger = logging.getLogger(__name__)
_POLL_INTERVAL = 5
_menu_cache: dict = {}
_known_version = -1
_last_poll_ts = 0.0


async def _check_version() -> None:
    global _known_version, _last_poll_ts
    now = time.time()
    if now - _last_poll_ts < _POLL_INTERVAL:
        return
    _last_poll_ts = now
    async with async_session() as session:
        row = await session.get(CacheVersion, 1)
        version = row.version if row else 0
    if version != _known_version:
        _menu_cache.clear()
        _known_version = version


def invalidate_cache() -> None:
    global _known_version
    _menu_cache.clear()
    _known_version = -1


async def _ensure_menu_cache() -> None:
    try:
        await _check_version()
    except Exception:
        logger.exception("Telegram menu cache version check failed")
        return
    if _menu_cache:
        return
    try:
        async with async_session() as session:
            result = await session.execute(
                select(MenuScreen)
                .options(selectinload(MenuScreen.buttons))
                .where(MenuScreen.is_active == True)  # noqa: E712
            )
            for screen in result.scalars().all():
                buttons = sorted(
                    (button for button in screen.buttons if button.is_active),
                    key=lambda button: (button.row, button.col, button.sort_order),
                )
                _menu_cache[screen.slug] = {
                    "message_text_ru": screen.message_text_ru,
                    "message_text_en": screen.message_text_en,
                    "buttons": [
                        {
                            "text_ru": button.text_ru,
                            "text_en": button.text_en,
                            "callback_data": button.callback_data,
                            "url": button.url,
                            "row": button.row,
                            "col": button.col,
                            "button_type": button.button_type,
                        }
                        for button in buttons
                    ],
                }
    except Exception:
        logger.exception("Telegram menu database read failed; using fallback")


async def get_screen_buttons(screen_slug: str, lang_code: str = "ru") -> list[dict] | None:
    await _ensure_menu_cache()
    screen = _menu_cache.get(screen_slug)
    if screen is None:
        return None
    text_key = "text_en" if lang_code == "en" else "text_ru"
    fallback_key = "text_ru" if text_key == "text_en" else "text_en"
    return [
        {
            "text": button.get(text_key) or button.get(fallback_key) or "—",
            "callback_data": button["callback_data"],
            "url": button["url"],
            "row": button["row"],
            "col": button["col"],
            "button_type": button["button_type"],
        }
        for button in screen["buttons"]
    ]


async def get_screen_text(screen_slug: str, lang_code: str = "ru") -> str | None:
    await _ensure_menu_cache()
    screen = _menu_cache.get(screen_slug)
    if screen is None:
        return None
    if lang_code == "en":
        return screen.get("message_text_en") or screen.get("message_text_ru")
    return screen.get("message_text_ru") or screen.get("message_text_en")
