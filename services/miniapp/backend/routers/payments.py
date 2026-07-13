import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from payments import (
    InvoiceRequest,
    PaymentError,
    available_providers,
    create_invoice,
    get_provider,
)
from common_db.repo import promos as _repo_promos
from common_db.repo import users as _repo_users

from ..database.models import Transaction
from ..database.session import async_session
from ..menu_invoice import invoice_from_node, load_menu_node
from ..notify_log import esc, notify_log
from ..schemas.payments import (
    InvoiceCreateRequest,
    InvoiceResponse,
    ProviderInfo,
    ProvidersResponse,
)
from ..tg_auth import TgUser, get_tg_user
from ..android.auth_router import limiter

router = APIRouter(prefix="/api/payments", tags=["payments"])
logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@router.get("/providers", response_model=ProvidersResponse)
async def list_providers() -> ProvidersResponse:
    return ProvidersResponse(
        providers=[
            ProviderInfo(
                name=p.name,
                payment_method=p.payment_method,
                currencies=list(p.supported_currencies),
            )
            for p in available_providers()
        ]
    )


@router.post("/invoice", response_model=InvoiceResponse)
@limiter.limit("10/minute")
async def create_payment_invoice(
    request: Request,
    body: InvoiceCreateRequest,
    tg: TgUser = Depends(get_tg_user),
) -> InvoiceResponse:
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg.tg_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not registered")
    if user.is_banned:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "user is banned")

    node = await load_menu_node(body.node_id)
    if node is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "menu node not found")

    invoice_data = invoice_from_node(node)
    if invoice_data is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "menu node is not a valid invoice tariff",
        )

    try:
        provider = get_provider(invoice_data["provider"])
    except PaymentError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    if not provider.supports(invoice_data["currency"]):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"provider '{provider.name}' does not support currency "
            f"'{invoice_data['currency']}'",
        )

    # Apply promo discount if user has an unconsumed active redemption.
    invoice_amount = invoice_data["amount"]
    async with async_session() as session:
        ed = await _repo_promos.get_effective_discount(session, tg.tg_id)
        await session.commit()  # persist auto-seeded PromoSettings
        if ed is not None:
            invoice_amount = round(
                invoice_data["amount"] * (1 - ed.discount_percent / 100), 2
            )

    transaction_id = str(uuid.uuid4())
    invoice_req = InvoiceRequest(
        transaction_id=transaction_id,
        amount=invoice_amount,
        currency=invoice_data["currency"],
        days=invoice_data["days"],
        user_tg_id=tg.tg_id,
        username=tg.username,
        description=body.description or node["text"],
        method=invoice_data["method"],
    )

    try:
        invoice = await create_invoice(provider.name, invoice_req)
    except PaymentError as e:
        logger.warning(
            "invoice creation failed (provider=%s node=%s): %s",
            provider.name,
            body.node_id,
            e,
        )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))
    except Exception as e:  # defensive: SDKs can raise unexpected types
        logger.exception("unexpected invoice failure")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"invoice failed: {e}")

    persisted_id = (
        invoice.invoice_id
        if provider.name in {"crystal", "crypto", "platega"}
        else transaction_id
    )

    async with async_session() as session:
        session.add(
            Transaction(
                transaction_id=persisted_id,
                vless_uuid="None",
                username=tg.username or f"id_{tg.tg_id}",
                order_status="created",
                delivery_status=0,
                days_ordered=invoice_data["days"],
                user_id=user.id,
                payment_method=provider.payment_method,
                amount=float(invoice_data["amount"]),
                created_at=_now_iso(),
                tariff_slug=invoice_data["tariff_slug"],
            )
        )
        await session.commit()

    await notify_log(
        f"🧾 <b>Invoice created (miniapp)</b>\n"
        f"user: <code>{tg.tg_id}</code> @{esc(tg.username or '—')}\n"
        f"provider: <code>{esc(provider.name)}</code>\n"
        f"amount: <code>{invoice_amount} {esc(invoice_data['currency'])}</code>\n"
        f"days: <code>{invoice_data['days']}</code>\n"
        f"slug: <code>{esc(invoice_data['tariff_slug'])}</code>\n"
        f"tx: <code>{esc(persisted_id)}</code>"
    )

    return InvoiceResponse(
        provider=provider.name,
        invoice_id=invoice.invoice_id,
        url=invoice.url,
        amount=invoice.amount,
        currency=invoice.currency,
        transaction_id=persisted_id,
        payment_method=provider.payment_method,
    )
