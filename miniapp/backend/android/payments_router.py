"""External payment endpoints for the Android API.

Tariff source of truth: `webapp_menu_nodes` (Tariff Constructor in dashboard,
already consumed by miniapp via /api/menu/tree). Android клиент:

  1. GET  /menu      — получает дерево узлов (только апрувленные провайдеры)
  2. POST /invoice   — указывает только `node_id`; provider/amount/currency/
                       method/days/tariff_slug сервер достаёт из узла меню.

Клиент не знает и не передаёт ни цену, ни провайдера, ни slug — это критично
для безопасности: на мобильном клиенте всё, что приходит «снаружи», подменяемо.
Единственный source of truth — БД, редактируется в дашборде.
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
    """Android-клиент передаёт только id узла меню — provider/amount/
    currency/method/days/tariff_slug сервер достаёт сам из webapp_menu_nodes.
    Никакие тарифные параметры со стороны клиента не принимаются: всё, что
    хранится у клиента, подменяемо."""
    node_id: int = Field(..., ge=1)
    description: str | None = None


class AndroidMenuInvoice(BaseModel):
    provider: str
    amount: float
    currency: str
    method: str | None
    days: int
    tariff_slug: str


class AndroidMenuNode(BaseModel):
    id: int
    parent_id: int | None
    text: str
    action: str | None
    invoice: AndroidMenuInvoice | None
    children: list["AndroidMenuNode"]


class AndroidMenuResponse(BaseModel):
    tree: list[AndroidMenuNode]


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


async def _load_menu_rows() -> list[dict]:
    """Прочитать активные узлы меню из общей таблицы Tariff Constructor.
    Та же таблица, что используется miniapp `/api/menu/tree`."""
    async with async_session() as session:
        result = await session.execute(text(
            "SELECT id, parent_id, text, action, sort_order, "
            "invoice_provider, invoice_amount, invoice_currency, "
            "invoice_method, invoice_days, invoice_tariff_slug "
            "FROM webapp_menu_nodes WHERE is_active = 1"
        ))
        return [dict(r._mapping) for r in result.all()]


def _node_payload(row: dict) -> dict | None:
    """Превращает row из БД в AndroidMenuInvoice-словарь.
    Возвращает None, если у узла нет валидного invoice (не invoice action,
    или провайдер не разрешён для Android, или нет slug-а)."""
    if row["action"] != "invoice":
        return None
    provider = (row["invoice_provider"] or "").lower()
    if provider not in _ANDROID_PROVIDERS:
        return None
    slug = row["invoice_tariff_slug"]
    if not slug:
        return None
    return {
        "provider": provider,
        "amount": float(row["invoice_amount"] or 0),
        "currency": (row["invoice_currency"] or "RUB").upper(),
        "method": row["invoice_method"],
        "days": int(row["invoice_days"] or 0),
        "tariff_slug": slug,
    }


def _build_tree(rows: list[dict], parent_id: int | None) -> list[dict]:
    """Рекурсивный билд дерева. Узлы с action=invoice оставляем только если
    провайдер разрешён. Не-invoice узлы оставляем, только если у них есть
    хотя бы один валидный потомок (иначе пустые группы засоряли бы UI)."""
    items = sorted(
        [r for r in rows if r["parent_id"] == parent_id],
        key=lambda r: (r["sort_order"], r["id"]),
    )
    out: list[dict] = []
    for r in items:
        invoice = _node_payload(r)
        children = _build_tree(rows, r["id"])
        if r["action"] == "invoice" and invoice is None:
            continue  # инвойс с не-Android провайдером — режем целиком
        if r["action"] != "invoice" and not children and invoice is None:
            continue  # пустая ветка после фильтрации
        out.append({
            "id": r["id"],
            "parent_id": r["parent_id"],
            "text": r["text"],
            "action": r["action"],
            "invoice": invoice,
            "children": children,
        })
    return out


async def _load_node(node_id: int) -> dict | None:
    """Прочитать один активный узел меню по id."""
    async with async_session() as session:
        result = await session.execute(
            text(
                "SELECT id, parent_id, text, action, sort_order, "
                "invoice_provider, invoice_amount, invoice_currency, "
                "invoice_method, invoice_days, invoice_tariff_slug "
                "FROM webapp_menu_nodes WHERE id = :id AND is_active = 1"
            ),
            {"id": node_id},
        )
        row = result.first()
    return dict(row._mapping) if row is not None else None


# --- Endpoints -------------------------------------------------------------


@router.get("/menu", response_model=AndroidMenuResponse)
async def get_payments_menu(
    user: repo.UserRow = Depends(deps.get_current_user),
) -> AndroidMenuResponse:
    """Вернуть дерево тарифного меню из Tariff Constructor.

    Источник — таблица `webapp_menu_nodes` (та же, что для miniapp). Узлы
    с invoice-провайдерами не из `_ANDROID_PROVIDERS` отфильтровываются,
    как и пустые после фильтрации ветки. Аутентификация — стандартный
    Bearer (без verified-email-гейта, чтобы клиент мог показать тарифы
    до подтверждения email)."""
    rows = await _load_menu_rows()
    tree = _build_tree(rows, None)
    return AndroidMenuResponse(tree=[AndroidMenuNode(**n) for n in tree])


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
    node = await _load_node(body.node_id)
    if node is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail={"code": "node_not_found"}
        )

    invoice_data = _node_payload(node)
    if invoice_data is None:
        # Узел существует, но это либо группа (action != invoice), либо
        # invoice с провайдером не из Android-набора.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"code": "node_not_invoice"}
        )

    try:
        provider = get_provider(invoice_data["provider"])
    except PaymentError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"code": "provider_unavailable"}
        ) from exc

    if not provider.supports(invoice_data["currency"]):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "currency_unsupported"},
        )

    if invoice_data["amount"] <= 0 or invoice_data["days"] <= 0:
        # Tariff Constructor может временно содержать незаполненные узлы
        # (черновик в дашборде). Лучше явный 400, чем мутный 502 от провайдера.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "node_misconfigured"},
        )

    transaction_id = str(uuid.uuid4())
    invoice_req = InvoiceRequest(
        transaction_id=transaction_id,
        amount=invoice_data["amount"],
        currency=invoice_data["currency"],
        days=invoice_data["days"],
        # У Android-юзеров нет tg_id. Передаём -user.id, чтобы не пересечься
        # с настоящими tg_id; провайдеры используют это поле только для
        # описания/payload-тэга.
        user_tg_id=-int(user.id),
        username=user.email,
        description=body.description or f"AndroidUser:{user.id}",
        method=invoice_data["method"],
    )

    try:
        invoice = await create_invoice(provider.name, invoice_req)
    except PaymentError as exc:
        logger.warning(
            "android invoice creation failed (provider=%s node=%s slug=%s): %s",
            provider.name, body.node_id, invoice_data["tariff_slug"], exc,
        )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail={"code": "invoice_failed"}
        ) from exc
    except Exception as exc:  # defensive
        logger.exception("android: unexpected invoice failure")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail={"code": "invoice_failed"}
        ) from exc

    # Платежные провайдеры используют разные ключи в вебхуках:
    #  • Platega → transactionId, выданный самим Platega → используем его.
    #  • APay → отправляет мерчанту наш transaction_id обратно → наш uuid.
    persisted_id = invoice.invoice_id if provider.name == "platega" else transaction_id

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
                "amt": float(invoice_data["amount"]),
                "ts": _now_iso(),
                "days": invoice_data["days"],
                # Кладём настоящий slug из узла Tariff Constructor — Android-
                # доставка резолвит squad через get_squad_for_tariff_slug.
                "slug": invoice_data["tariff_slug"],
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
