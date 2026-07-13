import logging

import httpx

from .config import get_bot_token, get_news_id

logger = logging.getLogger(__name__)

_OK_STATUSES = {"member", "administrator", "creator"}


async def is_user_subscribed_to_news(user_id: int) -> bool:
    """Check if a user is a member of the configured news channel."""
    bot_token = get_bot_token()
    chat_id = get_news_id()
    if not bot_token or chat_id is None:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/getChatMember"
    params = {"chat_id": chat_id, "user_id": user_id}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, params=params)
        data = r.json()
        if not data.get("ok"):
            return False
        status = (data.get("result") or {}).get("status")
        return status in _OK_STATUSES
    except Exception as e:
        logger.error("getChatMember failed for %s: %s", user_id, e)
        return False
