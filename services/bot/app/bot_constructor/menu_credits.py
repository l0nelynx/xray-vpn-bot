"""Bonus-credits tariff picker backed by webapp_menu_nodes (same tree as MiniApp)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from payments.rub_pricing import get_rub_rates, invoice_points_cost
from sqlalchemy import text

from app.database.models import async_session
from app.settings import secrets


def _invoice_from_node(row: dict) -> dict | None:
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


def _path_label(rows_by_id: dict[int, dict], row_id: int) -> str:
    parts: list[str] = []
    current_id: int | None = row_id
    while current_id is not None:
        row = rows_by_id.get(current_id)
        if row is None:
            break
        parts.append(row["text"])
        current_id = row["parent_id"]
    return " / ".join(reversed(parts))


async def _load_menu_rows() -> list[dict]:
    async with async_session() as session:
        result = await session.execute(text(
            "SELECT id, parent_id, text, action, sort_order, "
            "invoice_provider, invoice_amount, invoice_currency, "
            "invoice_method, invoice_days, invoice_tariff_slug "
            "FROM webapp_menu_nodes WHERE is_active = TRUE"
        ))
        return [dict(r._mapping) for r in result.all()]


async def load_menu_node(node_id: int) -> dict | None:
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


async def resolve_node_points_cost(node: dict) -> tuple[dict, int] | None:
    invoice = _invoice_from_node(node)
    if invoice is None:
        return None
    rates = await get_rub_rates(secrets)
    return invoice, invoice_points_cost(invoice, rates)


async def create_credits_menu_keyboard() -> InlineKeyboardMarkup | None:
    """Flat list of invoice leaves with RUB point prices."""
    from app.bot_constructor.keyboards.tools import CreditsNodeCallbackData

    rows = await _load_menu_rows()
    if not rows:
        return None

    rows_by_id = {r["id"]: r for r in rows}
    rates = await get_rub_rates(secrets)
    items: list[tuple[int, str, int]] = []

    for row in sorted(rows, key=lambda r: (r["sort_order"], r["id"])):
        invoice = _invoice_from_node(row)
        if invoice is None:
            continue
        points = invoice_points_cost(invoice, rates)
        label = _path_label(rows_by_id, row["id"])
        items.append((row["id"], label, points))

    if not items:
        return None

    builder = InlineKeyboardBuilder()
    for node_id, label, points in items:
        builder.row(
            InlineKeyboardButton(
                text=f"{label} | {points} 🪙",
                callback_data=CreditsNodeCallbackData(node_id=node_id).pack(),
            )
        )
    builder.row(InlineKeyboardButton(text="Назад", callback_data="Premium"))
    builder.row(InlineKeyboardButton(text="На главную", callback_data="Main"))
    return builder.as_markup()
