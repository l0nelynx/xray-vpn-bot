"""Web portal backend router.

Provides three groups of endpoints:

1. Invite-code validation
   POST /api/web/validate-invite — check a code without consuming it;
       rate-limited (5/min per IP) + in-memory brute-force guard.

2. Web registration
   POST /api/web/register — create account + auto-activate promo discount;
       requires a valid invite code; rate-limited (3/min per IP).

3. Discount-aware payment endpoints
   GET  /api/web/payments/menu    — tariff tree with prices discounted for
       the authenticated user's active promo redemption.
   POST /api/web/payments/invoice — create an invoice at the discounted
       price; stored in `transactions` like an android invoice.

All other auth/data endpoints (login, refresh, email verification, /me,
/devices, /sessions, /transactions) are the existing android routes
at /api/android/... and are reused unchanged by the web client.

Discount accounting for web users:
  Web-only users have no Telegram ID (tg_id IS NULL). The promo system
  uses tg_id as its user key. To avoid a DB migration we store promo
  redemptions with a synthetic tg_id = -user.id (negative values never
  collide with real Telegram IDs which are always positive).
"""
from __future__ import annotations

import base64
import hashlib
import json as _json
import logging
import secrets
import time
import urllib.parse
import uuid
from datetime import datetime, timezone

import httpx
import jwt as _pyjwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from jwt import PyJWKClient as _PyJWKClient
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ..android import deps
from ..android import repo as android_repo
from ..android import security as android_security
from ..android.auth_router import _issue_pair, _user_summary, limiter
from ..android.payments_router import _load_menu_rows, _load_node, _node_payload
from ..bonus_points import enrich_invoice_dict, resolve_points_cost
from ..android.schemas import AuthResponse, UserSummary
from ..database.session import async_session
from ..database.models import Transaction
from ..config import get_bot_token, get_config, get_tg_client_secret
from payments.rub_pricing import get_rub_rates_for_currencies
from ..notify_log import esc, notify_log, notify_web
from remnawave_client.api import get_user_from_username as _rw_get_by_username
from payments import (
    InvoiceRequest,
    PaymentError,
    create_invoice,
    validate_provider_invoice,
)
from . import brute_force
from common_db.repo import balance as _repo_balance
from common_db.repo import promos as _repo_promos
from common_db.repo import system as _repo_system

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/web", tags=["web-portal"])

# PKCE state store: state_token → {code_verifier, redirect_uri, expires_ts}
# Entries expire after 10 minutes and are cleaned up lazily.
_pkce_store: dict[str, dict] = {}
_PKCE_TTL = 600

# JWKS client — fetches Telegram's public keys on first use, then caches them.
_tg_jwks: _PyJWKClient | None = None


def _get_tg_jwks() -> _PyJWKClient:
    global _tg_jwks
    if _tg_jwks is None:
        _tg_jwks = _PyJWKClient("https://oauth.telegram.org/.well-known/jwks.json")
    return _tg_jwks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _client_ip(request: Request) -> str:
    # Real client IP via the trusted edge (X-Real-IP), not the nginx socket peer.
    # Keeps the brute-force guard per-attacker instead of one shared global bucket.
    return deps.real_client_ip(request)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fake_tg_id(user_id: int) -> int:
    """Synthetic tg_id for a web-only user — always negative."""
    return -int(user_id)


def _promo_tg_id(user: android_repo.UserRow) -> int:
    """Key used to look up this user's promo/discount state.

    Promos are keyed by tg_id everywhere (miniapp, bot). A web account with a
    linked Telegram must use that *real* tg_id here too, or it ends up
    reading/writing a completely separate, synthetic row that miniapp/bot
    never touch — the synthetic key is only for genuinely tg_id-less
    web-only accounts.
    """
    return user.tg_id if user.tg_id is not None else _fake_tg_id(user.id)


async def _resolve_credit_grant_for_promo(promo) -> int:
    if promo.credit_grant is not None:
        return promo.credit_grant
    async with async_session() as session:
        return await _repo_system.get_default_credit_grant(session)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ValidateInviteRequest(BaseModel):
    invite_code: str = Field(min_length=1, max_length=20)


