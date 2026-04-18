"""Utility to get the language module for a specific user."""
import time

import app.database.requests as rq
from app.locale import get_lang

# TTL cache for user language — avoids DB hit on every handler call.
# language changes are rare; 60s staleness is acceptable.
_lang_cache: dict[int, tuple[str, float]] = {}
_LANG_TTL = 60.0  # seconds


async def get_user_lang(tg_id: int):
    """Get the language module for a user based on their saved preference.
    Falls back to 'ru' if language is not set."""
    now = time.monotonic()
    cached = _lang_cache.get(tg_id)
    if cached and (now - cached[1]) < _LANG_TTL:
        return get_lang(cached[0])

    language = await rq.get_user_language(tg_id)
    lang_code = language or "ru"
    _lang_cache[tg_id] = (lang_code, now)
    return get_lang(lang_code)


def invalidate_lang_cache(tg_id: int):
    """Call after set_user_language to immediately reflect the change."""
    _lang_cache.pop(tg_id, None)
