"""Ownership and state contract for MiniApp transaction polling."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from common_db.models import Transaction, User


@dataclass
class _FakeTg:
    tg_id: int = 55
    username: str | None = "owner"


@pytest.fixture
def payment_status_app(with_app_db, monkeypatch):
    import miniapp.backend.routers.payments as payments

    monkeypatch.setattr(payments, "async_session", with_app_db)
    app = FastAPI()
    app.include_router(payments.router)

    async def override_tg():
        return _FakeTg()

    app.dependency_overrides[payments.get_tg_user] = override_tg

    async def seed():
        async with with_app_db() as session:
            session.add_all([User(id=1, tg_id=55), User(id=2, tg_id=66)])
            for tx_id, order_status, delivery_status, user_id in [
                ("awaiting", "created", 0, 1),
                ("processing", "confirmed", 0, 1),
                ("succeeded", "confirmed", 1, 1),
                ("failed", "failed", 0, 1),
                ("foreign", "confirmed", 1, 2),
            ]:
                session.add(Transaction(
                    transaction_id=tx_id,
                    vless_uuid="None",
                    order_status=order_status,
                    delivery_status=delivery_status,
                    days_ordered=30,
                    user_id=user_id,
                ))
            await session.commit()

    asyncio.run(seed())
    return app


@pytest.mark.parametrize(
    ("transaction_id", "expected"),
    [
        ("awaiting", "awaiting_payment"),
        ("processing", "processing"),
        ("succeeded", "succeeded"),
        ("failed", "failed"),
    ],
)
def test_owner_sees_normalized_transaction_state(
    payment_status_app, transaction_id, expected,
):
    response = TestClient(payment_status_app).get(
        f"/api/payments/transactions/{transaction_id}"
    )

    assert response.status_code == 200
    assert response.json()["state"] == expected


def test_foreign_transaction_is_not_disclosed(payment_status_app):
    response = TestClient(payment_status_app).get(
        "/api/payments/transactions/foreign"
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "transaction_not_found"