class ValidateInviteResponse(BaseModel):
    valid: bool
    credit_grant: int | None = None
    promo_type: str | None = None


class WebRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    invite_code: str = Field(min_length=1, max_length=20)


class PartnershipInquiryRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    contact: str = Field(min_length=1, max_length=200)


class PartnershipInquiryResponse(BaseModel):
    ok: bool


class WebMenuInvoice(BaseModel):
    provider: str
    amount: float
    original_amount: float
    currency: str
    method: str | None
    days: int
    tariff_slug: str
    points_cost: int


class WebMenuNode(BaseModel):
    id: int
    parent_id: int | None
    text: str
    action: str | None
    invoice: WebMenuInvoice | None
    children: list["WebMenuNode"]


class WebMenuResponse(BaseModel):
    tree: list[WebMenuNode]
    balance: int


class WebInvoiceRequest(BaseModel):
    node_id: int = Field(..., ge=1)
    description: str | None = None


class TelegramExchangeRequest(BaseModel):
    code: str
    state: str


class WebInvoiceResponse(BaseModel):
    provider: str
    invoice_id: str
    url: str
    amount: float
    original_amount: float
    currency: str
    transaction_id: str
    payment_method: str


class WebPayCreditsRequest(BaseModel):
    node_id: int = Field(..., ge=1)


class WebPayCreditsResponse(BaseModel):
    ok: bool
    transaction_id: str | None = None
    points_spent: int | None = None
    points_cost: int | None = None
    credits_spent: int | None = None
    balance_after: int | None = None
    subscription_url: str | None = None
    message: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/validate-invite", response_model=ValidateInviteResponse)
@limiter.limit("5/minute")
async def validate_invite(
    body: ValidateInviteRequest,
    request: Request,
) -> ValidateInviteResponse:
    """Return whether the invite code is valid (discount info on success).

    In addition to the slowapi 5/min rate limit, an in-memory brute-force
    guard blocks IPs that accumulate 20 failures within one hour for 24 h.
    Successful lookups reset the failure counter for the IP.
    """
    ip = _client_ip(request)
    brute_force.check(ip)

    code = body.invite_code.strip().upper()
    async with async_session() as session:
        promo = await _repo_promos.get_promo_by_code(session, code)
        if promo is None:
            brute_force.record_fail(ip)
            return ValidateInviteResponse(valid=False)
        discount = await _resolve_credit_grant_for_promo(promo)

    brute_force.clear(ip)
    return ValidateInviteResponse(
        valid=True,
        credit_grant=discount,
        promo_type=promo.promo_type,
    )


@router.post("/partnership-inquiry", response_model=PartnershipInquiryResponse)
@limiter.limit("3/hour")
async def partnership_inquiry(
    body: PartnershipInquiryRequest,
    request: Request,
) -> PartnershipInquiryResponse:
    """Accept a business/partnership inquiry from the public landing page and
    forward it to the `web_id` Telegram chat.

    Unauthenticated + rate-limited (3/hour per IP). If `web_id` is not
    configured the submission is accepted but silently dropped (notify_web
    no-ops), so the landing form never surfaces a server misconfiguration.
    """
    ip = _client_ip(request)
    goal = body.goal.strip()
    description = body.description.strip()
    contact = body.contact.strip()

    await notify_web(
        "🤝 <b>Partnership inquiry</b>\n"
        f"<b>Goal:</b> {esc(goal)}\n"
        f"<b>Contact:</b> {esc(contact)}\n"
        f"<b>IP:</b> <code>{esc(ip)}</code>\n\n"
        f"{esc(description)}"
    )
    return PartnershipInquiryResponse(ok=True)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def web_register(
    body: WebRegisterRequest,
    request: Request,
) -> AuthResponse:
    """Register a new account requiring a valid invite code.

    Flow:
      1. Brute-force + rate-limit check.
      2. Validate invite code (code must exist; any type accepted).
      3. Create user with hashed password.
      4. Record a PromoRedemption with tg_id = -user.id so the discount
         is applied when the user creates their first payment invoice.
      5. Issue access + refresh token pair.
    """
    ip = _client_ip(request)
    brute_force.check(ip)

    code = body.invite_code.strip().upper()

    async with async_session() as session:
        promo = await _repo_promos.get_promo_by_code(session, code)
        if promo is None:
            brute_force.record_fail(ip)
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": "invalid_invite"},
            )
        grant = await _resolve_credit_grant_for_promo(promo)

    brute_force.clear(ip)

    pwd_hash = await android_security.hash_password(body.password)
    try:
        user_id = await android_repo.create_user_with_password(str(body.email), pwd_hash)
    except IntegrityError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "email_taken"},
        )

    user = await android_repo.find_user_by_id(user_id)
    assert user is not None

    fake_tg = _fake_tg_id(user_id)
    async with async_session() as session:
        redeem_result = await _repo_promos.redeem_promo(session, fake_tg, code)
        if not redeem_result.ok:
            await session.rollback()
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": "invalid_invite"},
            )
        await session.commit()

    tokens = await _issue_pair(user_id, request)
    _, ip_log = deps.client_meta(request)
    await notify_log(
        f"🌐 <b>Web registration</b>\n"
        f"ID: <code>{user_id}</code>\n"
        f"email: <code>{esc(user.email)}</code>\n"
        f"invite: <code>{esc(code)}</code> (+{grant} credits)\n"
        f"IP: <code>{esc(ip_log or '—')}</code>"
    )
    return AuthResponse(tokens=tokens, user=_user_summary(user))


