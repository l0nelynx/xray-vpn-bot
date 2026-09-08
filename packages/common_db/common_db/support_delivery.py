"""Small, bounded Telegram delivery policy shared by ticket APIs."""
import asyncio
import logging
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger(__name__)


def ticket_keyboard(config, ticket_id, *, admin=False):
    base = config.get("dashboard_url" if admin else "miniapp_url") or ""
    if admin and not base and config.get("miniapp_url"):
        parsed = urlsplit(config.get("miniapp_url"))
        base = urlunsplit((parsed.scheme, parsed.netloc, "/bot/dashboard", "", ""))
    if not base.startswith("https://"):
        return {}
    parsed = urlsplit(base)
    path = parsed.path.rstrip("/") + ("/support" if admin else f"/support/{ticket_id}")
    url = urlunsplit((parsed.scheme, parsed.netloc, path, f"ticket={ticket_id}" if admin else "", ""))
    button = {"text": "Open ticket" if admin else "Открыть обращение", **({"url": url} if admin else {"web_app": {"url": url}})}
    return {"reply_markup": {"inline_keyboard": [[button]]}}


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
