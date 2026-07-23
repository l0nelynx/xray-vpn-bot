"""Server-side invoice resolution from the shared Tariff Constructor tree."""
from __future__ import annotations

from common_db.repo.webapp_menu import get_active_node, invoice_target

from .database.session import async_session


async def load_menu_node(node_id: int) -> dict | None:
    async with async_session() as session:
        node = await get_active_node(session, node_id)
        if node is None:
            return None
        return {
            "id": node.id,
            "parent_id": node.parent_id,
            "text": node.text_ru or node.text_en,
            "text_ru": node.text_ru,
            "text_en": node.text_en,
            "action": node.action,
            "invoice_provider": node.invoice_provider,
            "invoice_amount": node.invoice_amount,
            "invoice_currency": node.invoice_currency,
            "invoice_method": node.invoice_method,
            "invoice_days": node.invoice_days,
            "invoice_squad_id": node.invoice_squad_id,
            "invoice_external_squad_id": node.invoice_external_squad_id,
        }


def invoice_from_node(row: dict) -> dict | None:
    class _Node:
        pass

    node = _Node()
    for key, value in row.items():
        setattr(node, key, value)
    target = invoice_target(node)  # type: ignore[arg-type]
    if target is None:
        return None
    return {
        "provider": target.provider,
        "amount": target.amount,
        "currency": target.currency,
        "method": target.method,
        "days": target.days,
        "squad_id": target.squad_id,
        "external_squad_id": target.external_squad_id,
        "tariff_slug": f"sid:{target.squad_id}:esid:{target.external_squad_id}",
    }