@router.get("/payments/menu", response_model=WebMenuResponse)
async def web_payments_menu(
    user: android_repo.UserRow = Depends(deps.get_current_user),
) -> WebMenuResponse:
    """Tariff tree with user's bonus credit balance."""
    async with async_session() as session:
        balance = await _repo_balance.get_balance(session, user.id)

    rows = await _load_menu_rows()
    currencies = [
        str(r.get("invoice_currency") or "RUB")
        for r in rows
        if r.get("action") == "invoice"
    ]
    rates = await get_rub_rates_for_currencies(currencies, get_config())

    async def _build(parent_id) -> list[dict]:
        items = sorted(
            [r for r in rows if r["parent_id"] == parent_id],
            key=lambda r: (r["sort_order"], r["id"]),
        )
        out: list[dict] = []
        for r in items:
            children = await _build(r["id"])
            inv_raw = _node_payload(r, surface="web")
            if r["action"] == "invoice" and inv_raw is None:
                continue
            if r["action"] != "invoice" and not children and inv_raw is None:
                continue
            orig = float(inv_raw["amount"]) if inv_raw else 0
            inv = None
            if inv_raw:
                enriched = await enrich_invoice_dict(inv_raw, rates)
                inv = {
                    "provider": enriched["provider"],
                    "amount": orig,
                    "original_amount": orig,
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
                    "text": (
                        (r["text_en"] or r["text_ru"])
                        if user.language == "en"
                        else (r["text_ru"] or r["text_en"])
                    ),
                    "action": r["action"],
                    "invoice": inv,
                    "children": children,
                }
            )
        return out

    tree = await _build(None)
    return WebMenuResponse(
        tree=[WebMenuNode(**n) for n in tree],
        balance=balance,
    )


