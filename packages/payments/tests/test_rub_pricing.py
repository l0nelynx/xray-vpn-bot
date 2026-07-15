"""Tests for RUB bonus points conversion."""
from __future__ import annotations

from payments.rub_pricing import (
    LEGACY_CREDIT_TO_POINTS,
    amount_to_rub_points,
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
