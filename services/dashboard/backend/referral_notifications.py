"""Distinguish explicit Telegram rejection from an ambiguous network result."""
import httpx
from .telegram import tg_url


async def send_referral_notice(tg_id, message):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(tg_url("sendMessage"), json={
                "chat_id": tg_id, "text": message, "parse_mode": "HTML",
            })
        data = response.json()
    except (httpx.HTTPError, ValueError):
        return "unknown", "Нет достоверного ответа Telegram; автоматический повтор отключён"
    if data.get("ok") is True:
        return "sent", None
    if data.get("ok") is False and response.status_code < 500:
        return "failed", str(data.get("description", "Telegram rejected request"))[:200]
    return "unknown", "Неоднозначный ответ Telegram"