@router.post("/payments/invoice", response_model=WebInvoiceResponse)
@limiter.limit("10/minute")
async def web_invoice(
    body: WebInvoiceRequest,
    request: Request,
    user: android_repo.UserRow = Depends(deps.require_verified_email),
) -> WebInvoiceResponse:
    """Create a payment invoice at full price (no promo discount)."""
    node = await _load_node(body.node_id)
    if node is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "node_not_found"})

    invoice_data = _node_payload(node, surface="web")
    if invoice_data is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "node_not_invoice"})

    try:
        provider = validate_provider_invoice(
            invoice_data["provider"],
            currency=invoice_data["currency"],
            method=invoice_data["method"],
            surface="web",
        )
    except PaymentError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"code": "provider_unavailable"}
        ) from exc

    if invoice_data["amount"] <= 0 or invoice_data["days"] <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "node_misconfigured"})

    original_amount = float(invoice_data["amount"])
    final_amount = original_amount

    transaction_id = str(uuid.uuid4())
    invoice_req = InvoiceRequest(
        transaction_id=transaction_id,
        amount=final_amount,
        currency=invoice_data["currency"],
        days=invoice_data["days"],
        user_tg_id=_promo_tg_id(user),
        username=user.email,
        description=body.description or f"WebUser:{user.id}",
        method=invoice_data["method"],
    )

    try:
        invoice = await create_invoice(provider.name, invoice_req)
    except PaymentError as exc:
        logger.warning(
            "web invoice failed (provider=%s node=%s): %s", provider.name, body.node_id, exc
        )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail={"code": "invoice_failed"}) from exc

    async with async_session() as session:
        session.add(
            Transaction(
                transaction_id=transaction_id,
                provider_invoice_id=invoice.invoice_id,
                vless_uuid="None",
                username=user.email or f"webuser_{user.id}",
                order_status="created",
                delivery_status=0,
                payment_method=provider.payment_method,
                amount=final_amount,
                created_at=_now_iso(),
                days_ordered=invoice_data["days"],
                squad_id=invoice_data["squad_id"],
                internal_squad_ids=invoice_data["internal_squad_ids"],
                external_squad_id=invoice_data["external_squad_id"],
                traffic_limit_bytes=invoice_data["traffic_limit_bytes"],
                traffic_limit_strategy=invoice_data["traffic_limit_strategy"],
                remnawave_description=invoice_data["remnawave_description"],
                remnawave_tag=invoice_data["remnawave_tag"],
                user_id=user.id,
                android_user_id=user.id,
            )
        )
        await session.commit()

    await notify_log(
        f"🌐🧾 <b>Invoice (Web)</b>\n"
        f"user: <code>{user.id}</code> {esc(user.email or '')}\n"
        f"amount: <code>{final_amount} {esc(invoice_data['currency'])}</code>\n"
        f"days: <code>{invoice_data['days']}</code>\n"
        f"tx: <code>{esc(transaction_id)}</code>"
    )

    return WebInvoiceResponse(
        provider=provider.name,
        invoice_id=invoice.invoice_id,
        url=invoice.url,
        amount=final_amount,
        original_amount=original_amount,
        currency=invoice.currency,
        transaction_id=transaction_id,
        payment_method=provider.payment_method,
    )


@router.post("/payments/pay-credits", response_model=WebPayCreditsResponse)
@limiter.limit("10/minute")
async def web_pay_credits(
    body: WebPayCreditsRequest,
    request: Request,
    user: android_repo.UserRow = Depends(deps.require_verified_email),
) -> WebPayCreditsResponse:
    from ..credits_delivery import pay_and_deliver

    node = await _load_node(body.node_id)
    if node is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "node_not_found"})

    invoice_data = _node_payload(node, surface="web")
    if invoice_data is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "node_not_invoice"})

    days = invoice_data["days"]
    points_cost = await resolve_points_cost(invoice_data)
    async with async_session() as session:
        balance = await _repo_balance.get_balance(session, user.id)
    if balance < points_cost:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": "insufficient_credits", "need": points_cost, "have": balance},
        )

    promo_tg_id = _promo_tg_id(user)
    result = await pay_and_deliver(
        user_id=user.id,
        tg_id=user.tg_id,
        username=user.email or f"webuser_{user.id}",
        points_cost=points_cost,
        days=days,
        tariff_slug=invoice_data["tariff_slug"],
        delivery_target=invoice_data,
        android_user_id=user.id if user.tg_id is None else None,
        email=user.email,
        referral_tg_id=_promo_tg_id(user),
    )
    if result.get("status") != "success":
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail={"code": result.get("message", "delivery_failed")},
        )
    return WebPayCreditsResponse(
        ok=True,
        transaction_id=result.get("transaction_id"),
        points_spent=result.get("points_spent"),
        points_cost=points_cost,
        credits_spent=result.get("credits_spent"),
        balance_after=result.get("balance_after"),
        subscription_url=result.get("subscription_url"),
    )


