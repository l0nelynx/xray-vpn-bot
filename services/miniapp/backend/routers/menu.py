"""Localized Tariff Constructor tree consumed by the Telegram MiniApp."""
from fastapi import APIRouter, Depends
from payments import PaymentError, available_providers, validate_provider_invoice
from payments.rub_pricing import get_rub_rates_for_currencies

from common_db.repo import users as _repo_users
from common_db.repo.webapp_menu import build_tree, list_nodes

from ..bonus_points import enrich_invoice_dict
from ..config import get_config
from ..database.session import async_session
from ..tg_auth import TgUser, get_tg_user

router = APIRouter(prefix="/api/menu", tags=["menu"])


def _valid_miniapp_target(target) -> bool:
    try:
        validate_provider_invoice(
            target.provider,
            currency=target.currency,
            method=target.method,
            surface="miniapp",
        )
    except PaymentError:
        return False
    return True


async def _enrich(nodes: list[dict], rates) -> list[dict]:
    output = []
    for node in nodes:
        children = await _enrich(node["children"], rates)
        invoice = node["invoice"]
        if invoice:
            invoice = await enrich_invoice_dict(invoice, rates)
        output.append(
            {
                "id": node["id"],
                "parent_id": node["parent_id"],
                "text": node["text"],
                "action": node["action"],
                "invoice": invoice,
                "children": children,
            }
        )
    return output


@router.get("/tree")
async def get_menu_tree(tg: TgUser = Depends(get_tg_user)) -> dict:
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg.tg_id)
        lang = (user.language if user else None) or "ru"
        nodes = await list_nodes(session)
    allowed = {
        provider.name
        for provider in available_providers()
        if "miniapp" in provider.surfaces
    }
    tree = build_tree(
        nodes,
        lang=lang,
        allowed_providers=allowed,
        invoice_validator=_valid_miniapp_target,
    )
    currencies = [
        node["invoice"]["currency"]
        for node in _walk(tree)
        if node.get("invoice")
    ]
    rates = await get_rub_rates_for_currencies(currencies, get_config())
    return {"tree": await _enrich(tree, rates)}


def _walk(nodes: list[dict]):
    for node in nodes:
        yield node
        yield from _walk(node["children"])
