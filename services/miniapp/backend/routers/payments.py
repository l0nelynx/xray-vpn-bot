import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from payments import (
    InvoiceRequest,
    PaymentError,
    available_providers,
    create_invoice,
    validate_provider_invoice,
)
from common_db.repo import balance as _repo_balance
from common_db.repo import users as _repo_users
from common_db.repo import subscriptions as _repo_subscriptions

from ..bonus_points import resolve_points_cost
from ..credits_delivery import pay_and_deliver
from ..database.models import Transaction
from ..database.session import async_session
from ..menu_invoice import invoice_from_node, load_menu_node
from ..notify_log import esc, notify_log
from ..schemas.payments import (
    InvoiceCreateRequest,
    InvoiceResponse,
    PayCreditsRequest,
    PayCreditsResponse,
    ProviderInfo,
    ProvidersResponse,
)
from ..tg_auth import TgUser, get_tg_user
from ..android.auth_router import limiter

router = APIRouter(prefix="/api/payments", tags=["payments"])
logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _purchase_target_rw_id(
    *, user_id: int, subscription_id: int | None
) -> int | None:
    async with async_session() as session:
        if subscription_id is not None:
            target = await _repo_subscriptions.get_for_user(
                session, user_id=user_id, subscription_id=subscription_id
            )
            if target is None:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    detail={"code": "subscription_not_found"},
                )
        else:
            target = await _repo_subscriptions.get_primary(session, user_id)
    return target.rw_id if target is not None else None


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
            if "miniapp" in p.surfaces
        ]
    )


@router.get("/balance")
async def get_credit_balance(tg: TgUser = Depends(get_tg_user)):
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg.tg_id)
        if not user:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user not registered")
        balance = await _repo_balance.get_balance(session, user.id)
        return {"balance": balance}


@router.post("/pay-credits", response_model=PayCreditsResponse)
@limiter.limit("10/minute")
async def pay_with_credits(
    request: Request,
    body: PayCreditsRequest,
    tg: TgUser = Depends(get_tg_user),
) -> PayCreditsResponse:
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg.tg_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not registered")
    if user.is_banned:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "user is banned")

    target_rw_id = await _purchase_target_rw_id(
        user_id=user.id, subscription_id=body.subscription_id
    )

    node = await load_menu_node(body.node_id)
    if node is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "menu node not found")

    invoice_data = invoice_from_node(node)
    if invoice_data is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "menu node is not a valid invoice tariff",
        )

    days = invoice_data["days"]
    points_cost = await resolve_points_cost(invoice_data)
    async with async_session() as session:
        balance = await _repo_balance.get_balance(session, user.id)

    if balance < points_cost:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "insufficient_credits",
                "need": points_cost,
                "have": balance,
            },
        )

    result = await pay_and_deliver(
        user_id=user.id,
        tg_id=tg.tg_id,
        username=tg.username or f"id_{tg.tg_id}",
        points_cost=points_cost,
        days=days,
        tariff_slug=invoice_data["tariff_slug"],
        delivery_target=invoice_data,
        android_user_id=None,
        purchase_source="miniapp",
        email=user.email,
        target_rw_id=target_rw_id,
    )

    if result.get("status") != "success":
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            result.get("message", "delivery failed"),
        )

    return PayCreditsResponse(
        ok=True,
        transaction_id=result.get("transaction_id"),
        points_spent=result.get("points_spent"),
        points_cost=points_cost,
        credits_spent=result.get("credits_spent"),
        balance_after=result.get("balance_after"),
        subscription_url=result.get("subscription_url"),
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

    target_rw_id = await _purchase_target_rw_id(
        user_id=user.id, subscription_id=body.subscription_id
    )

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
        provider = validate_provider_invoice(
            invoice_data["provider"],
            currency=invoice_data["currency"],
            method=invoice_data["method"],
            surface="miniapp",
        )
    except PaymentError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    invoice_amount = invoice_data["amount"]

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
    except Exception as e:
        logger.exception("unexpected invoice failure")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"invoice failed: {e}")

    async with async_session() as session:
        session.add(
            Transaction(
                transaction_id=transaction_id,
                provider_invoice_id=invoice.invoice_id,
                vless_uuid="None",
                username=tg.username or f"id_{tg.tg_id}",
                order_status="created",
                delivery_status=0,
                days_ordered=invoice_data["days"],
                user_id=user.id,
                payment_method=provider.payment_method,
                amount=float(invoice_amount),
                created_at=_now_iso(),
                squad_id=invoice_data["squad_id"],
                internal_squad_ids=invoice_data["internal_squad_ids"],
                external_squad_id=invoice_data["external_squad_id"],
                traffic_limit_bytes=invoice_data["traffic_limit_bytes"],
                traffic_limit_strategy=invoice_data["traffic_limit_strategy"],
                remnawave_description=invoice_data["remnawave_description"],
                remnawave_tag=invoice_data["remnawave_tag"],
                android_user_id=None,
                target_rw_id=target_rw_id,
                purchase_source="miniapp",
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
        f"tx: <code>{esc(transaction_id)}</code>"
    )

    return InvoiceResponse(
        provider=provider.name,
        invoice_id=invoice.invoice_id,
        url=invoice.url,
        amount=invoice.amount,
        currency=invoice.currency,
        transaction_id=transaction_id,
        payment_method=provider.payment_method,
    )