@router.get("/auth/telegram/init")
@limiter.limit("20/minute")
async def telegram_auth_init(request: Request, redirect_uri: str) -> dict:
    """Generate PKCE pair + state and return the Telegram OIDC authorization URL.

    The frontend opens this URL in a popup; Telegram redirects to redirect_uri
    with ?code=...&state=... after the user authorizes.
    """
    bot_token = get_bot_token()
    bot_id = bot_token.split(":")[0] if bot_token else ""
    if not bot_id or not get_tg_client_secret():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "tg_auth_unavailable"},
        )

    # Lazy cleanup of expired entries
    now_ts = time.time()
    for k in [s for s, v in _pkce_store.items() if v["expires"] < now_ts]:
        del _pkce_store[k]

    # PKCE S256
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()

    state = secrets.token_hex(16)
    _pkce_store[state] = {
        "code_verifier": verifier,
        "redirect_uri": redirect_uri,
        "expires": now_ts + _PKCE_TTL,
    }

    params = urllib.parse.urlencode({
        "client_id": bot_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid profile",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return {"auth_url": f"https://oauth.telegram.org/auth?{params}"}


@router.post("/auth/telegram/exchange", response_model=AuthResponse)
@limiter.limit("10/minute")
async def telegram_auth_exchange(
    body: TelegramExchangeRequest,
    request: Request,
) -> AuthResponse:
    """Complete Telegram OIDC login: exchange code → tokens → verify id_token → issue JWT."""
    entry = _pkce_store.pop(body.state, None)
    if entry is None or entry["expires"] < time.time():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_state"},
        )

    bot_token = get_bot_token()
    bot_id = bot_token.split(":")[0] if bot_token else ""
    client_secret = get_tg_client_secret()

    # Exchange authorization code for id_token
    credentials = base64.b64encode(f"{bot_id}:{client_secret}".encode()).decode()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://oauth.telegram.org/token",
                data={
                    "grant_type": "authorization_code",
                    "code": body.code,
                    "redirect_uri": entry["redirect_uri"],
                    "client_id": bot_id,
                    "code_verifier": entry["code_verifier"],
                },
                headers={"Authorization": f"Basic {credentials}"},
            )
    except httpx.HTTPError as exc:
        logger.warning("Telegram token endpoint unreachable: %s", exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail={"code": "tg_exchange_failed"},
        ) from exc

    if resp.status_code != 200:
        logger.warning("Telegram token exchange %s: %s", resp.status_code, resp.text)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "tg_exchange_failed"},
        )

    id_token = resp.json().get("id_token")
    if not id_token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "tg_no_id_token"},
        )

    # Verify id_token signature and claims with Telegram's JWKS
    try:
        signing_key = _get_tg_jwks().get_signing_key_from_jwt(id_token)
        claims = _pyjwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=str(bot_id),
            issuer="https://oauth.telegram.org",
        )
    except Exception as exc:
        logger.warning("Telegram id_token invalid: %s", exc)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_tg_token"},
        ) from exc

    # Telegram OIDC JWT fields (per https://core.telegram.org/bots/telegram-login):
    #   `sub`  — opaque OIDC subject, NOT the bot-API user ID
    #   `id`   — actual Telegram numeric user ID (same as message.from_user.id in bot)
    #   `preferred_username` — Telegram @username
    tg_id: int | None = int(claims["id"]) if claims.get("id") else None
    tg_username: str | None = (
        claims.get("preferred_username") or claims.get("username") or ""
    ).lstrip("@").strip() or None

    logger.info(
        "Telegram OIDC exchange: id=%s username=%s sub=%s",
        tg_id, tg_username, claims.get("sub"),
    )

    user = None

    # ── 1. Primary: exact tg_id match — the `id` claim IS the bot-API user ID.
    if tg_id:
        user = await android_repo.find_user_by_tg_id(tg_id)
        if user:
            logger.info("Telegram OIDC: found user_id=%s by tg_id=%s", user.id, tg_id)

    # ── 2. Fallback: Telegram @username (case-insensitive) in users.username.
    #       Covers web-portal users whose tg_id column is still NULL.
    if user is None and tg_username:
        user = await android_repo.find_user_by_username_ci(tg_username)
        if user:
            logger.info(
                "Telegram OIDC: found user_id=%s by @username=%s", user.id, tg_username
            )

    # ── 3. Last resort: Remnawave lookup by @username → vless_uuid → users row.
    if user is None and tg_username:
        try:
            _rw = await _rw_get_by_username(tg_username)
        except Exception:
            _rw = None
        if _rw:
            _uuid = _rw.get("uuid")
            if _uuid:
                user = await android_repo.find_user_by_vless_uuid(_uuid)
                if user:
                    logger.info(
                        "Telegram OIDC: found user_id=%s via Remnawave uuid=%s",
                        user.id, _uuid,
                    )

    if user is None:
        logger.warning(
            "Telegram OIDC: no user found — tg_id=%s username=%s",
            tg_id, tg_username,
        )
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "tg_not_registered"},
        )

    if user.is_banned:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "banned"},
        )

    # Fallback paths 2/3 find the user by username/Remnawave-uuid without
    # tg_id being set on the row yet — persist the link now. Telegram's own
    # OIDC signature already proves ownership of this tg_id, so this is safe;
    # never overwrite an existing link (path 1 already handles that case).
    if tg_id is not None and user.tg_id is None:
        await android_repo.set_user_tg_id(user.id, tg_id)
        user.tg_id = tg_id

    if user.email_verified_at is None:
        await android_repo.mark_email_verified(user.id)

    tokens = await _issue_pair(user.id, request)

    _, ip_log = deps.client_meta(request)
    await notify_log(
        f"🌐🔑 <b>Telegram OIDC login (Web)</b>\n"
        f"@username: <code>{esc(tg_username or '—')}</code>\n"
        f"user_id: <code>{user.id}</code>\n"
        f"IP: <code>{esc(ip_log or '—')}</code>"
    )

    return AuthResponse(
        tokens=tokens,
        user=UserSummary(
            id=user.id,
            email=user.email,
            email_verified=True,
            has_password=user.password_hash is not None,
            has_telegram=user.tg_id is not None,
        ),
    )


