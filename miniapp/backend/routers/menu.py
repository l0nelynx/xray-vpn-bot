"""Public menu tree endpoint consumed by the webapp.

The tree is authored in the dashboard (Tariff Constructor) and stored in the
shared `webapp_menu_nodes` table. We read it directly via SQL so the miniapp
backend does not need to import the dashboard ORM models.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text

from ..database.session import async_session
from ..tg_auth import TgUser, get_tg_user

router = APIRouter(prefix="/api/menu", tags=["menu"])


def _build_tree(rows: list[dict], parent_id: int | None) -> list[dict]:
    items = [r for r in rows if r["parent_id"] == parent_id]
    items.sort(key=lambda r: (r["sort_order"], r["id"]))
    return [
        {
            "id": r["id"],
            "parent_id": r["parent_id"],
            "text": r["text"],
            "action": r["action"],
            "invoice": (
                {
                    "provider": r["invoice_provider"],
                    "amount": r["invoice_amount"],
                    "currency": r["invoice_currency"],
                    "method": r["invoice_method"],
                    "days": r["invoice_days"],
                    "tariff_slug": r["invoice_tariff_slug"],
                }
                if r["action"] == "invoice"
                else None
            ),
            "children": _build_tree(rows, r["id"]),
        }
        for r in items
    ]


@router.get("/tree")
async def get_menu_tree(_: TgUser = Depends(get_tg_user)) -> dict:
    async with async_session() as session:
        result = await session.execute(text(
            "SELECT id, parent_id, text, action, sort_order, is_active, "
            "invoice_provider, invoice_amount, invoice_currency, invoice_method, "
            "invoice_days, invoice_tariff_slug "
            "FROM webapp_menu_nodes WHERE is_active = 1"
        ))
        rows = [dict(r._mapping) for r in result.all()]

    return {"tree": _build_tree(rows, None)}
