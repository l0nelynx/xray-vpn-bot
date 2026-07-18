"""Currency normalisation for revenue reporting.

Transactions store `amount` in whatever currency the payment method uses, with
no currency column. We map each payment_method to its native currency and
convert everything to RUB so totals are comparable.

USD→RUB is fetched from the Central Bank of Russia open endpoint
(cbr-xml-daily.ru, no key required) and cached in-process. Telegram Stars have
no market feed, so they use a fixed rate. Both rates fall back to constants if
the network is unavailable or config overrides are absent.
"""

from __future__ import annotations

import time

import httpx

from .config import get_config

# payment_method (as stored in the DB) -> native currency code
PAYMENT_CURRENCY: dict[str, str] = {
    "CRYPTOPAY": "USD",
    "TG_STARS": "STAR",
    "CRYSTAL_PAY": "RUB",
    "SBP_APAY": "RUB",
    "PLATEGA": "RUB",
    "PARITYPAY": "RUB",
    "FREE": "RUB",
}

# Wallet spend / non-cash settlement — not real money turnover for revenue KPIs.
NON_REVENUE_PAYMENT_METHODS: frozenset[str] = frozenset({"BONUS_CREDITS"})

_USD_RUB_FALLBACK = 75.0
_STAR_RUB_DEFAULT = 1.3
_CBR_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
_CACHE_TTL = 3600  # seconds

_usd_cache: dict[str, float] = {"rate": 0.0, "ts": 0.0}


def _star_rub_rate() -> float:
    """Stars → RUB. Config override `star_rub_rate`, else default 1.3."""
    try:
        return float(get_config().get("star_rub_rate", _STAR_RUB_DEFAULT))
    except (TypeError, ValueError):
        return _STAR_RUB_DEFAULT


def _usd_rub_fallback() -> float:
    """USD → RUB fallback when CBR is unreachable. Config override `usd_rub_rate`."""
    try:
        return float(get_config().get("usd_rub_rate", _USD_RUB_FALLBACK))
    except (TypeError, ValueError):
        return _USD_RUB_FALLBACK


async def get_usd_rub_rate() -> float:
    """Live USD→RUB from CBR, cached for an hour. Falls back to a constant."""
    now = time.time()
    if _usd_cache["rate"] > 0 and now - _usd_cache["ts"] < _CACHE_TTL:
        return _usd_cache["rate"]

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(_CBR_URL)
            resp.raise_for_status()
            rate = float(resp.json()["Valute"]["USD"]["Value"])
        if rate > 0:
            _usd_cache["rate"] = rate
            _usd_cache["ts"] = now
            return rate
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        pass

    return _usd_cache["rate"] or _usd_rub_fallback()


async def get_rates() -> dict[str, float]:
    """Return RUB-per-unit multipliers for every currency we handle."""
    usd = await get_usd_rub_rate()
    return {"RUB": 1.0, "USD": usd, "STAR": _star_rub_rate()}


def convert_to_rub(amount: float, payment_method: str | None, rates: dict[str, float]) -> float:
    """Convert a single amount in its native currency to RUB.

    Non-cash methods (e.g. BONUS_CREDITS) contribute 0 to revenue.
    """
    if payment_method in NON_REVENUE_PAYMENT_METHODS:
        return 0.0
    currency = PAYMENT_CURRENCY.get(payment_method or "", "RUB")
    return amount * rates.get(currency, 1.0)