# ── Credential setup for Telegram-only users ──────────────────────────────────
#
# Two flows:
#   A) No email, no password  → /setup/email-request + /setup/email-confirm
#   B) Has email, no password → /setup/password-request + /setup/password-confirm


class SetupEmailRequest(BaseModel):
    email: EmailStr
    new_password: str = Field(min_length=8, max_length=128)


class SetupEmailConfirm(BaseModel):
    code: str = Field(min_length=4, max_length=12)


class SetupPasswordConfirm(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)
    code: str = Field(min_length=4, max_length=12)


@router.post("/auth/setup/email-request")
@limiter.limit("3/minute")
async def setup_email_request(
    body: SetupEmailRequest,
    request: Request,
    user: android_repo.UserRow = Depends(deps.get_current_user),
) -> dict:
    """Step 1 for users with no email: validate email, store password hash in code
    payload, send verification code to the new email."""
    if user.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "email_already_set"})

    new_email = str(body.email).strip().lower()
    other = await android_repo.find_user_by_email(new_email)
    if other is not None and other.id != user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "email_taken"})

    from ..android import mailer, security as _sec
    from ..config import get_email_code_ttl_seconds

    password_hash = await _sec.hash_password(body.new_password)
    payload = _json.dumps({"email": new_email, "ph": password_hash})

    code = _sec.new_email_code()
    code_hash = _sec.hash_email_code(code)
    await android_repo.invalidate_pending_codes(user.id, android_repo.PURPOSE_SETUP_EMAIL)
    await android_repo.store_verification_code(
        user_id=user.id,
        purpose=android_repo.PURPOSE_SETUP_EMAIL,
        code_hash=code_hash,
        payload=payload,
        ttl_seconds=get_email_code_ttl_seconds(),
    )
    try:
        subject, text_body = mailer.render_verify(code)
        await mailer.send_email(to=new_email, subject=subject, text=text_body)
    except mailer.MailerError as exc:
        logger.error("setup_email_request: send to %s failed: %s", new_email, exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail={"code": "email_send_failed"}
        ) from exc

    return {"status": "ok"}


