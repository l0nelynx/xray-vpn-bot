"""FastAPI dependencies for Android API auth.

`get_current_user` extracts a Bearer access JWT and returns the user row.
`require_verified_email` is layered on top for endpoints that should be
gated behind email confirmation (most notably: payment invoicing).
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request, status

from . import repo, security


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ua = request.headers.get("user-agent")
    fwd = request.headers.get("x-forwarded-for")
    ip = (fwd.split(",")[0].strip() if fwd else None) or (
        request.client.host if request.client else None
    )
    return ua, ip


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> repo.UserRow:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = authorization[7:].strip()
    try:
        claims = security.decode_access_token(token)
    except security.JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    user = await repo.find_user_by_id(claims.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    if user.is_banned:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account banned")
    return user


async def require_verified_email(
    user: repo.UserRow = Depends(get_current_user),
) -> repo.UserRow:
    if not user.email_verified_at:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "email_not_verified"
        )
    return user


def client_meta(request: Request) -> tuple[str | None, str | None]:
    return _client_meta(request)
