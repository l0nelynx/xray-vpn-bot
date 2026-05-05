"""Stage 6 — Telegram link flow.

Direction: Android client requests a one-time code, then opens
`https://t.me/<bot>?start=link_<code>` in Telegram. The bot's `/start`
deep-link handler consumes the code and binds `users.tg_id`.

Re-link policy: if `users.tg_id` is already set, /link/start refuses with
`409 already_linked`. The user must explicitly DELETE /link/telegram first.
This protects against a leaked-token attacker quietly swapping the bound
Telegram account.
"""
from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..config import get_bot_url
from . import auth_router, deps, repo, security
from .schemas_data import LinkStartResponse

router = APIRouter(prefix="/api/android/link", tags=["android-link"])
logger = logging.getLogger(__name__)

# Reuse the auth router's slowapi instance — main.py wires it into
# `app.state.limiter`, so any decorator on it takes effect at app boot.
limiter = auth_router.limiter

_LINK_CODE_TTL_SECONDS = 600


def _build_deep_link(bot_url: str, code: str) -> str:
    base = bot_url.rstrip("/")
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}start=link_{code}"


@router.post("/start", response_model=LinkStartResponse)
@limiter.limit("3/minute")
async def start_link(
    request: Request,
    user: repo.UserRow = Depends(deps.require_verified_email),
) -> LinkStartResponse:
    if user.tg_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail={"code": "already_linked"}
        )

    # 8 random bytes → ~11-char URL-safe code. Telegram's /start payload
    # accepts up to 64 chars of [A-Za-z0-9_-], so this fits comfortably.
    code = secrets.token_urlsafe(8)
    code_hash = security.hash_email_code(code)
    await repo.invalidate_pending_codes(user.id, repo.PURPOSE_TG_LINK)
    await repo.store_verification_code(
        user_id=user.id,
        purpose=repo.PURPOSE_TG_LINK,
        code_hash=code_hash,
        payload=None,
        ttl_seconds=_LINK_CODE_TTL_SECONDS,
    )
    return LinkStartResponse(
        code=code,
        expires_in=_LINK_CODE_TTL_SECONDS,
        deep_link=_build_deep_link(get_bot_url(), code),
    )


@router.delete("/telegram", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_telegram(
    user: repo.UserRow = Depends(deps.get_current_user),
) -> None:
    # Idempotent — clearing an already-null tg_id is a no-op at the SQL
    # level. Returning 204 either way keeps client logic simple.
    await repo.clear_user_tg_id(user.id)
    return None
