from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from common_db.models import Transaction, User


def _signed(payload, secret="secret"):
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).replace("/", "\\/")
    signature = hashlib.md5(base64.b64encode(raw.encode()) + secret.encode()).hexdigest()
    return (raw[:-1] + ',"sign":"' + signature + '"}').encode()


@pytest.fixture
def webhook(monkeypatch):
    import app.api.heleket as module

    monkeypatch.setattr(module, "secrets", {"heleket_api_key": "secret"})
    app = FastAPI()
    app.post("/bot/heleket_webhook")(module.payment_webhook_handler)
    client = TestClient(app)

    def post(status="paid", *, secret="secret", **changes):
        return client.post("/bot/heleket_webhook", content=_signed({
            "type": "payment", "uuid": "provider-id", "order_id": "local-id",
            "amount": "12.34000000", "currency": "USD", "status": status,
            "additional_data": "Тариф / месяц", **changes,
        }, secret), headers={"Content-Type": "application/json"})

    lookup = AsyncMock(return_value={
        "transaction_id": "local-id", "provider_invoice_id": "provider-id",
        "payment_method": "HELEKET", "amount": 12.34,
    })
    lookup.original_lookup = module.rq.get_full_transaction_info
    monkeypatch.setattr(module.rq, "get_full_transaction_info", lookup)
    process = AsyncMock()
    monkeypatch.setattr(module, "payment_process_background", process)
    return module, post, lookup, process


@pytest.mark.parametrize("status", ["paid", "paid_over"])
def test_paid_webhook_delivers_by_local_order_id(webhook, status):
    _, post, lookup, process = webhook
    assert post(status).json() == {"ok": True}
    lookup.assert_awaited_once_with("local-id")
    process.assert_awaited_once_with("local-id")


@pytest.mark.parametrize("status", [
    "check", "confirm_check", "wrong_amount", "fail", "cancel", "system_fail",
    "refund_process", "refund_fail", "refund_paid", "locked", "unknown",
])
def test_nonpaid_states_never_deliver(webhook, status):
    _, post, lookup, process = webhook
    assert post(status).json() == {"ok": True, "skipped": True}
    lookup.assert_not_awaited()
    process.assert_not_awaited()


@pytest.mark.parametrize("event_type", ["wallet", "payout"])
def test_other_event_types_never_deliver(webhook, event_type):
    _, post, lookup, process = webhook
    assert post(type=event_type).json() == {"ok": True, "skipped": True}
    lookup.assert_not_awaited()
    process.assert_not_awaited()


def test_invalid_signature_or_missing_credentials_never_deliver(webhook, monkeypatch):
    module, post, lookup, process = webhook
    assert post(secret="wrong").status_code == 401
    monkeypatch.setattr(module, "secrets", {})
    assert post().status_code == 401
    lookup.assert_not_awaited()
    process.assert_not_awaited()


@pytest.mark.parametrize("changes", [
    {"order_id": ""}, {"uuid": None}, {"order_id": ["local-id"]},
    {"uuid": "another-id"}, {"currency": "RUB"}, {"amount": "12.33"},
    {"amount": "NaN"}, {"amount": "bad"},
])
def test_invalid_invoice_data_never_delivers(webhook, changes):
    _, post, _, process = webhook
    assert post(**changes).status_code == 400
    process.assert_not_awaited()


def test_foreign_provider_and_provider_id_alias_do_not_deliver(webhook):
    _, post, lookup, process = webhook
    lookup.return_value["payment_method"] = "PLATEGA"
    assert post().status_code == 400
    lookup.return_value["payment_method"] = "HELEKET"
    lookup.return_value["transaction_id"] = "different-local-id"
    assert post().status_code == 400
    process.assert_not_awaited()


def test_callback_before_transaction_commit_can_retry(webhook):
    _, post, lookup, process = webhook
    tx = lookup.return_value
    lookup.return_value = None
    assert post().status_code == 404
    process.assert_not_awaited()
    lookup.return_value = tx
    assert post().status_code == 200
    process.assert_awaited_once_with("local-id")


def test_repeated_paid_events_deliver_once(webhook, session_factory, monkeypatch):
    import app.api.handlers as handlers
    import app.database.requests as requests
    import app.handlers.android_delivery as android_delivery

    module, post, lookup_mock, _ = webhook
    # Use the real payment lookup and delivery processor with an isolated DB.
    monkeypatch.setattr(requests, "get_full_transaction_info", lookup_mock.original_lookup)
    monkeypatch.setattr(requests, "async_session", session_factory)
    monkeypatch.setattr(module, "payment_process_background", handlers.payment_process_background)
    monkeypatch.setattr(handlers, "send_alert", AsyncMock())

    async def seed():
        async with session_factory() as session:
            session.add(User(id=1, tg_id=101, username="buyer"))
            session.add(Transaction(
                transaction_id="local-id", provider_invoice_id="provider-id", user_id=1,
                vless_uuid="None", order_status="created", delivery_status=0,
                days_ordered=30, created_at="2026-10-31T10:00:00",
                payment_method="HELEKET", amount=12.34, purchase_source="miniapp",
            ))
            await session.commit()

    async def deliver(**kwargs):
        async with session_factory() as session:
            tx = await session.get(Transaction, kwargs["transaction_id"])
            tx.delivery_status = 1
            await session.commit()
        return {"status": "success", "scenario": "extend"}

    delivery = AsyncMock(side_effect=deliver)
    monkeypatch.setattr(android_delivery, "deliver_android_paid", delivery)
    asyncio.run(seed())
    for status in ("paid", "paid", "paid_over", "paid"):
        assert post(status).json() == {"ok": True}
    delivery.assert_awaited_once()
    assert delivery.call_args.kwargs["transaction_id"] == "local-id"
