from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import threading
from dataclasses import replace

import pytest
from heleket_sdk import RequestsTransport, TransportResponse

from payments import config, create_invoice, validate_provider_invoice
from payments.base import InvoiceRequest, PaymentError
from payments.config import PaymentsConfig
from payments.signatures import verify_heleket_webhook


def _request(**overrides):
    return replace(InvoiceRequest(
        transaction_id="local-id", amount=12.34, currency="USD", days=30,
        user_tg_id=101, user_id=1, user_email="buyer@example.com",
    ), **overrides)


@pytest.fixture
def transport(monkeypatch):
    calls = []
    response = {"state": 0, "result": {
        "uuid": "provider-id", "url": "https://pay.heleket.com/pay/provider-id",
    }}

    def round_trip(self, method, url, headers, body, timeout):
        calls.append((method, url, headers, body, timeout, threading.get_ident()))
        return TransportResponse(status_code=200, body=json.dumps(response))

    monkeypatch.setattr(RequestsTransport, "round_trip", round_trip)
    monkeypatch.setattr(config, "_provider", lambda: PaymentsConfig(
        heleket_merchant_id="merchant", heleket_api_key="secret",
        heleket_webhook="https://vpn.example/bot/heleket_webhook",
    ))
    return calls, response


def test_real_sdk_signs_invoice_and_runs_outside_event_loop(transport):
    calls, _ = transport
    loop_thread = threading.get_ident()
    invoice = asyncio.run(create_invoice("heleket", _request()))
    method, url, headers, raw, timeout, worker_thread = calls[0]
    assert method == "POST" and url == "https://api.heleket.com/v1/payment"
    assert headers["merchant"] == "merchant"
    assert headers["sign"] == hashlib.md5(base64.b64encode(raw.encode()) + b"secret").hexdigest()
    assert timeout == 30 and worker_thread != loop_thread
    assert json.loads(raw) == {
        "amount": "12.34", "currency": "USD", "order_id": "local-id",
        "url_callback": "https://vpn.example/bot/heleket_webhook",
        "lifetime": 3600, "is_payment_multiple": False,
        "accuracy_payment_percent": "0", "payer_email": "buyer@example.com",
    }
    assert invoice.invoice_id == "provider-id"
    assert invoice.url == "https://pay.heleket.com/pay/provider-id"
    assert invoice.amount == 12.34 and invoice.currency == "USD"


@pytest.mark.parametrize("missing", ["heleket_merchant_id", "heleket_api_key", "heleket_webhook"])
def test_missing_settings_only_block_checkout(transport, monkeypatch, missing):
    calls, _ = transport
    cfg = replace(config.get_config(), **{missing: ""})
    monkeypatch.setattr(config, "_provider", lambda: cfg)
    with pytest.raises(PaymentError, match="not configured"):
        asyncio.run(create_invoice("heleket", _request()))
    assert not calls


def test_credentials_are_read_again_after_rotation(transport, monkeypatch):
    calls, _ = transport
    original = config.get_config()
    current = [original]
    monkeypatch.setattr(config, "_provider", lambda: current[0])
    asyncio.run(create_invoice("heleket", _request()))
    current[0] = replace(original, heleket_api_key="rotated", heleket_merchant_id="new-merchant")
    asyncio.run(create_invoice("heleket", _request()))
    assert calls[1][2]["merchant"] == "new-merchant"
    assert calls[1][2]["sign"] != calls[0][2]["sign"]
    current[0] = PaymentsConfig()
    with pytest.raises(PaymentError, match="not configured"):
        asyncio.run(create_invoice("heleket", _request()))
    assert len(calls) == 2


@pytest.mark.parametrize("result", [
    {"state": 1, "message": "upstream details must not be public"},
    {"state": 0, "result": {"uuid": "provider-id"}},
])
def test_upstream_errors_and_incomplete_invoices(transport, result):
    _, response = transport
    response.clear()
    response.update(result)
    with pytest.raises(PaymentError) as exc:
        asyncio.run(create_invoice("heleket", _request()))
    assert "upstream details" not in str(exc.value)


@pytest.mark.parametrize("amount", [0, -1, float("nan"), float("inf")])
def test_invalid_amount_does_not_reach_gateway(transport, amount):
    calls, _ = transport
    with pytest.raises(PaymentError, match="positive and finite"):
        asyncio.run(create_invoice("heleket", _request(amount=amount)))
    assert not calls


@pytest.mark.parametrize("surface", ["bot", "miniapp", "web", "android"])
def test_registry_exposes_heleket_on_all_checkout_surfaces(surface):
    provider = validate_provider_invoice("heleket", currency="USD", method="default", surface=surface)
    assert provider.payment_method == "HELEKET" and provider.webhook_key == "merchant"
    with pytest.raises(PaymentError):
        validate_provider_invoice("heleket", currency="BTC", method="default", surface=surface)


def test_webhook_verification_preserves_php_slashes_and_unicode():
    body = '{"type":"payment","amount":"12.34000000","additional_data":"Тариф \\/ месяц","status":"paid"}'
    signature = hashlib.md5(base64.b64encode(body.encode()) + b"secret").hexdigest()
    raw = (body[:-1] + ',"sign":"' + signature + '"}').encode()
    assert verify_heleket_webhook(raw, "secret")
    assert not verify_heleket_webhook(raw, "wrong")
    assert not verify_heleket_webhook(raw.replace(b"12.34", b"99.99"), "secret")
    assert not verify_heleket_webhook(raw, "")


@pytest.mark.parametrize("raw", [
    b"not JSON", b"[]", b"{}", b'{"sign":null}', b'{"sign":123}',
    '{"sign":"не hex"}'.encode(), b'\xff',
])
def test_malformed_webhooks_fail_closed(raw):
    assert not verify_heleket_webhook(raw, "secret")
