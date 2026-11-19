"""Exercise the web checkout, verified payment claim and GA4 worker together."""
import asyncio
import inspect
import logging
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from sqlalchemy import text
from starlette.requests import Request

from common_db.models import Transaction, User, WebAnalyticsPurchase
from miniapp.backend.web import analytics, web_router
from payments.base import Invoice

CONTEXT = {"client_id": "123.456", "session_id": "1234567890"}


def transaction(tx_id="tx", **values):
    fields = dict(transaction_id=tx_id, user_id=1, purchase_source="web",
                  order_status="created", delivery_status=0, vless_uuid="None",
                  amount=199, currency="RUB", payment_method="PLATEGA",
                  squad_id="s1", external_squad_id="e1", days_ordered=30)
    return Transaction(**{**fields, **values})


@pytest.mark.parametrize("context", [None, {"client_id": "invalid"}, {**CONTEXT, "session_id": "0"}])
def test_unavailable_analytics_does_not_reject_checkout(context):
    assert web_router.WebInvoiceRequest(node_id=1, analytics=context).analytics is None


def test_web_invoice_confirmation_and_ga4_retry(session_factory, monkeypatch, caplog):
    from app.api import handlers
    from app.database import requests
    from app.handlers import android_delivery

    secret = "integration-test-secret"
    monkeypatch.setattr(analytics, "settings", lambda: ("G-TEST123", secret))
    monkeypatch.setattr(requests, "async_session", session_factory)
    monkeypatch.setattr(web_router, "async_session", session_factory)
    monkeypatch.setattr(web_router, "notify_log", AsyncMock())
    monkeypatch.setattr(web_router, "_purchase_target_rw_id", AsyncMock(return_value=100))
    monkeypatch.setattr(web_router, "_load_node", AsyncMock(return_value={}))
    invoice = dict(provider="platega", method="2", amount=199, currency="RUB", days=30,
                   squad_id="s1", external_squad_id="e1", internal_squad_ids=["s1"],
                   traffic_limit_bytes=0, traffic_limit_strategy="NO_RESET",
                   remnawave_description=None, remnawave_tag=None)
    monkeypatch.setattr(web_router, "_node_payload", lambda *a, **kw: invoice)
    monkeypatch.setattr(web_router, "create_invoice", AsyncMock(return_value=Invoice(
        "platega", "gateway-id", "https://example.test/pay", 199, "RUB",
    )))
    monkeypatch.setattr(handlers, "send_alert", AsyncMock())
    deliver = AsyncMock(return_value={"status": "success", "scenario": "extend"})
    monkeypatch.setattr(android_delivery, "deliver_android_paid", deliver)
    caplog.set_level(logging.DEBUG)
    received = []

    async def collect(request):
        assert request.query == {"measurement_id": "G-TEST123", "api_secret": secret}
        # A second worker polling during the HTTP call cannot claim this row.
        assert await analytics.send_batch(session_factory, Mock(), "G-TEST123", secret) == 0
        received.append(await request.json())
        return web.Response(status=503 if len(received) == 1 else 204)

    async def run():
        async with session_factory() as session:
            session.add(User(id=1, tg_id=101))
            await session.commit()
        user = SimpleNamespace(id=1, email=None, tg_id=101)
        body = web_router.WebInvoiceRequest.model_validate({
            "node_id": 1, "analytics": {**CONTEXT, "currency": "EUR", "value": 0.01},
            "amount": 1, "transaction_id": "from-browser",
        })
        response = await inspect.unwrap(web_router.web_invoice)(
            body=body, request=Request({"type": "http", "headers": []}), user=user,
        )
        tx_id = response.transaction_id
        app = web.Application()
        app.router.add_post("/mp/collect", collect)
        async with TestServer(app) as server, aiohttp.ClientSession() as client:
            monkeypatch.setattr(analytics, "COLLECT_URL", str(server.make_url("/mp/collect")))
            async def send():
                return await analytics.send_batch(session_factory, client, "G-TEST123", secret)
            assert await send() == 0 and received == []
            await handlers.payment_process_background("gateway-id")
            deliver.assert_awaited_once()
            assert await send() == 0
            async with session_factory() as session:
                row = await session.get(WebAnalyticsPurchase, tx_id)
                tx = await session.get(Transaction, tx_id)
                assert row.last_error == "http_503" and row.sent_at is None
                assert row.next_attempt_at > time.time()
                assert tx.order_status == "confirmed" and row.confirmed_at == tx.payment_confirmed_at
                timestamp = int(tx.payment_confirmed_at * 1_000_000)
                row.next_attempt_at = 0
                await session.commit()
            await handlers.payment_process_background("gateway-id")
            assert await send() == 1
            await handlers.payment_process_background("gateway-id")
            assert await send() == 0
            deliver.assert_awaited_once()
        assert len(received) == 2 and received[0] == received[1]
        payload = received[1]
        assert payload["client_id"] == "123.456" and payload["timestamp_micros"] == timestamp
        event, = payload["events"]
        assert event == {"name": "purchase", "params": {
            "transaction_id": tx_id, "session_id": 1234567890, "currency": "RUB", "value": 199,
            "payment_provider": "platega", "payment_type": "PLATEGA", "purchase_kind": "renewal",
            "engagement_time_msec": 1, "items": [{
                "item_id": "sid:s1:esid:e1:30", "item_name": "sid:s1:esid:e1",
                "item_variant": "30", "quantity": 1, "price": 199,
            }],
        }}
    # The local collector is an HTTP server. Suppress its inbound access log,
    # independently of the application's outbound and payment logs under test.
    caplog.set_level(logging.WARNING, logger="aiohttp.access")
    asyncio.run(run())
    assert secret not in caplog.text


