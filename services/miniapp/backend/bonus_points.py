"""Resolve RUB bonus point costs for menu invoices."""
from __future__ import annotations

from payments.rub_pricing import get_rub_rates, invoice_points_cost

from .config import get_config


async def resolve_points_cost(invoice_data: dict) -> int:
    rates = await get_rub_rates(get_config())
    return invoice_points_cost(invoice_data, rates)


async def enrich_invoice_dict(invoice_data: dict) -> dict:
    out = dict(invoice_data)
    out["points_cost"] = await resolve_points_cost(invoice_data)
    return out
