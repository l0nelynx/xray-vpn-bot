from __future__ import annotations

import asyncio

import pytest

from payments.base import InvoiceRequest, PaymentError
from payments.config import PaymentsConfig, set_config_provider
from payments.stars import TelegramStarsProvider, validate_stars_payment


class _Response:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def json(self):
        return {"ok": True, "result": "https://t.me/$invoice"}


class _Session:
    def __init__(self):
        self.url = None
        self.data = None

    def post(self, url, *, data):
        self.url = url
        self.data = data
        return _Response()


def _request(amount: float = 25, currency: str = "XTR") -> InvoiceRequest:
    return InvoiceRequest(
        transaction_id="local-transaction-id",
        amount=amount,
        currency=currency,
        days=30,
        user_tg_id=42,
    )


def test_stars_creates_telegram_invoice_link(monkeypatch) -> None:
    session = _Session()
    set_config_provider(lambda: PaymentsConfig(bot_token="secret-token"))
    monkeypatch.setattr(
        TelegramStarsProvider, "_get_session", classmethod(lambda cls: session)
    )
    invoice = asyncio.run(TelegramStarsProvider().create_invoice(_request()))
    assert invoice.invoice_id == "local-transaction-id"
    assert invoice.currency == "XTR"
    assert invoice.url == "https://t.me/$invoice"
    assert session.url.endswith("/botsecret-token/createInvoiceLink")
    assert session.data["payload"] == "local-transaction-id"
    assert '"amount": 25' in session.data["prices"]


@pytest.mark.parametrize(
    ("amount", "currency"),
    [(0, "XTR"), (-1, "XTR"), (1.5, "XTR"), (10, "RUB")],
)
def test_stars_rejects_invalid_amount_or_currency(amount, currency) -> None:
    set_config_provider(lambda: PaymentsConfig(bot_token="secret-token"))
    with pytest.raises(PaymentError):
        asyncio.run(
            TelegramStarsProvider().create_invoice(_request(amount, currency))
        )


def _transaction(**overrides):
    transaction = {
        "transaction_id": "local-transaction-id",
        "status": "created",
        "user_tg_id": 42,
        "payment_method": "TG_STARS",
        "amount": 25,
    }
    transaction.update(overrides)
    return transaction


def test_stars_payment_matches_transaction_snapshot() -> None:
    assert validate_stars_payment(
        _transaction(), user_tg_id=42, currency="XTR", total_amount=25
    )


@pytest.mark.parametrize(
    "transaction,user_tg_id,currency,total_amount",
    [
        (None, 42, "XTR", 25),
        (_transaction(transaction_id="forged"), 7, "XTR", 25),
        (_transaction(), 42, "USD", 25),
        (_transaction(), 42, "XTR", 24),
        (_transaction(payment_method="crypto"), 42, "XTR", 25),
        (_transaction(status="paid"), 42, "XTR", 25),
        (_transaction(status="processing"), 42, "XTR", 25),
        (_transaction(amount=1.5), 42, "XTR", 1),
    ],
)
def test_stars_payment_rejects_forgery_and_replays(
    transaction, user_tg_id, currency, total_amount
) -> None:
    assert not validate_stars_payment(
        transaction,
        user_tg_id=user_tg_id,
        currency=currency,
        total_amount=total_amount,
    )
