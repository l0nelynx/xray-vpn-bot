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
from ..android.schemas import AuthResponse, UserSummary
from ..database.session import async_session
from ..config import get_bot_token, get_tg_client_secret
from ..notify_log import esc, notify_log
from ..remnawave_client import get_user_from_username as _rw_get_by_username
from ..payments import InvoiceRequest, PaymentError, create_invoice, get_provider
from . import brute_force
from common_db.models.promo_redemptions import PromoRedemption, REDEMPTION_ACTIVE
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
    return request.client.host if request.client else "unknown"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fake_tg_id(user_id: int) -> int:
    """Synthetic tg_id for a web-only user — always negative."""
    return -int(user_id)


async def _resolve_discount_for_promo(promo) -> int:
    """Cascade: promo.discount_percent (incl. explicit 0) → PromoSettings default."""
    if promo.discount_percent is not None:
        return promo.discount_percent
    async with async_session() as session:
        return await _repo_system.get_default_discount_percent(session)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ValidateInviteRequest(BaseModel):
    invite_code: str = Field(min_length=1, max_length=20)


class ValidateInviteResponse(BaseModel):
    valid: bool
    discount_percent: int | None = None
    promo_type: str | None = None


class WebRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    invite_code: str = Field(min_length=1, max_length=20)


class WebMenuInvoice(BaseModel):
    provider: str
    amount: float
    original_amount: float
    currency: str
    method: str | None
    days: int
    tariff_slug: str


class WebMenuNode(BaseModel):
    id: int
    parent_id: int | None
    text: str
    action: str | None
    invoice: WebMenuInvoice | None
    children: list["WebMenuNode"]


class WebMenuResponse(BaseModel):
    tree: list[WebMenuNode]
    discount_percent: int
    promo_code: str | None


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
    discount_percent: int
    currency: str
    transaction_id: str
    payment_method: str


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
        discount = await _resolve_discount_for_promo(promo)

    brute_force.clear(ip)
    return ValidateInviteResponse(
        valid=True,
        discount_percent=discount,
        promo_type=promo.promo_type,
    )


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
        discount = await _resolve_discount_for_promo(promo)
        promo_type = promo.promo_type

    brute_force.clear(ip)

    pwd_hash = android_security.hash_password(body.password)
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
        session.add(
            PromoRedemption(
                tg_id=fake_tg,
                promo_code=code,
                promo_type=promo_type,
                discount_percent=discount,
                status=REDEMPTION_ACTIVE,
                created_at=_now_iso(),
            )
        )
        await session.commit()

    tokens = await _issue_pair(user_id, request)
    _, ip_log = deps.client_meta(request)
    await notify_log(
        f"🌐 <b>Web registration</b>\n"
        f"ID: <code>{user_id}</code>\n"
        f"email: <code>{esc(user.email)}</code>\n"
        f"invite: <code>{esc(code)}</code> ({discount}% discount)\n"
        f"IP: <code>{esc(ip_log or '—')}</code>"
    )
    return AuthResponse(tokens=tokens, user=_user_summary(user))


@router.get("/payments/menu", response_model=WebMenuResponse)
async def web_payments_menu(
    user: android_repo.UserRow = Depends(deps.get_current_user),
) -> WebMenuResponse:
    """Tariff tree with prices discounted by the user's active promo."""
    fake_tg = _fake_tg_id(user.id)
    async with async_session() as session:
        discount_info = await _repo_promos.get_effective_discount(session, fake_tg)

    discount_pct = discount_info.discount_percent if discount_info else 0
    promo_code = discount_info.promo_code if discount_info else None

    rows = await _load_menu_rows()

    def _build(parent_id) -> list[dict]:
        items = sorted(
            [r for r in rows if r["parent_id"] == parent_id],
            key=lambda r: (r["sort_order"], r["id"]),
        )
        out: list[dict] = []
        for r in items:
            children = _build(r["id"])
            inv_raw = _node_payload(r)
            if r["action"] == "invoice" and inv_raw is None:
                continue
            if r["action"] != "invoice" and not children and inv_raw is None:
                continue
            orig = float(inv_raw["amount"]) if inv_raw else 0
            discounted = round(orig * (1 - discount_pct / 100), 2) if (inv_raw and discount_pct) else orig
            inv = (
                {
                    "provider": inv_raw["provider"],
                    "amount": discounted,
                    "original_amount": orig,
                    "currency": inv_raw["currency"],
                    "method": inv_raw["method"],
                    "days": inv_raw["days"],
                    "tariff_slug": inv_raw["tariff_slug"],
                }
                if inv_raw
                else None
            )
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

    tree = _build(None)
    return WebMenuResponse(
        tree=[WebMenuNode(**n) for n in tree],
        discount_percent=discount_pct,
        promo_code=promo_code,
    )


@router.post("/payments/invoice", response_model=WebInvoiceResponse)
@limiter.limit("10/minute")
async def web_invoice(
    body: WebInvoiceRequest,
    request: Request,
    user: android_repo.UserRow = Depends(deps.require_verified_email),
) -> WebInvoiceResponse:
    """Create a payment invoice with promo discount applied to the price."""
    node = await _load_node(body.node_id)
    if node is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "node_not_found"})

    invoice_data = _node_payload(node)
    if invoice_data is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "node_not_invoice"})

    try:
        provider = get_provider(invoice_data["provider"])
    except PaymentError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"code": "provider_unavailable"}
        ) from exc

    if invoice_data["amount"] <= 0 or invoice_data["days"] <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "node_misconfigured"})

    fake_tg = _fake_tg_id(user.id)
    async with async_session() as session:
        discount_info = await _repo_promos.get_effective_discount(session, fake_tg)

    discount_pct = discount_info.discount_percent if discount_info else 0
    original_amount = float(invoice_data["amount"])
    final_amount = round(original_amount * (1 - discount_pct / 100), 2) if discount_pct else original_amount

    transaction_id = str(uuid.uuid4())
    invoice_req = InvoiceRequest(
        transaction_id=transaction_id,
        amount=final_amount,
        currency=invoice_data["currency"],
        days=invoice_data["days"],
        user_tg_id=fake_tg,
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
                "uname": user.email or f"webuser_{user.id}",
                "pm": provider.payment_method,
                "amt": final_amount,
                "ts": _now_iso(),
                "days": invoice_data["days"],
                "slug": invoice_data["tariff_slug"],
                "uid": user.id,
                "aid": user.id,
            },
        )
        await session.commit()

    await notify_log(
        f"🌐🧾 <b>Invoice (Web)</b>\n"
        f"user: <code>{user.id}</code> {esc(user.email or '')}\n"
        f"amount: <code>{final_amount} {esc(invoice_data['currency'])}</code>"
        f" (orig {original_amount}, -{discount_pct}%)\n"
        f"days: <code>{invoice_data['days']}</code>\n"
        f"tx: <code>{esc(persisted_id)}</code>"
    )

    return WebInvoiceResponse(
        provider=provider.name,
        invoice_id=invoice.invoice_id,
        url=invoice.url,
        amount=final_amount,
        original_amount=original_amount,
        discount_percent=discount_pct,
        currency=invoice.currency,
        transaction_id=persisted_id,
        payment_method=provider.payment_method,
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
