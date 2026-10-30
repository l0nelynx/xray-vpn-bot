from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from payments import config
from payments.base import InvoiceRequest, PaymentError
from payments.config import PaymentsConfig
from payments.platega import PlategaProvider


class _Response:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def json(self):
        return {"transactionId": "gateway-id", "redirect": "https://pay.platega.io/test"}


class _Session:
    def __init__(self):
        self.calls = []

    def post(self, url, *, json, headers):
        self.calls.append((url, json, headers))
        return _Response()


@pytest.fixture
def session(monkeypatch):
    session = _Session()
    monkeypatch.setattr(config, "_provider", lambda: PaymentsConfig(
        platega_merchant_id="merchant", platega_api_key="secret",
        platega_url="https://app.platega.io", platega_payment_method=2,
    ))
    monkeypatch.setattr(
        PlategaProvider, "_get_session", classmethod(lambda cls: session)
    )
    return session


def _request(**overrides):
    return replace(InvoiceRequest(
        transaction_id="order-1", amount=500, currency="RUB", days=30,
        user_tg_id=5512345678, user_id=42,
    ), **overrides)


@pytest.mark.parametrize(("email", "tg_id", "expected"), [
    (None, 5512345678, "5512345678@telegram.org"),
    ("buyer@gmail.com", -42, "buyer@gmail.com"),
    ("Buyer+vpn@gmail.com", 5512345678, "Buyer+vpn@gmail.com"),
])
def test_customer_metadata_is_stable_across_orders(session, email, tg_id, expected):
    request = _request(user_email=email, user_tg_id=tg_id, description="СБП #1")
    provider = PlategaProvider()
    invoice = asyncio.run(provider.create_invoice(request))
    asyncio.run(provider.create_invoice(replace(request, transaction_id="order-2")))

    for url, body, headers in session.calls:
        assert url == "https://app.platega.io/v2/transaction/process"
        assert body["metadata"] == {"userId": "42", "user_email": expected}
        assert body["description"] == "Оплата подписки клиенту №42"
        assert body["paymentMethod"] == 2
        assert body["paymentDetails"] == {"amount": 500.0, "currency": "RUB"}
        assert headers["X-MerchantId"] == "merchant"
    assert [body["payload"] for _, body, _ in session.calls] == ["order-1", "order-2"]
    assert invoice.invoice_id == "gateway-id"
    assert invoice.url == "https://pay.platega.io/test"


@pytest.mark.parametrize("overrides", [
    {"user_id": None},
    {"user_id": 0},
    {"user_id": -42},
    {"user_tg_id": -42},
    {"user_tg_id": 0},
    {"user_email": "buyer"},
    {"user_email": "buyer@@gmail.com"},
    {"user_email": " buyer@gmail.com"},
    {"user_email": "buyer@gmail.com\n"},
])
def test_invalid_identity_is_rejected_before_http_request(session, overrides):
    with pytest.raises(PaymentError):
        asyncio.run(PlategaProvider().create_invoice(_request(**overrides)))
    assert session.calls == []
