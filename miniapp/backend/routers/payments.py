import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from ..database.models import Promo, PromoSettings, Transaction, User
from ..database.session import async_session
from ..payments import (
    InvoiceRequest,
    PaymentError,
    available_providers,
    create_invoice,
    get_provider,
)
from ..schemas.payments import (
    InvoiceCreateRequest,
    InvoiceResponse,
    ProviderInfo,
    ProvidersResponse,
)
from ..tg_auth import TgUser, get_tg_user

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
async def create_payment_invoice(
    body: InvoiceCreateRequest,
    tg: TgUser = Depends(get_tg_user),
) -> InvoiceResponse:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg.tg_id))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not registered")
    if user.is_banned:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "user is banned")

    try:
        provider = get_provider(body.provider)
    except PaymentError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    if not provider.supports(body.currency):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"provider '{provider.name}' does not support currency '{body.currency}'",
        )

    # Apply promo discount if user has an unconsumed active promo
    invoice_amount = body.amount
    async with async_session() as session:
        user_promo = await session.scalar(select(Promo).where(Promo.tg_id == tg.tg_id))
        if user_promo and user_promo.used_promo and not user_promo.used_promo_consumed:
            owner_promo = await session.scalar(
                select(Promo).where(Promo.promo_code == user_promo.used_promo)
            )
            if owner_promo and owner_promo.discount_percent is not None:
                discount_pct = owner_promo.discount_percent
            else:
                ps = await session.scalar(select(PromoSettings).where(PromoSettings.id == 1))
                discount_pct = ps.default_discount_percent if ps else 20
            invoice_amount = round(body.amount * (1 - discount_pct / 100), 2)

    transaction_id = str(uuid.uuid4())
    request = InvoiceRequest(
        transaction_id=transaction_id,
        amount=invoice_amount,
        currency=body.currency.upper(),
        days=body.days,
        user_tg_id=tg.tg_id,
        username=tg.username,
        description=body.description,
    )

    try:
        invoice = await create_invoice(provider.name, request)
    except PaymentError as e:
        logger.warning("invoice creation failed (provider=%s): %s", provider.name, e)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))
    except Exception as e:  # defensive: SDKs can raise unexpected types
        logger.exception("unexpected invoice failure")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"invoice failed: {e}")

    # Persist into the shared transactions table so existing webhook handlers
    # (in main.py: /bot/apays_webhook, /bot/crystal_webhook) and the CryptoPay
    # poller in app/handlers/payments.py can deliver the subscription.
    # Use the provider-issued id as the transaction key when available
    # (CrystalPay/CryptoPay) so the webhook lookups match.
    persisted_id = invoice.invoice_id if provider.name in {"crystal", "crypto"} else transaction_id

    async with async_session() as session:
        session.add(
            Transaction(
                transaction_id=persisted_id,
                vless_uuid="None",
                username=tg.username or f"id_{tg.tg_id}",
                order_status="created",
                delivery_status=0,
                days_ordered=body.days,
                user_id=user.id,
                payment_method=provider.payment_method,
                amount=float(body.amount),
                created_at=_now_iso(),
                tariff_slug=body.tariff_slug,
            )
        )
        await session.commit()

    return InvoiceResponse(
        provider=provider.name,
        invoice_id=invoice.invoice_id,
        url=invoice.url,
        amount=invoice.amount,
        currency=invoice.currency,
        transaction_id=persisted_id,
        payment_method=provider.payment_method,
    )