def test_outbox_failure_does_not_break_invoice_or_confirmation(session_factory, monkeypatch):
    from app.database import requests
    monkeypatch.setattr(analytics, "settings", lambda: ("G-TEST123", "secret"))
    monkeypatch.setattr(requests, "async_session", session_factory)
    async def run():
        async with session_factory() as session:
            await session.execute(text("DROP TABLE web_analytics_purchases"))
            session.add(User(id=1, tg_id=101))
            session.add(transaction())
            await analytics.enqueue(session, analytics.AnalyticsContext(**CONTEXT), "tx", "platega")
            await session.commit()
        assert await requests.claim_order_for_processing("tx")
        async with session_factory() as session:
            tx = await session.get(Transaction, "tx")
            confirmed_at = tx.payment_confirmed_at
            tx.order_status = "pending"
            await session.commit()
        assert await requests.claim_order_for_processing("tx")
        async with session_factory() as session:
            assert confirmed_at and (await session.get(Transaction, "tx")).payment_confirmed_at == confirmed_at
    asyncio.run(run())


def test_expired_confirmation_skipped(session_factory):
    async def run():
        async with session_factory() as session:
            session.add(User(id=1, tg_id=101))
            session.add(transaction(payment_confirmed_at=time.time() - 72 * 3600))
            await session.flush()
            session.add(WebAnalyticsPurchase(transaction_id="tx", payload=CONTEXT))
            await session.commit()
        client = Mock()
        assert await analytics.send_batch(session_factory, client, "G-TEST123", "secret") == 0
        client.post.assert_not_called()
        async with session_factory() as session:
            assert (await session.get(WebAnalyticsPurchase, "tx")).last_error == "expired"
    asyncio.run(run())


def test_crypto_amount_preserves_settlement_asset():
    tx = transaction(currency="USDT", amount=9.99)
    row = WebAnalyticsPurchase(payload={**CONTEXT, "payment_provider": "crypto"}, confirmed_at=time.time())
    params = analytics.purchase_payload(row, tx)["events"][0]["params"]
    assert params["payment_asset"] == "USDT" and params["payment_amount"] == 9.99
    assert "currency" not in params and "value" not in params


def test_network_failure_does_not_expose_secret(session_factory, caplog):
    secret = "private-ga4-secret"
    client = Mock()
    client.post.side_effect = aiohttp.ClientConnectionError(f"connection to ?api_secret={secret} failed")
    async def run():
        async with session_factory.begin() as session:
            session.add(User(id=1, tg_id=101))
            session.add(transaction(payment_confirmed_at=time.time()))
            await session.flush()
            session.add(WebAnalyticsPurchase(transaction_id="tx", payload={**CONTEXT, "payment_provider": "platega"}))
        assert await analytics.send_batch(session_factory, client, "G-TEST123", secret) == 0
        async with session_factory() as session:
            row = await session.get(WebAnalyticsPurchase, "tx")
            assert row.last_error == "network_error" and row.sent_at is None
    asyncio.run(run())
    assert secret not in caplog.text
