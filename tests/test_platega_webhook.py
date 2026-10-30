"""Platega review callbacks must not duplicate subscription delivery."""
from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from common_db.models import Transaction, User


@pytest.fixture
def webhook(monkeypatch):
    import app.api.platega as platega

    monkeypatch.setattr(platega, "secrets", {
        "platega_merchant_id": "merchant", "platega_api_key": "secret",
    })
    app = FastAPI()
    app.post("/bot/platega_webhook")(platega.payment_webhook_handler)
    client = TestClient(app)

    def post(status, *, secret="secret"):
        return client.post("/bot/platega_webhook", headers={
            "X-MerchantId": "merchant", "X-Secret": secret,
        }, json={
            "id": "provider-id", "amount": 1500.25, "currency": "RUB",
            "status": status, "paymentMethod": 2, "payload": "local-id",
        })

    return platega, post


def test_disputed_is_acknowledged_and_logged_without_delivery(webhook, monkeypatch, caplog):
    platega, post = webhook
    process = AsyncMock()
    monkeypatch.setattr(platega, "payment_process_background", process)

    with caplog.at_level(logging.WARNING, logger=platega.__name__):
        for _ in range(2):
            response = post("DISPUTED")
            assert response.status_code == 200
            assert response.json() == {"status": "received"}

    process.assert_not_awaited()
    assert len(caplog.records) == 2
    assert all("DISPUTED: provider-id" in record.message for record in caplog.records)


def test_disputed_requires_webhook_authentication(webhook, monkeypatch, caplog):
    platega, post = webhook
    process = AsyncMock()
    monkeypatch.setattr(platega, "payment_process_background", process)

    response = post("DISPUTED", secret="invalid")

    assert response.json() == {"status": "error", "message": "unauthorized"}
    process.assert_not_awaited()
    assert "DISPUTED: provider-id" not in caplog.text


@pytest.mark.parametrize("resolution", ["CONFIRMED", "CHARGEBACKED"])
def test_review_cycles_preserve_delivery_state_and_do_not_deliver_twice(
    webhook, session_factory, monkeypatch, resolution,
):
    import app.api.handlers as handlers
    import app.database.requests as requests
    import app.handlers.android_delivery as android_delivery

    _, post = webhook
    monkeypatch.setattr(requests, "async_session", session_factory)
    monkeypatch.setattr(handlers, "send_alert", AsyncMock())

    async def seed():
        async with session_factory() as session:
            session.add(User(id=1, tg_id=101, username="buyer"))
            session.add(Transaction(
                transaction_id="local-id", provider_invoice_id="provider-id",
                vless_uuid="None", order_status="created", delivery_status=0,
                days_ordered=30, created_at="2026-10-30T10:00:00", user_id=1,
                payment_method="PLATEGA", amount=1500.25, purchase_source="miniapp",
            ))
            await session.commit()

    async def deliver(**kwargs):
        # Stand in for the external subscription service, retaining real DB
        # lookup, atomic claim and delivery marker for repeat-webhook checks.
        async with session_factory() as session:
            tx = await session.get(Transaction, kwargs["transaction_id"])
            tx.delivery_status = 1
            await session.commit()
        return {"status": "success", "scenario": "extend"}

    delivery = AsyncMock(side_effect=deliver)
    monkeypatch.setattr(android_delivery, "deliver_android_paid", delivery)
    asyncio.run(seed())

    async def snapshot():
        async with session_factory() as session:
            tx = await session.get(Transaction, "local-id")
            return tx.order_status, tx.delivery_status, tx.expire_date

    assert post("CONFIRMED").json() == {"status": "success"}
    initial = asyncio.run(snapshot())
    assert initial[:2] == ("confirmed", 1)
    # A review can recur for the same payment after a previous release.
    for status in ("DISPUTED", "DISPUTED", "CONFIRMED", "DISPUTED", resolution):
        assert post(status).status_code == 200
        assert asyncio.run(snapshot()) == initial

    delivery.assert_awaited_once()
    assert delivery.call_args.kwargs["transaction_id"] == "local-id"
