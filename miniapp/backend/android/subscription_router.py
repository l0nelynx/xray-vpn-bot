"""Unauthenticated subscription-lookup + account-migration endpoints.

`/api/android/check-uuid` lets the app verify that a `short_uuid` collected
from a subscription link belongs to a real Remnawave user AND that the
caller knows the matching email/username — used during onboarding so the
client can confidently surface a "recover this subscription" flow.

`/api/android/migrate` performs the actual recovery: given the same proof
plus a target login (acc_email + password), it locates the matching row in
the local `users` table (priority: vless_uuid → username → email) and
binds Android credentials to it. If no local row exists yet, a new one is
created pre-bound to the Remnawave `vless_uuid`.

Both endpoints sit outside auth_router because they're intentionally
unauthenticated — they're the entry points to recovery, before the client
has any session at all. Rate-limited because every call costs a Remnawave
round-trip.
"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError

from ..notify_log import esc, notify_log
from ..remnawave_client import get_user_by_short_uuid_raw
from . import deps, repo, security
from .auth_router import _issue_pair, _user_summary, limiter
from .schemas import AuthResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/android", tags=["android-subscription"])

# Remnawave short_uuid is a URL-safe slug; in practice 8-32 chars. Allow a
# generous superset to avoid breaking on SDK changes, but reject anything
# that obviously can't be a slug (whitespace, slashes) so we don't forward
# nonsense to Remnawave.
_SHORT_UUID_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")


def _identifier_matches(identifier: str, rw_user: dict) -> bool:
    """Compare a caller-supplied identifier against the Remnawave DTO.

    Identifiers containing `@` are treated as emails (case-insensitive,
    whitespace-stripped); everything else is treated as a username
    (exact match — Remnawave usernames are case-sensitive).
    """
    ident = identifier.strip()
    if "@" in ident:
        rw_email = rw_user.get("email")
        return bool(rw_email) and rw_email.strip().lower() == ident.lower()
    rw_username = rw_user.get("username")
    return bool(rw_username) and rw_username == ident


class CheckUuidRequest(BaseModel):
    short_uuid: str = Field(..., min_length=6, max_length=64)
    identifier: str = Field(..., min_length=1, max_length=320)


class MigrateRequest(BaseModel):
    short_uuid: str = Field(..., min_length=6, max_length=64)
    identifier: str = Field(..., min_length=1, max_length=320)
    acc_email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


@router.post("/check-uuid")
@limiter.limit("10/minute")
async def check_uuid(req: CheckUuidRequest, request: Request) -> dict:
    """Return the full Remnawave SDK DTO for the user matching `short_uuid`,
    but only if the caller also presents a matching `identifier`
    (email or username — distinguished by presence of `@`).

    Response shape is exactly what `RemnawaveSDK.users.get_user_by_short_uuid`
    returns (model_dump with aliases). Errors:
      - 400 `bad_short_uuid` — slug format rejected before hitting Remnawave
      - 404 `not_found` — no Remnawave user owns this short_uuid
      - 403 `identifier_mismatch` — short_uuid exists, but identifier
        doesn't match its email/username
    """
    if not _SHORT_UUID_RE.match(req.short_uuid):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "bad_short_uuid"},
        )
    data = await get_user_by_short_uuid_raw(req.short_uuid)
    if data is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found"},
        )
    if not _identifier_matches(req.identifier, data):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "identifier_mismatch"},
        )
    return data


@router.post("/migrate", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def migrate(req: MigrateRequest, request: Request) -> AuthResponse:
    """Bind Android credentials (acc_email + password) to an existing
    Remnawave subscription.

    Ownership proof is the same as `/check-uuid`: the caller must know both
    the `short_uuid` and a matching `identifier` (email or username).

    Local-row resolution priority:
      1. `users.vless_uuid == rw.vlessUuid`
      2. `users.email`-derived username == rw.username
      3. `users.email == rw.email`

    Outcomes:
      - No local row found → create one with `email = acc_email`,
        `password_hash`, and `vless_uuid` pre-bound.
      - Local row found, has BOTH email and password → 409 `already_registered`.
      - Local row found, missing password (email may or may not be set) →
        fill in `email = acc_email`, `password_hash`, `vless_uuid`.

    `email_verified_at` is NEVER set here — the client must call the normal
    `/email/send-code` + `/email/verify` flow afterwards. That's also when
    free-provisioning would have triggered, but `email_verify` skips it
    when `vless_uuid` is already populated, so an existing paid Remnawave
    subscription is preserved.

    On success returns an `AuthResponse` identical to `/register`.
    """
    if not _SHORT_UUID_RE.match(req.short_uuid):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "bad_short_uuid"},
        )

    rw_data = await get_user_by_short_uuid_raw(req.short_uuid)
    if rw_data is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found"},
        )
    if not _identifier_matches(req.identifier, rw_data):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "identifier_mismatch"},
        )

    vless_uuid = rw_data.get("vlessUuid") or rw_data.get("uuid")
    if not vless_uuid:
        # Should be impossible — Remnawave always returns vlessUuid for an
        # active user — but guard so we don't write NULL into our column.
        logger.error("Remnawave DTO missing vlessUuid for short_uuid=%s", req.short_uuid)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail={"code": "upstream_invalid"},
        )

    rw_username = rw_data.get("username")
    rw_email = rw_data.get("email")

    user = await repo.find_user_by_vless_uuid(str(vless_uuid))
    if user is None and rw_username:
        user = await repo.find_user_by_remnawave_username(rw_username)
    if user is None and rw_email:
        user = await repo.find_user_by_email(rw_email)

    acc_email_normalized = str(req.acc_email).strip().lower()
    pwd_hash = security.hash_password(req.password)

    if user is None:
        # Greenfield: build a brand new row with credentials and pre-bound
        # subscription. Email collision with a *different* account is still
        # possible if acc_email belongs to someone else — treat that the
        # same as /register.
        try:
            user_id = await repo.create_user_with_password_and_vless(
                acc_email_normalized, pwd_hash, str(vless_uuid)
            )
        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "email_taken"},
            )
    else:
        # Existing row — only block if BOTH credentials are already filled.
        if user.email and user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "already_registered"},
            )
        # If the acc_email belongs to *another* row, we'd violate the unique
        # constraint when we try to write it here. Detect and surface the
        # same `email_taken` code so the client can prompt for a different
        # address.
        if user.email and user.email.lower() != acc_email_normalized:
            collision = await repo.find_user_by_email(acc_email_normalized)
            if collision is not None and collision.id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"code": "email_taken"},
                )
        elif not user.email:
            collision = await repo.find_user_by_email(acc_email_normalized)
            if collision is not None and collision.id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"code": "email_taken"},
                )
        try:
            await repo.adopt_user_for_migration(
                user.id, acc_email_normalized, pwd_hash, str(vless_uuid)
            )
        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "email_taken"},
            )
        user_id = user.id

    user_row = await repo.find_user_by_id(user_id)
    assert user_row is not None
    tokens = await _issue_pair(user_id, request)
    ua, ip = deps.client_meta(request)
    await notify_log(
        f"🔁 <b>Android migrate</b>\n"
        f"ID: <code>{user_id}</code>\n"
        f"email: <code>{esc(user_row.email)}</code>\n"
        f"vless: <code>{esc(str(vless_uuid))}</code>\n"
        f"IP: <code>{esc(ip or '—')}</code>\n"
        f"UA: <code>{esc((ua or '—')[:120])}</code>"
    )
    return AuthResponse(tokens=tokens, user=_user_summary(user_row))
