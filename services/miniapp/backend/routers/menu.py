"""Public menu tree endpoint consumed by the webapp.

The tree is authored in the dashboard (Tariff Constructor) and stored in the
shared `webapp_menu_nodes` table. We read it directly via SQL so the miniapp
backend does not need to import the dashboard ORM models.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text

from ..bonus_points import enrich_invoice_dict
from ..database.session import async_session
from ..menu_invoice import invoice_from_node
from ..tg_auth import TgUser, get_tg_user

router = APIRouter(prefix="/api/menu", tags=["menu"])


async def _build_tree(rows: list[dict], parent_id: int | None) -> list[dict]:
    items = [r for r in rows if r["parent_id"] == parent_id]
    items.sort(key=lambda r: (r["sort_order"], r["id"]))
    out: list[dict] = []
    for r in items:
        children = await _build_tree(rows, r["id"])
        inv_raw = invoice_from_node(r)
        if r["action"] == "invoice" and inv_raw is None:
            continue
        if r["action"] != "invoice" and not children and inv_raw is None:
            continue
        inv = None
        if inv_raw:
            enriched = await enrich_invoice_dict(inv_raw)
            inv = {
                "provider": enriched["provider"],
                "amount": enriched["amount"],
                "currency": enriched["currency"],
                "method": enriched["method"],
                "days": enriched["days"],
                "tariff_slug": enriched["tariff_slug"],
                "points_cost": enriched["points_cost"],
            }
        out.append(
            {
                "id": r["id"],
                "parent_id": r["parent_id"],
                "text": r["text"],
                "action": r["action"],
                "invoice": inv,
                "children": children,
            }
        )
    return out


@router.get("/tree")
async def get_menu_tree(_: TgUser = Depends(get_tg_user)) -> dict:
    async with async_session() as session:
        result = await session.execute(text(
            "SELECT id, parent_id, text, action, sort_order, is_active, "
            "invoice_provider, invoice_amount, invoice_currency, invoice_method, "
            "invoice_days, invoice_tariff_slug "
            "FROM webapp_menu_nodes WHERE is_active = TRUE"
        ))
        rows = [dict(r._mapping) for r in result.all()]

    return {"tree": await _build_tree(rows, None)}
