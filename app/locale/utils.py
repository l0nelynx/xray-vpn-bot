"""Utility to get the language module for a specific user."""
import app.database.requests as rq
from app.locale import get_lang


async def get_user_lang(tg_id: int):
    """Get the language module for a user based on their saved preference.
    Falls back to 'ru' if language is not set."""
    language = await rq.get_user_language(tg_id)
    return get_lang(language or "ru")
