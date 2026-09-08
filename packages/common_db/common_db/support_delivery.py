"""Small, bounded Telegram delivery policy shared by ticket APIs."""
import asyncio
import logging

logger = logging.getLogger(__name__)


async def send_notification(client, url: str, payload: dict) -> bool:
    # Never log the URL: it contains the bot token.
    for attempt in range(3):
        try:
            response = await client.post(url, json=payload)
            body = response.json()
            if response.is_success and body.get("ok"):
                return True
            code = body.get("error_code", response.status_code)
            if code != 429 and code < 500:
                logger.warning("support notification rejected (code %s)", code)
                return False
            delay = min(max(float(body.get("parameters", {}).get("retry_after", 1)), 1), 30)
        except Exception:
            delay = 2 ** attempt
        if attempt < 2:
            await asyncio.sleep(delay)
    logger.warning("support notification failed after three attempts")
    return False
