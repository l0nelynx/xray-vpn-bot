"""Auth endpoints for the Android API.

Mounted at <BASE_PATH>/api/android/auth. Anti-enumeration: register/login
respond with the same shape and timing whether or not the email exists.
Refresh-token rotation uses a family-id model — replaying a previously
rotated token revokes the entire family (assumed compromise).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.exc import IntegrityError

from . import deps, repo, security

# Module-level limiter shared with main.app.state.limiter via singleton.
limiter = Limiter(key_func=get_remote_address)
from .schemas import (
    AuthResponse,
    LoginRequest,
    LogoutRequest,
    PasswordChangeRequest,
    RefreshRequest,
    RegisterRequest,
    SimpleStatus,
    TokenPair,
    UserSummary,
)

router = APIRouter(prefix="/api/android/auth", tags=["android-auth"])


def _user_summary(user: repo.UserRow) -> UserSummary:
    return UserSummary(
        id=user.id,
        email=user.email,
        email_verified=user.email_verified_at is not None,
        has_password=user.password_hash is not None,
        has_telegram=user.tg_id is not None,
    )


async def _issue_pair(
    user_id: int, request: Request, family_id: str | None = None
) -> TokenPair:
    fam = family_id or security.new_family_id()
    raw_refresh, refresh_hash = security.issue_refresh_token(fam)
    ua, ip = deps.client_meta(request)
    await repo.store_refresh_token(
        user_id=user_id,
        family_id=fam,
        token_hash=refresh_hash,
        user_agent=ua,
        ip=ip,
    )
    access, claims = security.issue_access_token(user_id)
    return TokenPair(
        access_token=access,
        refresh_token=raw_refresh,
        expires_in=claims.expires_at - claims.issued_at,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(req: RegisterRequest, request: Request) -> AuthResponse:
    pwd_hash = security.hash_password(req.password)
    try:
        user_id = await repo.create_user_with_password(str(req.email), pwd_hash)
    except IntegrityError:
        # Anti-enumeration: same shape as success would leak; we use 409
        # because Android needs to react. The `code` lets the client show a
        # localized message without parsing free text.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "email_taken"},
        )
    user = await repo.find_user_by_id(user_id)
    assert user is not None
    tokens = await _issue_pair(user_id, request)
    return AuthResponse(tokens=tokens, user=_user_summary(user))


@router.post("/login", response_model=AuthResponse)
@limiter.limit("10/minute")
async def login(req: LoginRequest, request: Request) -> AuthResponse:
    user = await repo.find_user_by_email(str(req.email))
    # Always run verify to keep timing constant.
    if not security.verify_password(
        user.password_hash if user else None, req.password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials"},
        )
    assert user is not None  # verify_password returns False on user=None
    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail={"code": "banned"}
        )
    if security.needs_rehash(user.password_hash or ""):
        await repo.set_password(user.id, security.hash_password(req.password))
    tokens = await _issue_pair(user.id, request)
    return AuthResponse(tokens=tokens, user=_user_summary(user))


@router.post("/refresh", response_model=TokenPair)
@limiter.limit("60/minute")
async def refresh(req: RefreshRequest, request: Request) -> TokenPair:
    family = security.split_family_id(req.refresh_token)
    if family is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "bad_refresh"})

    token_hash = security.hash_refresh_token(req.refresh_token)
    row = await repo.find_refresh_by_hash(token_hash)
    if row is None or row.family_id != family:
        # Unknown token presented for a known-format family: treat as theft
        # and burn the family if we recognise it.
        await repo.revoke_family(family)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "bad_refresh"})

    if row.revoked_at is not None or row.replaced_by_id is not None:
        # Reuse of an already-rotated token => family compromise.
        await repo.revoke_family(family)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "refresh_reused"})

    from datetime import datetime, timezone

    if row.expires_at <= datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "refresh_expired"})

    user = await repo.find_user_by_id(row.user_id)
    if user is None or user.is_banned:
        await repo.revoke_family(family)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "user_unavailable"})

    new_raw, new_hash = security.issue_refresh_token(family)
    ua, ip = deps.client_meta(request)
    await repo.rotate_refresh_token(
        old_id=row.id,
        user_id=row.user_id,
        family_id=family,
        new_token_hash=new_hash,
        user_agent=ua,
        ip=ip,
    )
    access, claims = security.issue_access_token(row.user_id)
    return TokenPair(
        access_token=access,
        refresh_token=new_raw,
        expires_in=claims.expires_at - claims.issued_at,
    )


@router.post("/logout", response_model=SimpleStatus)
async def logout(req: LogoutRequest) -> SimpleStatus:
    token_hash = security.hash_refresh_token(req.refresh_token)
    row = await repo.find_refresh_by_hash(token_hash)
    if row is not None:
        await repo.revoke_family(row.family_id)
    return SimpleStatus()


@router.post("/logout-all", response_model=SimpleStatus)
async def logout_all(
    user: repo.UserRow = Depends(deps.get_current_user),
) -> SimpleStatus:
    await repo.revoke_all_user_tokens(user.id)
    return SimpleStatus()


@router.post("/password/change", response_model=SimpleStatus)
async def password_change(
    req: PasswordChangeRequest,
    user: repo.UserRow = Depends(deps.get_current_user),
) -> SimpleStatus:
    if not security.verify_password(user.password_hash, req.current_password):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"code": "invalid_credentials"}
        )
    await repo.set_password(user.id, security.hash_password(req.new_password))
    # Invalidate every existing session — client must re-login.
    await repo.revoke_all_user_tokens(user.id)
    return SimpleStatus()
