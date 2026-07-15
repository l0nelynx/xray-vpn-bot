"""Convert invoice amounts to RUB bonus points (1 point ≈ 1 RUB)."""
from __future__ import annotations

import asyncio
import math
import time
from typing import Mapping

import aiohttp

_CBR_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
_CACHE_TTL = 3600
_FAILURE_CACHE_TTL = 300  # don't hammer CBR / hang menu builds on repeated timeouts
_USD_RUB_FALLBACK = 75.0
_STAR_RUB_DEFAULT = 1.3

_usd_cache: dict[str, float] = {"rate": 0.0, "ts": 0.0, "live": 0.0}
_usd_fetch_lock: asyncio.Lock | None = None


def _get_usd_fetch_lock() -> asyncio.Lock:
    global _usd_fetch_lock
    if _usd_fetch_lock is None:
        _usd_fetch_lock = asyncio.Lock()
    return _usd_fetch_lock

# invoice_currency values → rate key in get_rub_rates()
_CURRENCY_TO_RATE_KEY: dict[str, str] = {
    "RUB": "RUB",
    "USD": "USD",
    "USDT": "USD",
    "USDC": "USD",
    "EUR": "EUR",
    "XTR": "STAR",
    "STAR": "STAR",
}


def star_rub_rate_from_config(config: Mapping[str, object] | None) -> float:
    if not config:
        return _STAR_RUB_DEFAULT
    try:
        return float(config.get("star_rub_rate", _STAR_RUB_DEFAULT))
    except (TypeError, ValueError):
        return _STAR_RUB_DEFAULT


def usd_rub_fallback_from_config(config: Mapping[str, object] | None) -> float:
    if not config:
        return _USD_RUB_FALLBACK
    try:
        return float(config.get("usd_rub_rate", _USD_RUB_FALLBACK))
    except (TypeError, ValueError):
        return _USD_RUB_FALLBACK


def _cached_usd(now: float) -> float | None:
    rate = _usd_cache["rate"]
    if rate <= 0:
        return None
    ttl = _CACHE_TTL if _usd_cache["live"] else _FAILURE_CACHE_TTL
    if now - _usd_cache["ts"] >= ttl:
        return None
    return rate


async def _fetch_usd_rub_uncached(config: Mapping[str, object] | None) -> float:
    now = time.time()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(_CBR_URL, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                resp.raise_for_status()
                data = await resp.json()
                rate = float(data["Valute"]["USD"]["Value"])
        if rate > 0:
            _usd_cache["rate"] = rate
            _usd_cache["ts"] = now
            _usd_cache["live"] = 1.0
            return rate
    except (aiohttp.ClientError, KeyError, TypeError, ValueError, asyncio.TimeoutError):
        pass

    fallback = _usd_cache["rate"] or usd_rub_fallback_from_config(config)
    # Cache the fallback so a flaky/blocked CBR does not time out once per invoice node.
    _usd_cache["rate"] = fallback
    _usd_cache["ts"] = now
    _usd_cache["live"] = 0.0
    return fallback


async def fetch_usd_rub_rate(config: Mapping[str, object] | None = None) -> float:
    """Live USD→RUB from CBR, cached. Falls back to config or constant."""
    now = time.time()
    cached = _cached_usd(now)
    if cached is not None:
        return cached

    async with _get_usd_fetch_lock():
        cached = _cached_usd(time.time())
        if cached is not None:
            return cached
        return await _fetch_usd_rub_uncached(config)


def currency_needs_live_usd(currency: str | None) -> bool:
    """True when points conversion depends on a live USD→RUB rate."""
    key = _CURRENCY_TO_RATE_KEY.get((currency or "RUB").upper().strip(), "RUB")
    return key in ("USD", "EUR")


async def get_rub_rates(config: Mapping[str, object] | None = None) -> dict[str, float]:
    """Return RUB-per-unit multipliers: RUB, USD, STAR, EUR."""
    usd = await fetch_usd_rub_rate(config)
    star = star_rub_rate_from_config(config)
    # EUR: no CBR fetch here — use USD as rough proxy if needed
    eur = usd * 1.05
    return {"RUB": 1.0, "USD": usd, "STAR": star, "EUR": eur}


async def get_rub_rates_for_currencies(
    currencies: list[str] | set[str] | tuple[str, ...],
    config: Mapping[str, object] | None = None,
) -> dict[str, float]:
    """Like get_rub_rates, but skip CBR when no invoice needs USD/EUR."""
    if any(currency_needs_live_usd(c) for c in currencies):
        return await get_rub_rates(config)
    star = star_rub_rate_from_config(config)
    # Unused multipliers kept for callers that always pass a rates map.
    usd = usd_rub_fallback_from_config(config)
    return {"RUB": 1.0, "USD": usd, "STAR": star, "EUR": usd * 1.05}


def amount_to_rub_points(
    amount: float,
    currency: str,
    rates: Mapping[str, float],
) -> int:
    """Convert invoice price to integer RUB points (ceil, minimum 1)."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    cur = (currency or "RUB").upper().strip()
    rate_key = _CURRENCY_TO_RATE_KEY.get(cur, "RUB")
    multiplier = rates.get(rate_key, 1.0)
    rub = float(amount) * float(multiplier)
    return max(1, math.ceil(rub))


def invoice_points_cost(invoice: Mapping[str, object], rates: Mapping[str, float]) -> int:
    """Points to debit for a server-resolved invoice dict."""
    return amount_to_rub_points(
        float(invoice["amount"]),
        str(invoice.get("currency") or "RUB"),
        rates,
    )


LEGACY_CREDIT_TO_POINTS = 10


__all__ = [
    "LEGACY_CREDIT_TO_POINTS",
    "amount_to_rub_points",
    "currency_needs_live_usd",
    "fetch_usd_rub_rate",
    "get_rub_rates",
    "get_rub_rates_for_currencies",
    "invoice_points_cost",
    "star_rub_rate_from_config",
    "usd_rub_fallback_from_config",
]
