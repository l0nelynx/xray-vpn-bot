"""PKCE SSO and signed subscription context for the subscription-page BFF."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import math
import re
import secrets
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from common_db.models import SubscriptionTransfer, WebAuthorizationCode
from common_db.repo import subscriptions as subscription_repo
from remnawave_client.api import get_user_by_short_uuid_raw, get_user_from_id, update_user_by_id

from ..android import deps, repo, security
from ..android.auth_router import limiter
from ..android.managed_subscriptions_router import _serialize
from ..android.schemas_subscriptions import (
    AttachSubscriptionRequest,
    AttachSubscriptionResponse,
    ManagedSubscriptionsResponse,
)
from ..config import get_subscription_page_oauth_redirect_uris
from ..database.session import async_session

router = APIRouter(prefix="/api/web", tags=["subscription-page-sso"])

_CLIENT_ID = "subscription-page"
_AUTH_CODE_TTL_SECONDS = 120
_SHORT_UUID_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
_PKCE_RE = re.compile(r"^[A-Za-z0-9_-]{43,128}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_client(client_id: str, redirect_uri: str) -> None:
    if client_id != _CLIENT_ID:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"code": "invalid_client"}
        )
    allowed = get_subscription_page_oauth_redirect_uris()
    if redirect_uri not in allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"code": "invalid_redirect_uri"}
        )


class SubscriptionContextRequest(BaseModel):
    short_uuid: str = Field(min_length=6, max_length=64)


class SubscriptionContextResponse(BaseModel):
    context: str
    rw_id: int
    expires_in: int = security.SUBSCRIPTION_CONTEXT_TTL_SECONDS


class AuthorizeRequest(BaseModel):
    client_id: str = Field(max_length=64)
    redirect_uri: str = Field(max_length=500)
    code_challenge: str = Field(min_length=43, max_length=128)
    code_challenge_method: str = "S256"
    state: str = Field(min_length=16, max_length=256)


class AuthorizeResponse(BaseModel):
    redirect_url: str


class TokenRequest(BaseModel):
    grant_type: str = "authorization_code"
    client_id: str = Field(max_length=64)
    redirect_uri: str = Field(max_length=500)
    code: str = Field(min_length=20, max_length=256)
    code_verifier: str = Field(min_length=43, max_length=128)


class TokenResponse(BaseModel):
    session_token: str
    token_type: str = "Bearer"
    expires_in: int


class SubscriptionSessionUser(BaseModel):
    id: int
    email: str | None
    has_telegram: bool


class TransferSubscriptionRequest(BaseModel):
    context: str = Field(min_length=20, max_length=4096)
    target_subscription_id: int = Field(ge=1)
    confirmed: bool


class TransferSubscriptionResponse(BaseModel):
    status: str
    days_transferred: int
    target_subscription_id: int


async def _subscription_session_user(
    authorization: str | None = Header(default=None),
) -> repo.UserRow:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "missing_token"})
    try:
        user_id = security.decode_subscription_session_token(authorization[7:].strip())
    except security.JWTError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail={"code": "invalid_session"}
        ) from exc
    user = await repo.find_user_by_id(user_id)
    if user is None or user.is_banned:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail={"code": "user_unavailable"}
        )
    return user


@router.post("/subscription/context", response_model=SubscriptionContextResponse)
@limiter.limit("30/minute")
async def create_subscription_context(
    body: SubscriptionContextRequest, request: Request
) -> SubscriptionContextResponse:
    if not _SHORT_UUID_RE.fullmatch(body.short_uuid):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"code": "bad_short_uuid"}
        )
    rem_user = await get_user_by_short_uuid_raw(body.short_uuid)
    raw_id = rem_user.get("id") if rem_user else None
    try:
        rw_id = int(raw_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail={"code": "subscription_not_found"}
        )
    return SubscriptionContextResponse(
        context=security.issue_subscription_context(
            rw_id=rw_id, short_uuid=body.short_uuid
        ),
        rw_id=rw_id,
    )


@router.post("/oauth/authorize", response_model=AuthorizeResponse)
@limiter.limit("20/minute")
async def authorize_subscription_page(
    body: AuthorizeRequest,
    request: Request,
    user: repo.UserRow = Depends(deps.get_current_user),
) -> AuthorizeResponse:
    _validate_client(body.client_id, body.redirect_uri)
    if body.code_challenge_method != "S256" or not _PKCE_RE.fullmatch(body.code_challenge):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"code": "invalid_pkce"}
        )

    code = secrets.token_urlsafe(32)
    now = _now()
    row = WebAuthorizationCode(
        user_id=user.id,
        code_hash=_hash(code),
        client_id=body.client_id,
        redirect_uri=body.redirect_uri,
        code_challenge=body.code_challenge,
        created_at=_iso(now),
        expires_at=_iso(now + timedelta(seconds=_AUTH_CODE_TTL_SECONDS)),
    )
    async with async_session() as session:
        session.add(row)
        await session.commit()

    query = urllib.parse.urlencode({"code": code, "state": body.state})
    separator = "&" if "?" in body.redirect_uri else "?"
    return AuthorizeResponse(redirect_url=f"{body.redirect_uri}{separator}{query}")


@router.post("/oauth/token", response_model=TokenResponse)
@limiter.limit("30/minute")
async def exchange_authorization_code(
    body: TokenRequest, request: Request
) -> TokenResponse:
    _validate_client(body.client_id, body.redirect_uri)
    if body.grant_type != "authorization_code" or not _PKCE_RE.fullmatch(body.code_verifier):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"code": "invalid_grant"}
        )

    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(body.code_verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    now = _iso(_now())
    async with async_session() as session:
        row = await session.scalar(
            select(WebAuthorizationCode).where(
                WebAuthorizationCode.code_hash == _hash(body.code)
            )
        )
        if (
            row is None
            or row.used_at is not None
            or row.expires_at <= now
            or row.client_id != body.client_id
            or row.redirect_uri != body.redirect_uri
            or not secrets.compare_digest(row.code_challenge, challenge)
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail={"code": "invalid_grant"}
            )
        consumed = await session.execute(
            update(WebAuthorizationCode)
            .where(
                WebAuthorizationCode.id == row.id,
                WebAuthorizationCode.used_at.is_(None),
                WebAuthorizationCode.expires_at > now,
            )
            .values(used_at=now)
        )
        if int(consumed.rowcount or 0) != 1:
            await session.rollback()
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail={"code": "invalid_grant"}
            )
        await session.commit()

    token, ttl = security.issue_subscription_session_token(row.user_id)
    return TokenResponse(session_token=token, expires_in=ttl)


@router.get("/oauth/userinfo", response_model=SubscriptionSessionUser)
async def subscription_userinfo(
    user: repo.UserRow = Depends(_subscription_session_user),
) -> SubscriptionSessionUser:
    return SubscriptionSessionUser(
        id=user.id,
        email=user.email,
        has_telegram=user.tg_id is not None,
    )


@router.get(
    "/oauth/subscriptions", response_model=ManagedSubscriptionsResponse
)
async def subscription_session_subscriptions(
    user: repo.UserRow = Depends(_subscription_session_user),
) -> ManagedSubscriptionsResponse:
    async with async_session() as session:
        rows = await subscription_repo.list_for_user(session, user.id)
    resolved = await asyncio.gather(*(_serialize(row) for row in rows))
    return ManagedSubscriptionsResponse(
        subscriptions=[item for item in resolved if item is not None]
    )


@router.post(
    "/oauth/subscriptions/attach", response_model=AttachSubscriptionResponse
)
async def attach_subscription(
    body: AttachSubscriptionRequest,
    user: repo.UserRow = Depends(_subscription_session_user),
) -> AttachSubscriptionResponse:
    try:
        rw_id, _ = security.decode_subscription_context(body.context)
    except security.JWTError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"code": "invalid_context"}
        ) from exc

    async with async_session() as session:
        try:
            linked = await subscription_repo.attach(
                session,
                user_id=user.id,
                rw_id=rw_id,
                source="subscription_page",
                label=body.label,
                make_primary=body.make_primary,
            )
        except ValueError as exc:
            code = str(exc)
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail={"code": code}
            ) from exc
        await session.commit()
    return AttachSubscriptionResponse(
        subscription_id=linked.id, is_primary=linked.is_primary
    )


def _remaining_days(rem_user: dict) -> int:
    expire = rem_user.get("expire")
    if expire is None:
        return 0
    return max(0, math.ceil((int(expire) - time.time()) / 86400))


@router.post(
    "/oauth/subscriptions/transfer", response_model=TransferSubscriptionResponse
)
async def transfer_subscription_time(
    body: TransferSubscriptionRequest,
    user: repo.UserRow = Depends(_subscription_session_user),
) -> TransferSubscriptionResponse:
    if not body.confirmed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"code": "confirmation_required"}
        )
    try:
        source_rw_id, _ = security.decode_subscription_context(body.context)
    except security.JWTError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"code": "invalid_context"}
        ) from exc

    now = _iso(_now())
    async with async_session() as session:
        target = await subscription_repo.get_for_user(
            session,
            user_id=user.id,
            subscription_id=body.target_subscription_id,
        )
        if target is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail={"code": "subscription_not_found"}
            )
        if target.rw_id == source_rw_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail={"code": "same_subscription"}
            )
        owner = await subscription_repo.get_by_rw_id(session, source_rw_id)
        if owner is not None and owner.user_id != user.id:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"code": "subscription_already_linked"},
            )
        existing = await session.scalar(
            select(SubscriptionTransfer).where(
                SubscriptionTransfer.source_rw_id == source_rw_id
            )
        )
        if existing is not None:
            if existing.user_id == user.id and existing.status == "completed":
                actual_target = await subscription_repo.get_by_rw_id(
                    session, existing.target_rw_id
                )
                return TransferSubscriptionResponse(
                    status="completed",
                    days_transferred=int(existing.days_transferred or 0),
                    target_subscription_id=(
                        actual_target.id
                        if actual_target is not None
                        else body.target_subscription_id
                    ),
                )
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"code": f"transfer_{existing.status}"},
            )

        ledger = SubscriptionTransfer(
            user_id=user.id,
            source_rw_id=source_rw_id,
            target_rw_id=target.rw_id,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        session.add(ledger)
        try:
            await session.commit()
        except IntegrityError:
            # The unique source_rw_id ledger is the serialization point for
            # concurrent transfer clicks. Return the winner's completed result
            # or a stable conflict instead of leaking a database 500.
            await session.rollback()
            existing = await session.scalar(
                select(SubscriptionTransfer).where(
                    SubscriptionTransfer.source_rw_id == source_rw_id
                )
            )
            if existing is not None and existing.user_id == user.id:
                if existing.status == "completed":
                    actual_target = await subscription_repo.get_by_rw_id(
                        session, existing.target_rw_id
                    )
                    return TransferSubscriptionResponse(
                        status="completed",
                        days_transferred=int(existing.days_transferred or 0),
                        target_subscription_id=(
                            actual_target.id
                            if actual_target is not None
                            else body.target_subscription_id
                        ),
                    )
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail={"code": f"transfer_{existing.status}"},
                )
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"code": "subscription_already_transferred"},
            )

    source_user, target_user = await asyncio.gather(
        get_user_from_id(source_rw_id), get_user_from_id(target.rw_id)
    )
    if source_user is None or target_user is None:
        async with async_session() as session:
            row = await session.get(SubscriptionTransfer, ledger.id)
            if row:
                row.status = "failed"
                row.error_code = "subscription_not_found"
                row.updated_at = _iso(_now())
                await session.commit()
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail={"code": "subscription_not_found"}
        )

    source_days = _remaining_days(source_user)
    if source_days <= 0:
        async with async_session() as session:
            row = await session.get(SubscriptionTransfer, ledger.id)
            if row:
                row.status = "failed"
                row.error_code = "no_remaining_time"
                row.updated_at = _iso(_now())
                await session.commit()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail={"code": "no_remaining_time"}
        )

    target_days = _remaining_days(target_user)
    extended = await update_user_by_id(target.rw_id, days=target_days + source_days)
    if extended is None:
        async with async_session() as session:
            row = await session.get(SubscriptionTransfer, ledger.id)
            if row:
                row.status = "manual_review"
                row.error_code = "target_update_failed"
                row.updated_at = _iso(_now())
                await session.commit()
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail={"code": "transfer_manual_review"}
        )

    disabled = await update_user_by_id(source_rw_id, status="disabled")
    async with async_session() as session:
        row = await session.get(SubscriptionTransfer, ledger.id)
        if disabled is None:
            if row:
                row.status = "manual_review"
                row.error_code = "source_disable_failed"
                row.days_transferred = source_days
                row.updated_at = _iso(_now())
                await session.commit()
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail={"code": "transfer_manual_review"},
            )

        await subscription_repo.attach(
            session,
            user_id=user.id,
            rw_id=source_rw_id,
            source="transferred",
            label="Transferred subscription",
        )
        if row:
            row.status = "completed"
            row.days_transferred = source_days
            row.updated_at = _iso(_now())
        await session.commit()

    return TransferSubscriptionResponse(
        status="completed",
        days_transferred=source_days,
        target_subscription_id=body.target_subscription_id,
    )
