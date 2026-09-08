import asyncio
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from common_db.support_delivery import send_notification, ticket_keyboard
from common_db.support_workflow import can_reopen


def test_delivery_retries_transient_but_not_permanent_errors(monkeypatch):
    monkeypatch.setattr("common_db.support_delivery.asyncio.sleep", AsyncMock())
    failure = SimpleNamespace(is_success=False, status_code=500, json=lambda: {"ok": False, "error_code": 500})
    success = SimpleNamespace(is_success=True, status_code=200, json=lambda: {"ok": True})
    client = SimpleNamespace(post=AsyncMock(side_effect=[failure, success]))
    assert asyncio.run(send_notification(client, "https://example.invalid", {}))
    assert client.post.await_count == 2
    denied = SimpleNamespace(is_success=False, status_code=403, json=lambda: {"ok": False, "error_code": 403})
    client.post = AsyncMock(return_value=denied)
    assert not asyncio.run(send_notification(client, "https://example.invalid", {}))
    assert client.post.await_count == 1


def test_links_are_scoped_to_ticket():
    config = {"miniapp_url": "https://vpn.example/bot/miniapp/"}
    user = ticket_keyboard(config, 123)["reply_markup"]["inline_keyboard"][0][0]
    admin = ticket_keyboard(config, 123, admin=True)["reply_markup"]["inline_keyboard"][0][0]
    assert admin["text"] == "Open ticket"
    assert user["text"] == "Открыть обращение"
    assert user["web_app"]["url"] == "https://vpn.example/bot/miniapp/support/123"
    assert admin["url"] == "https://vpn.example/bot/dashboard/support?ticket=123"
    assert ticket_keyboard({}, 123) == {}


def test_reopen_window_expires():
    ticket = SimpleNamespace(status="closed", closed_at=(datetime.now(timezone.utc) - timedelta(days=8)).isoformat())
    assert not can_reopen(ticket)
    ticket.closed_at = datetime.now(timezone.utc).isoformat()
    assert can_reopen(ticket)
