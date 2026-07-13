"""Shared helpers for resolving invoice parameters from Tariff Constructor nodes.

MiniApp, Android and web portal invoice endpoints must read price/days/provider
from `webapp_menu_nodes` — never trust client-supplied tariff fields.
"""

from __future__ import annotations

from sqlalchemy import text

from .database.session import async_session


async def load_menu_node(node_id: int) -> dict | None:
    """Return one active menu node row by id, or None."""
    async with async_session() as session:
        result = await session.execute(
            text(
                "SELECT id, parent_id, text, action, sort_order, "
                "invoice_provider, invoice_amount, invoice_currency, "
                "invoice_method, invoice_days, invoice_tariff_slug "
                "FROM webapp_menu_nodes WHERE id = :id AND is_active = TRUE"
            ),
            {"id": node_id},
        )
        row = result.first()
    return dict(row._mapping) if row is not None else None


def invoice_from_node(row: dict) -> dict | None:
    """Extract server-side invoice fields from a menu node row.

    Returns None when the node is not a valid invoice leaf (wrong action,
    missing provider/slug, or non-positive amount/days).
    """
    if row["action"] != "invoice":
        return None
    provider = (row["invoice_provider"] or "").lower().strip()
    if not provider:
        return None
    slug = (row["invoice_tariff_slug"] or "").strip()
    if not slug:
        return None
    amount = float(row["invoice_amount"] or 0)
    days = int(row["invoice_days"] or 0)
    if amount <= 0 or days <= 0:
        return None
    return {
        "provider": provider,
        "amount": amount,
        "currency": (row["invoice_currency"] or "RUB").upper(),
        "method": row["invoice_method"],
        "days": days,
        "tariff_slug": slug,
    }