@router.post("/auth/setup/email-confirm")
@limiter.limit("10/minute")
async def setup_email_confirm(
    body: SetupEmailConfirm,
    request: Request,
    user: android_repo.UserRow = Depends(deps.get_current_user),
) -> dict:
    """Step 2: verify the code, then atomically set email + password + verified_at."""
    if user.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "email_already_set"})

    from ..android import security as _sec

    row = await android_repo.find_active_code(user.id, android_repo.PURPOSE_SETUP_EMAIL)
    if row is None or row.expires_at <= _datetime_now_iso():
        if row:
            await android_repo.mark_code_used(row.id)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "code_expired"})

    if row.attempts >= _get_max_attempts():
        await android_repo.mark_code_used(row.id)
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail={"code": "code_exhausted"})

    if not _sec.constant_time_code_eq(row.code_hash, body.code):
        attempts = await android_repo.increment_code_attempts(row.id)
        if attempts >= _get_max_attempts():
            await android_repo.mark_code_used(row.id)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "code_invalid"})

    await android_repo.mark_code_used(row.id)

    try:
        data = _json.loads(row.payload or "{}")
        new_email = data["email"]
        password_hash = data["ph"]
    except (ValueError, KeyError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "code_invalid"}) from exc

    # Last-second collision check
    other = await android_repo.find_user_by_email(new_email)
    if other is not None and other.id != user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "email_taken"})

    await android_repo.set_email_with_password(user.id, new_email, password_hash)
    await notify_log(
        f"🔐 <b>Email+password set (Web)</b>\n"
        f"user_id: <code>{user.id}</code>\n"
        f"email: <code>{esc(new_email)}</code>"
    )
    return {"status": "ok"}


@router.post("/auth/setup/password-request")
@limiter.limit("3/minute")
async def setup_password_request(
    request: Request,
    user: android_repo.UserRow = Depends(deps.get_current_user),
) -> dict:
    """Step 1 for users with email but no password: send code to existing email."""
    if not user.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "email_missing"})
    if user.password_hash:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "password_already_set"})

    from ..android import mailer, security as _sec
    from ..config import get_email_code_ttl_seconds

    code = _sec.new_email_code()
    code_hash = _sec.hash_email_code(code)
    await android_repo.invalidate_pending_codes(user.id, android_repo.PURPOSE_SETUP_PASSWORD)
    await android_repo.store_verification_code(
        user_id=user.id,
        purpose=android_repo.PURPOSE_SETUP_PASSWORD,
        code_hash=code_hash,
        payload=None,
        ttl_seconds=get_email_code_ttl_seconds(),
    )
    try:
        subject, text_body = mailer.render_verify(code)
        await mailer.send_email(to=user.email, subject=subject, text=text_body)
    except mailer.MailerError as exc:
        logger.error("setup_password_request: send to %s failed: %s", user.email, exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail={"code": "email_send_failed"}
        ) from exc

    return {"status": "ok"}


@router.post("/auth/setup/password-confirm")
@limiter.limit("10/minute")
async def setup_password_confirm(
    body: SetupPasswordConfirm,
    request: Request,
    user: android_repo.UserRow = Depends(deps.get_current_user),
) -> dict:
    """Step 2: verify the code, then set the password."""
    if not user.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "email_missing"})
    if user.password_hash:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "password_already_set"})

    from ..android import security as _sec

    row = await android_repo.find_active_code(user.id, android_repo.PURPOSE_SETUP_PASSWORD)
    if row is None or row.expires_at <= _datetime_now_iso():
        if row:
            await android_repo.mark_code_used(row.id)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "code_expired"})

    if row.attempts >= _get_max_attempts():
        await android_repo.mark_code_used(row.id)
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail={"code": "code_exhausted"})

    if not _sec.constant_time_code_eq(row.code_hash, body.code):
        attempts = await android_repo.increment_code_attempts(row.id)
        if attempts >= _get_max_attempts():
            await android_repo.mark_code_used(row.id)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "code_invalid"})

    await android_repo.mark_code_used(row.id)
    await android_repo.set_password(user.id, await _sec.hash_password(body.new_password))
    if not user.email_verified_at:
        await android_repo.mark_email_verified(user.id)

    await notify_log(
        f"🔐 <b>Password set (Web)</b>\n"
        f"user_id: <code>{user.id}</code>\n"
        f"email: <code>{esc(user.email or '—')}</code>"
    )
    return {"status": "ok"}


def _datetime_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _get_max_attempts() -> int:
    from ..config import get_email_code_max_attempts
    return get_email_code_max_attempts()
