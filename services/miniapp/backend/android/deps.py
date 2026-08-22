"""FastAPI dependencies for Android API auth.

`get_current_user` extracts a Bearer access JWT and returns the user row.
`require_verified_email` is layered on top for endpoints that should be
gated behind email confirmation (most notably: payment invoicing).
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request, status

from . import repo, security


def real_client_ip(request: Request) -> str:
    """Resolve the real client IP behind the trusted edge nginx.

    The edge sets ``X-Real-IP`` to its ``$remote_addr`` (the actual connecting
    client) with ``proxy_set_header`` (overwrite, not append), so we trust it
    first. We deliberately do NOT trust the *leftmost* ``X-Forwarded-For`` entry
    — that one is attacker-supplied and was previously used here, which let a
    client spoof its IP to evade the brute-force guard and poison logs. As a
    fallback we take the *rightmost* XFF hop (the value the trusted edge
    appended) and finally the socket peer.

    Backend ports are bound to 127.0.0.1, so requests can only reach us via the
    edge; the ``X-Real-IP`` it sets cannot be forged by external clients.
    """
    xri = request.headers.get("x-real-ip")
    if xri and xri.strip():
        return xri.strip()
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        hops = [p.strip() for p in fwd.split(",") if p.strip()]
        if hops:
            return hops[-1]
    return request.client.host if request.client else "unknown"


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ua = request.headers.get("user-agent")
    return ua, real_client_ip(request)


async def get_current_user(
    request: Request,
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
    request.state.api_user_id = user.id
    request.state.api_tg_id = user.tg_id
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
