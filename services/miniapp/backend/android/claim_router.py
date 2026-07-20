"""Subscription claim flow — shortID-first onboarding.

Evolution of `/check-uuid` + `/migrate` (see subscription_router.py): the
client no longer needs to know the Remnawave identifier upfront. Instead:

  1. POST /claim/resolve   — short_uuid (or full subscription URL) →
     routing status + masked email hint + short-lived claim_token.
  2. POST /claim/otp-request — sends a 6-digit code to the canonical owner
     email (DB email, else Remnawave email).
  3. POST /claim/complete  — code + new credentials → AuthResponse.

Security model: the subscription URL is a weak bearer secret, so resolve is
a deliberate (rate-limited) oracle returning only a routing status and a
strongly masked hint. Session tokens are NEVER issued from the short_uuid
alone — every mutation requires either the account password
(`ready_login` → `/claim/login`) or proof of mailbox ownership via OTP
(when a deliverable owner email exists). Remnawave-only rows without a
mailbox can register+bind from URL possession alone; the new email is then
verified via the normal `/email/*` flow. The claim_token carries no PII;
each endpoint re-resolves current state from the slug.

Statuses:
  - ready_login    — DB row with email + password → /claim/login (password
                     only; email is already bound to the short_uuid).
  - needs_password — DB row with email, no password → OTP → set password.
  - rw_only        — Remnawave user without usable DB credentials → register
                     acc_email + password and bind vless_uuid. If a real
                     owner email exists (RW/DB), OTP to that address first;
                     otherwise possession of the subscription URL is enough
                     and the new email is verified via the normal flow.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy.exc import IntegrityError

from ..config import get_subscription_host
from ..notify_log import esc, notify_log
from remnawave_client.api import get_user_by_short_uuid_raw
from . import deps, mailer, repo, security
from .auth_router import _issue_pair, _user_summary, limiter
from .email_router import _consume_code, _send_code
from .schemas import AuthResponse, SimpleStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/android/claim", tags=["android-claim"])

_SHORT_UUID_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
# Good-enough sanity check for "can we actually deliver mail there" — the
# real proof is the OTP round-trip itself.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
# Placeholder addresses the bot writes into Remnawave when no real mailbox
# exists — not deliverable, so they must not trigger the OTP branch.
_SYNTHETIC_EMAIL_DOMAINS = frozenset({"bot.local", "miniapp.xyz"})

STATUS_READY_LOGIN = "ready_login"
STATUS_NEEDS_PASSWORD = "needs_password"
STATUS_RW_ONLY = "rw_only"


def _extract_short_uuid(url: str) -> str | None:
    """Strict URL → slug: https only, exact configured subscription host,
    single path segment. Mirrors android-link `by_url` validation."""
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    if parsed.scheme != "https" or parsed.netloc != get_subscription_host():
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) != 1 or not _SHORT_UUID_RE.match(parts[0]):
        return None
    return parts[0]


def _mask_email(email: str) -> str:
    """Fixed masking: `user@example.com` → `u***@ex***.com`. Reveals the
    first char of the local part, first two of the domain, and the TLD —
    enough for the owner to recognise the address, useless for guessing."""
    local, _, domain = email.strip().partition("@")
    dom_head, _, tld = domain.rpartition(".")
    if not dom_head:
        return f"{local[:1]}***@***"
    return f"{local[:1]}***@{dom_head[:2]}***.{tld}"


def _usable_email(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if not _EMAIL_RE.match(cleaned):
        return None
    domain = cleaned.rsplit("@", 1)[-1].lower()
    if domain in _SYNTHETIC_EMAIL_DOMAINS:
        return None
    return cleaned


class _Resolved:
    """Snapshot of RW + DB state for a short_uuid, shared by all endpoints."""

    def __init__(
        self,
        *,
        short_uuid: str,
        rw_data: dict,
        user: repo.UserRow | None,
    ) -> None:
        self.short_uuid = short_uuid
        self.rw_data = rw_data
        self.user = user
        self.vless_uuid = str(rw_data.get("vlessUuid") or rw_data.get("uuid") or "")
        # Username is often the real mailbox when the dedicated email field
        # is empty or filled with a synthetic placeholder.
        self.rw_email = _usable_email(rw_data.get("email")) or _usable_email(
            rw_data.get("username")
        )
        self.subscription_url = (
            rw_data.get("subscriptionUrl") or rw_data.get("subscription_url") or None
        )

        if user is not None and user.email and user.password_hash:
            self.status = STATUS_READY_LOGIN
            self.owner_email: str | None = user.email
        elif user is not None and user.email and not user.password_hash:
            self.status = STATUS_NEEDS_PASSWORD
            self.owner_email = user.email
        else:
            # Remnawave-only or bare TG/claim row without credentials:
            # client always opens registration + bind. OTP only when we
            # actually have a deliverable owner mailbox.
            self.status = STATUS_RW_ONLY
            self.owner_email = self.rw_email


async def _resolve_state(short_uuid: str) -> _Resolved:
    if not _SHORT_UUID_RE.match(short_uuid):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"code": "bad_short_uuid"}
        )
    rw_data = await get_user_by_short_uuid_raw(short_uuid)
    if rw_data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found"})

    vless_uuid = rw_data.get("vlessUuid") or rw_data.get("uuid")
    if not vless_uuid:
        logger.error("Remnawave DTO missing vlessUuid for short_uuid=%s", short_uuid)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail={"code": "upstream_invalid"}
        )

    # Prefer the row already bound to this Remnawave user. Username/email
    # fallbacks must not attach a foreign portal account that already owns a
    # different vless_uuid (otherwise ready_login would hijack the wrong row).
    user = await repo.find_user_by_vless_uuid(str(vless_uuid))
    if user is None and rw_data.get("username"):
        candidate = await repo.find_user_by_remnawave_username(rw_data["username"])
        if candidate is not None and (
            not candidate.vless_uuid or candidate.vless_uuid == str(vless_uuid)
        ):
            user = candidate
    if user is None and rw_data.get("email"):
        candidate = await repo.find_user_by_email(rw_data["email"])
        if candidate is not None and (
            not candidate.vless_uuid or candidate.vless_uuid == str(vless_uuid)
        ):
            user = candidate

    if user is not None and user.is_banned:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "banned"})

    return _Resolved(short_uuid=short_uuid, rw_data=rw_data, user=user)


def _short_uuid_from_claim_token(token: str) -> str:
    try:
        return security.decode_claim_token(token)
    except security.JWTError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail={"code": "bad_claim_token"}
        )


# --- Schemas -----------------------------------------------------------------


class ClaimResolveRequest(BaseModel):
    short_uuid: str | None = Field(None, min_length=6, max_length=64)
    url: str | None = Field(None, min_length=8, max_length=512)

    @model_validator(mode="after")
    def _one_of(self) -> "ClaimResolveRequest":
        if not self.short_uuid and not self.url:
            raise ValueError("short_uuid or url required")
        return self


class ClaimResolveResponse(BaseModel):
    status: str
    email_hint: str | None = None
    has_telegram: bool = False
    claim_token: str
    subscription_url: str | None = None
    # False when the bound row has credentials but email_verified_at is null
    # (client may offer "use a different email" rebind). True/False for
    # ready_login; False for needs_password/rw_only when no verified mailbox.
    email_verified: bool = False


class ClaimOtpRequest(BaseModel):
    claim_token: str = Field(min_length=10, max_length=2048)


class ClaimLoginRequest(BaseModel):
    claim_token: str = Field(min_length=10, max_length=2048)
    password: str = Field(min_length=1, max_length=128)


class ClaimCompleteRequest(BaseModel):
    claim_token: str = Field(min_length=10, max_length=2048)
    # Required when an owner mailbox exists (needs_password / rw_only+email).
    # Omitted for Remnawave-only registration where URL possession is enough.
    code: str | None = Field(None, min_length=4, max_length=12)
    new_password: str = Field(min_length=8, max_length=128)
    acc_email: EmailStr | None = None


# --- Endpoints ---------------------------------------------------------------


@router.post("/resolve", response_model=ClaimResolveResponse)
@limiter.limit("5/minute")
async def claim_resolve(
    req: ClaimResolveRequest, request: Request
) -> ClaimResolveResponse:
    """ShortID-first router: tell the client which onboarding branch applies.

    Deliberately an oracle for holders of the subscription URL (a weak
    bearer secret already) — hence the tight rate limit and the strongly
    masked hint. No session tokens are issued here.
    """
    short_uuid = req.short_uuid
    if not short_uuid and req.url:
        short_uuid = _extract_short_uuid(req.url)
        if short_uuid is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "invalid_url"}
            )
    assert short_uuid is not None

    resolved = await _resolve_state(short_uuid)
    return ClaimResolveResponse(
        status=resolved.status,
        email_hint=_mask_email(resolved.owner_email) if resolved.owner_email else None,
        has_telegram=bool(resolved.user and resolved.user.tg_id),
        claim_token=security.issue_claim_token(short_uuid),
        subscription_url=resolved.subscription_url,
        email_verified=bool(resolved.user and resolved.user.email_verified_at),
    )


@router.post("/login", response_model=AuthResponse)
@limiter.limit("10/minute")
async def claim_login(req: ClaimLoginRequest, request: Request) -> AuthResponse:
    """Password-only sign-in for `ready_login`.

    The claim_token already binds the flow to the subscription's DB row, so
    the client only confirms the password (email is shown as a masked hint).
    """
    short_uuid = _short_uuid_from_claim_token(req.claim_token)
    resolved = await _resolve_state(short_uuid)
    user = resolved.user

    if (
        resolved.status != STATUS_READY_LOGIN
        or user is None
        or not user.password_hash
    ):
        # Same opaque error as /auth/login — don't leak routing status here.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail={"code": "invalid_credentials"}
        )

    if not await security.verify_password(user.password_hash, req.password):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail={"code": "invalid_credentials"}
        )
    if user.is_banned:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail={"code": "banned"}
        )
    if security.needs_rehash(user.password_hash or ""):
        await repo.set_password(
            user.id, await security.hash_password(req.password)
        )

    tokens = await _issue_pair(user.id, request)
    return AuthResponse(tokens=tokens, user=_user_summary(user))


@router.post("/otp-request", response_model=SimpleStatus)
@limiter.limit("3/minute")
async def claim_otp_request(req: ClaimOtpRequest, request: Request) -> SimpleStatus:
    """Send the ownership code to the canonical owner email.

    For `rw_only` with no DB row yet, a bare credential-less row bound to
    the vless_uuid is created first — verification codes need a user_id
    anchor, and the row is exactly what a Telegram-created user looks like
    (idempotent: found by vless_uuid on every subsequent resolve).
    """
    short_uuid = _short_uuid_from_claim_token(req.claim_token)
    resolved = await _resolve_state(short_uuid)

    if resolved.status == STATUS_READY_LOGIN:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail={"code": "already_registered"}
        )
    if not resolved.owner_email:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"code": "email_missing"}
        )

    user = resolved.user
    if user is None:
        user_id = await repo.create_bare_user_with_vless(resolved.vless_uuid)
        user = await repo.find_user_by_id(user_id)
        assert user is not None

    await _send_code(
        user_id=user.id,
        purpose=repo.PURPOSE_CLAIM,
        to_email=resolved.owner_email,
        payload=resolved.owner_email.lower(),
        template=lambda code, _payload: mailer.render_verify(code),
    )
    return SimpleStatus()


@router.post("/complete", response_model=AuthResponse)
@limiter.limit("10/minute")
async def claim_complete(req: ClaimCompleteRequest, request: Request) -> AuthResponse:
    """Finish the claim: OTP (when required) + credentials → AuthResponse.

    - needs_password: set password on the existing row; the OTP round-trip
      to the account email doubles as email verification.
    - rw_only + owner email: adopt/fill after OTP proof of mailbox access.
      If acc_email matches the OTP address it is verified immediately;
      otherwise the normal /email/send-code + /verify flow follows.
    - rw_only without owner email: register + bind using subscription URL
      possession as ownership proof; new email stays unverified until the
      standard verify step. An abandoned (unverified) prior bind on the same
      vless_uuid is overwritten so a mistyped email can be corrected.
    - ready_login + unverified + acc_email: same overwrite without OTP
      (claim_token already proves subscription URL possession).
    """
    short_uuid = _short_uuid_from_claim_token(req.claim_token)
    resolved = await _resolve_state(short_uuid)
    user = resolved.user

    allow_unverified_rebind = (
        resolved.status == STATUS_READY_LOGIN
        and user is not None
        and not user.email_verified_at
        and req.acc_email is not None
    )
    if resolved.status == STATUS_READY_LOGIN and not allow_unverified_rebind:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail={"code": "already_registered"}
        )

    needs_otp = resolved.owner_email is not None and not allow_unverified_rebind
    otp_email = ""

    if needs_otp:
        if not req.code:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail={"code": "code_invalid"}
            )
        if user is None:
            # otp-request creates the anchor row; without it there is no
            # active code to consume.
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail={"code": "code_invalid"}
            )
        code_row = await _consume_code(
            user_id=user.id,
            purpose=repo.PURPOSE_CLAIM,
            presented_code=req.code,
        )
        otp_email = (code_row.payload or "").strip().lower()
    elif user is None:
        user_id = await repo.create_bare_user_with_vless(resolved.vless_uuid)
        user = await repo.find_user_by_id(user_id)
        assert user is not None

    pwd_hash = await security.hash_password(req.new_password)

    if resolved.status == STATUS_NEEDS_PASSWORD:
        await repo.set_password(user.id, pwd_hash)
        if not user.email_verified_at:
            await repo.mark_email_verified(user.id)
    else:  # rw_only or unverified ready_login rebind
        if req.acc_email is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail={"code": "acc_email_required"}
            )
        acc_email = str(req.acc_email).strip().lower()
        collision = await repo.find_user_by_email(acc_email)
        if collision is not None and collision.id != user.id:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail={"code": "email_taken"}
            )
        try:
            await repo.adopt_user_for_migration(
                user.id, acc_email, pwd_hash, resolved.vless_uuid
            )
        except IntegrityError:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail={"code": "email_taken"}
            )
        if needs_otp and acc_email == otp_email:
            await repo.mark_email_verified(user.id)

    user_row = await repo.find_user_by_id(user.id)
    assert user_row is not None
    tokens = await _issue_pair(user.id, request)
    ua, ip = deps.client_meta(request)
    await notify_log(
        f"🧀 <b>Subscription claim ({esc(resolved.status)})</b>\n"
        f"ID: <code>{user.id}</code>\n"
        f"email: <code>{esc(user_row.email or '—')}</code>\n"
        f"vless: <code>{esc(resolved.vless_uuid)}</code>\n"
        f"IP: <code>{esc(ip or '—')}</code>\n"
        f"UA: <code>{esc((ua or '—')[:120])}</code>"
    )
    return AuthResponse(tokens=tokens, user=_user_summary(user_row))
