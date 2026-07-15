"""Tests for RUB bonus points conversion."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from payments import rub_pricing
from payments.rub_pricing import (
    LEGACY_CREDIT_TO_POINTS,
    amount_to_rub_points,
    currency_needs_live_usd,
    invoice_points_cost,
)


def test_rub_amount_ceil() -> None:
    rates = {"RUB": 1.0, "USD": 90.0, "STAR": 1.3}
    assert amount_to_rub_points(299.0, "RUB", rates) == 299
    assert amount_to_rub_points(299.1, "RUB", rates) == 300


def test_usd_conversion() -> None:
    rates = {"RUB": 1.0, "USD": 90.0, "STAR": 1.3}
    assert amount_to_rub_points(5.0, "USD", rates) == 450
    assert amount_to_rub_points(5.0, "USDT", rates) == 450


def test_star_conversion() -> None:
    rates = {"RUB": 1.0, "USD": 90.0, "STAR": 1.3}
    assert amount_to_rub_points(100, "XTR", rates) == 130


def test_invoice_points_cost() -> None:
    rates = {"RUB": 1.0, "USD": 90.0, "STAR": 1.3}
    inv = {"amount": 10.0, "currency": "USD", "days": 30, "tariff_slug": "pro"}
    assert invoice_points_cost(inv, rates) == 900


def test_legacy_multiplier_constant() -> None:
    assert LEGACY_CREDIT_TO_POINTS == 10


def test_currency_needs_live_usd() -> None:
    assert not currency_needs_live_usd("RUB")
    assert not currency_needs_live_usd("XTR")
    assert currency_needs_live_usd("USD")
    assert currency_needs_live_usd("USDT")
    assert currency_needs_live_usd("EUR")


def test_failed_cbr_fetch_is_cached() -> None:
    """A blocked CBR must not re-timeout on every invoice enrichment."""
    rub_pricing._usd_cache.update({"rate": 0.0, "ts": 0.0, "live": 0.0})

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
    mock_session.__aexit__ = AsyncMock(return_value=False)

    async def _run() -> None:
        with patch("payments.rub_pricing.aiohttp.ClientSession", return_value=mock_session):
            first = await rub_pricing.fetch_usd_rub_rate({"usd_rub_rate": 80.0})
            assert first == 80.0
            # Second call must hit the failure cache — no new ClientSession.
            with patch(
                "payments.rub_pricing.aiohttp.ClientSession",
                side_effect=AssertionError("CBR must not be re-fetched"),
            ):
                second = await rub_pricing.fetch_usd_rub_rate({"usd_rub_rate": 80.0})
            assert second == 80.0

    asyncio.run(_run())
