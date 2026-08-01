"""Retry and webhook idempotency for paid account delivery."""
from __future__ import annotations

import asyncio
import json

from common_db.models import Transaction, User


def _transaction(
    transaction_id: str,
    *,
    status: str,
    delivery_status: int = 0,
) -> Transaction:
    return Transaction(
        transaction_id=transaction_id,
        vless_uuid="None",
        username="user01",
        order_status=status,
        delivery_status=delivery_status,
        days_ordered=30,
        created_at="2026-08-01T10:00:00",
        user_id=1,
        purchase_source="miniapp",
    )


def test_claim_accepts_created_and_pending_but_not_terminal_states(
    session_factory, monkeypatch,
) -> None:
    import app.database.requests as requests

    monkeypatch.setattr(requests, "async_session", session_factory)

    async def run():
        async with session_factory() as session:
            session.add(User(id=1, tg_id=101, username="user01"))
            session.add_all([
                _transaction("created", status="created"),
                _transaction("pending", status="pending"),
                _transaction("confirmed", status="confirmed"),
                _transaction("delivered", status="pending", delivery_status=1),
            ])
            await session.commit()

        outcomes = {
            tx_id: await requests.claim_order_for_processing(tx_id)
            for tx_id in ("created", "pending", "confirmed", "delivered")
        }
        async with session_factory() as session:
            statuses = {
                tx_id: (await session.get(Transaction, tx_id)).order_status
                for tx_id in outcomes
            }
        return outcomes, statuses

    outcomes, statuses = asyncio.run(run())

    assert outcomes == {
        "created": True,
        "pending": True,
        "confirmed": False,
        "delivered": False,
    }
    assert statuses["created"] == "confirmed"
    assert statuses["pending"] == "confirmed"
    assert statuses["confirmed"] == "confirmed"
    assert statuses["delivered"] == "pending"


def test_account_delivery_retries_transient_failure(monkeypatch) -> None:
    import app.api.handlers as handlers
    import app.handlers.android_delivery as android_delivery

    calls = 0
    sleeps: list[int] = []

    async def claim(_transaction_id):
        return True

    async def no_alert(*_args, **_kwargs):
        return None

    async def fake_sleep(delay):
        sleeps.append(delay)

    async def deliver(**_kwargs):
        nonlocal calls
        calls += 1
        if calls < 3:
            return {
                "status": "pending",
                "message": "remnawave unavailable",
                "retryable": True,
            }
        return {"status": "success", "scenario": "extend"}

    monkeypatch.setattr(handlers.rq, "claim_order_for_processing", claim)
    monkeypatch.setattr(handlers, "send_alert", no_alert)
    monkeypatch.setattr(handlers.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(android_delivery, "deliver_android_paid", deliver)

    userdata = {
        "status": "pending",
        "transaction_id": "tx-retry",
        "payment_method": "test",
        "amount": 100,
        "user_email": None,
        "user_tg_id": 101,
        "user_username": "user01",
        "purchase_source": "miniapp",
        "tariff_slug": "sid:S1:esid:E1",
        "internal_squad_ids": ["S1"],
        "external_squad_id": "E1",
        "target_rw_id": 901,
    }

    asyncio.run(
        handlers._process_account_payment("tx-retry", userdata, 1, 30)
    )

    assert calls == 3
    assert sleeps == [2, 4]


def test_cryptopay_repeated_webhook_enqueues_pending(monkeypatch) -> None:
    import app.api.crypto_pay as crypto_pay

    body = json.dumps({
        "update_type": "invoice_paid",
        "payload": {"invoice_id": 12345},
    }).encode()

    class Request:
        headers = {"Crypto-Pay-Api-Signature": "valid"}

        async def body(self):
            return body

    class BackgroundTasks:
        def __init__(self):
            self.calls = []

        def add_task(self, function, *args):
            self.calls.append((function, args))

    async def transaction(_invoice_id):
        return {"status": "pending"}

    monkeypatch.setattr(
        crypto_pay.signatures, "verify_cryptopay_webhook",
        lambda *_args: True,
    )
    monkeypatch.setattr(crypto_pay.rq, "get_full_transaction_info", transaction)
    tasks = BackgroundTasks()

    result = asyncio.run(
        crypto_pay.cryptopay_webhook_handler(Request(), tasks)
    )

    assert result == {"ok": True}
    assert tasks.calls == [(crypto_pay.payment_process_background, ("12345",))]
