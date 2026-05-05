"""External payment endpoints for the Android API.

Reuses miniapp's provider abstractions (`payments/apay.py`, `payments/platega.py`)
and the shared `transactions` table. Android transactions are tagged with
`android_user_id` so the bot's webhook delivery can locate the user without a
Telegram id.

Tariff selection mirrors miniapp's tariff constructor: the client passes
`amount`, `days`, `squad_id`, `external_squad_id` and we encode them into
`tariff_slug = "sid:<squad>:esid:<external>"` — the same format
`subscription_service._parse_squad_slug` already understands.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..database.session import async_session
from ..payments import (
    InvoiceRequest,
    PaymentError,
    create_invoice,
    get_provider,
)
from . import deps, repo
from .auth_router import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/android/payments", tags=["android-payments"])


# Android exposes only fiat providers — Telegram-bound providers (CryptoBot)
# don't make sense from a native app context.
_ANDROID_PROVIDERS = ("apay", "platega")


# --- Schemas ---------------------------------------------------------------


class AndroidProviderInfo(BaseModel):
    name: str
    payment_method: str
    currencies: list[str]


class AndroidProvidersResponse(BaseModel):
    providers: list[AndroidProviderInfo]


class AndroidInvoiceRequest(BaseModel):
    provider: str = Field(..., description="apay | platega")
    amount: float = Field(..., gt=0)
    currency: str = Field("RUB", description="Provider-supported currency")
    days: int = Field(..., gt=0)
    squad_id: str = Field(..., min_length=1, max_length=100)
    external_squad_id: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    method: str | None = Field(
        None, description="Optional provider-specific method id (Platega)"
    )


class AndroidInvoiceResponse(BaseModel):
    provider: str
    invoice_id: str
    url: str
    amount: float
    currency: str
    transaction_id: str
    payment_method: str


# --- Helpers ---------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _build_tariff_slug(squad_id: str, external_squad_id: str) -> str:
    return f"sid:{squad_id}:esid:{external_squad_id}"


# --- Endpoints -------------------------------------------------------------


@router.get("/providers", response_model=AndroidProvidersResponse)
async def list_providers() -> AndroidProvidersResponse:
    out: list[AndroidProviderInfo] = []
    for name in _ANDROID_PROVIDERS:
        try:
            p = get_provider(name)
        except PaymentError:
            continue
        out.append(
            AndroidProviderInfo(
                name=p.name,
                payment_method=p.payment_method,
                currencies=list(p.supported_currencies),
            )
        )
    return AndroidProvidersResponse(providers=out)


@router.post("/invoice", response_model=AndroidInvoiceResponse)
@limiter.limit("10/minute")
async def create_payment_invoice(
    body: AndroidInvoiceRequest,
    request: Request,
    user: repo.UserRow = Depends(deps.require_verified_email),
) -> AndroidInvoiceResponse:
    if body.provider not in _ANDROID_PROVIDERS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "provider_not_allowed"},
        )

    try:
        provider = get_provider(body.provider)
    except PaymentError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"code": "provider_unavailable"}
        ) from exc

    if not provider.supports(body.currency):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "currency_unsupported"},
        )

    transaction_id = str(uuid.uuid4())
    invoice_req = InvoiceRequest(
        transaction_id=transaction_id,
        amount=body.amount,
        currency=body.currency.upper(),
        days=body.days,
        # Providers expect an int. We don't have a tg_id for Android users —
        # pass user.id (negated to keep collisions impossible against real
        # tg_ids); only used for description/payload tagging by Platega.
        user_tg_id=-int(user.id),
        username=user.email,
        description=body.description or f"AndroidUser:{user.id}",
        method=body.method,
    )

    try:
        invoice = await create_invoice(provider.name, invoice_req)
    except PaymentError as exc:
        logger.warning(
            "android invoice creation failed (provider=%s): %s", provider.name, exc
        )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail={"code": "invoice_failed"}
        ) from exc
    except Exception as exc:  # defensive
        logger.exception("android: unexpected invoice failure")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail={"code": "invoice_failed"}
        ) from exc

    # Persist into the shared transactions table. Use the provider-issued id
    # for Platega so its webhook (keyed by transactionId) matches; APay echoes
    # the merchant order id back, so we keep our uuid.
    persisted_id = invoice.invoice_id if provider.name == "platega" else transaction_id
    tariff_slug = _build_tariff_slug(body.squad_id, body.external_squad_id)

    async with async_session() as session:
        await session.execute(
            text(
                "INSERT INTO transactions ("
                "transaction_id, vless_uuid, username, order_status, "
                "delivery_status, payment_method, amount, created_at, "
                "days_ordered, tariff_slug, user_id, android_user_id"
                ") VALUES ("
                ":tid, :vu, :uname, 'created', 0, :pm, :amt, :ts, "
                ":days, :slug, :uid, :aid"
                ")"
            ),
            {
                "tid": persisted_id,
                "vu": "None",
                "uname": user.email or f"android_{user.id}",
                "pm": provider.payment_method,
                "amt": float(body.amount),
                "ts": _now_iso(),
                "days": body.days,
                "slug": tariff_slug,
                # Bot's transactions schema requires user_id NOT NULL; reuse the
                # same row id since users.id is the unified identity.
                "uid": user.id,
                "aid": user.id,
            },
        )
        await session.commit()

    return AndroidInvoiceResponse(
        provider=provider.name,
        invoice_id=invoice.invoice_id,
        url=invoice.url,
        amount=invoice.amount,
        currency=invoice.currency,
        transaction_id=persisted_id,
        payment_method=provider.payment_method,
    )


# --- Status / list ---------------------------------------------------------


class AndroidTransactionInfo(BaseModel):
    transaction_id: str
    status: str
    delivery_status: int
    payment_method: str | None
    amount: float | None
    days_ordered: int
    created_at: str | None


class AndroidTransactionsResponse(BaseModel):
    transactions: list[AndroidTransactionInfo]


@router.get("/transactions", response_model=AndroidTransactionsResponse)
async def list_user_transactions(
    user: repo.UserRow = Depends(deps.get_current_user),
) -> AndroidTransactionsResponse:
    async with async_session() as session:
        rows = (await session.execute(
            text(
                "SELECT transaction_id, order_status, delivery_status, "
                "payment_method, amount, days_ordered, created_at "
                "FROM transactions WHERE android_user_id = :u "
                "ORDER BY created_at DESC LIMIT 50"
            ),
            {"u": user.id},
        )).all()
    return AndroidTransactionsResponse(
        transactions=[
            AndroidTransactionInfo(
                transaction_id=r[0],
                status=r[1],
                delivery_status=int(r[2] or 0),
                payment_method=r[3],
                amount=float(r[4]) if r[4] is not None else None,
                days_ordered=int(r[5] or 0),
                created_at=r[6],
            )
            for r in rows
        ]
    )


@router.get("/transactions/{transaction_id}", response_model=AndroidTransactionInfo)
async def get_user_transaction(
    transaction_id: str,
    user: repo.UserRow = Depends(deps.get_current_user),
) -> AndroidTransactionInfo:
    async with async_session() as session:
        row = (await session.execute(
            text(
                "SELECT transaction_id, order_status, delivery_status, "
                "payment_method, amount, days_ordered, created_at "
                "FROM transactions WHERE transaction_id = :t AND android_user_id = :u"
            ),
            {"t": transaction_id, "u": user.id},
        )).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found"})
    return AndroidTransactionInfo(
        transaction_id=row[0],
        status=row[1],
        delivery_status=int(row[2] or 0),
        payment_method=row[3],
        amount=float(row[4]) if row[4] is not None else None,
        days_ordered=int(row[5] or 0),
        created_at=row[6],
    )
