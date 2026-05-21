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
import os
import re
import secrets
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..config import get_bot_url
from ..database.session import async_session
from ..notify_log import esc, notify_log
from ..remnawave_client import update_user
from . import auth_router, deps, repo, security
from .schemas_data import LinkByUrlRequest, LinkByUrlResponse, LinkStartResponse

router = APIRouter(prefix="/api/android/link", tags=["android-link"])
logger = logging.getLogger(__name__)

# Reuse the auth router's slowapi instance — main.py wires it into
# `app.state.limiter`, so any decorator on it takes effect at app boot.
limiter = auth_router.limiter

_LINK_CODE_TTL_SECONDS = 600

_SUBSCRIPTION_HOST = os.environ.get(
    "SUBSCRIPTION_HOST", "user.spicycheeze.xyz",
)
_SHORT_UUID_RE = re.compile(r"^[A-Za-z0-9_-]{8,32}$")


def _parse_short_uuid(url: str) -> str:
    """Extract the short_uuid from a subscription URL.

    Strict: https only, exact host match against $SUBSCRIPTION_HOST
    (default ``user.spicycheeze.xyz``), single path segment matching
    ``[A-Za-z0-9_-]{8,32}``. Query string and fragment are ignored.

    Raises ``HTTPException(422, {"code": "invalid_url"})`` on any failure.
    """
    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_url"},
        ) from exc

    if parsed.scheme != "https" or parsed.netloc != _SUBSCRIPTION_HOST:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_url"},
        )
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) != 1 or not _SHORT_UUID_RE.match(parts[0]):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_url"},
        )
    return parts[0]


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


@router.post("/by_url", response_model=LinkByUrlResponse)
@limiter.limit("3/minute")
async def link_by_url(
    request: Request,
    payload: LinkByUrlRequest,
    user: repo.UserRow = Depends(deps.require_verified_email),
) -> LinkByUrlResponse:
    """Import a Remnawave subscription URL into the authenticated account.

    Flow:
      1. Parse short_uuid from URL (422 on bad shape).
      2. Run import_subscription_by_uuid in a new session.
         - LookupNotFound  → 404 rw_not_found.
         - MergeBlocked    → 200 both_pro_support_needed.
         - Any other exc   → 500 internal.
      3. Commit, best-effort disable loser RW user.
      4. notify_log.

    The URL is a bearer credential — anyone holding it can take the
    subscription. require_verified_email gates this, the rate limit
    slows credential-stuffing against random short_uuids.
    """
    from app.handlers.android_link_merge import (
        LookupNotFound, MergeBlocked, import_subscription_by_uuid,
    )

    short_uuid = _parse_short_uuid(payload.url)

    # Capture the notify text and any deferred action inside the `async with`
    # and emit/raise after the DB session closes — `notify_log` does network
    # I/O (up to 5s) and we don't want to hold a DB connection on errors.
    blocked_response: LinkByUrlResponse | None = None
    pending_404 = False
    pending_500 = False
    merge: dict | None = None

    async with async_session() as s:
        try:
            merge = await import_subscription_by_uuid(
                s,
                current_user_id=user.id,
                b_rw_short_uuid=short_uuid,
            )
        except LookupNotFound:
            await s.rollback()
            pending_notify = (
                f"❌ <b>Android sub-URL import: rw_not_found</b>\n"
                f"user=<code>{user.id}</code> "
                f"short_uuid=<code>{esc(short_uuid)}</code>"
            )
            pending_404 = True
        except MergeBlocked as blocked:
            await s.rollback()
            pending_notify = _format_notify(
                result="both_pro_support_needed",
                user_id=user.id, email=user.email,
                a_rw_uuid=blocked.details.get("a_rw_uuid"),
                a_tier="pro",
                b_rw_uuid=blocked.details.get("t_rw_uuid"),
                b_tier="pro",
                chosen=None, disabled=None,
            )
            blocked_response = LinkByUrlResponse(
                result="both_pro_support_needed",
                a_tier="pro",
                b_tier="pro",
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(
                "link_by_url failed: %s", exc, exc_info=True,
            )
            await s.rollback()
            pending_500 = True
        else:
            await s.commit()

    if pending_500:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "internal"},
        )

    if pending_404:
        await notify_log(pending_notify)
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "rw_not_found"},
        )

    if blocked_response is not None:
        await notify_log(pending_notify)
        return blocked_response

    assert merge is not None  # success path: merge was populated

    # Best-effort RW deactivate. Failure does NOT roll back the DB.
    disabled_uuid = merge.get("loser_rw_uuid")
    if merge["result"] in ("merged_pro", "merged_free", "ok") and disabled_uuid:
        try:
            await update_user(user_uuid=disabled_uuid, status="disabled")
        except Exception as exc:
            logger.warning(
                "Failed to disable old RW user %s: %s",
                disabled_uuid, exc,
            )
            await notify_log(
                f"⚠️ <b>Failed to disable old RW user</b>\n"
                f"uuid: <code>{esc(disabled_uuid)}</code>\n"
                f"error: <code>{esc(str(exc)[:300])}</code>"
            )
            disabled_uuid = None  # didn't actually disable; reflect in log

    await notify_log(
        _format_notify(
            result=merge["result"],
            user_id=user.id, email=user.email,
            a_rw_uuid=merge.get("a_rw_uuid"),
            a_tier=merge["a_tier"],
            b_rw_uuid=merge["b_rw_uuid"],
            b_tier=merge["b_tier"],
            chosen=merge["chosen_uuid"],
            disabled=disabled_uuid,
        )
    )

    return LinkByUrlResponse(
        result=merge["result"],
        a_tier=merge["a_tier"],
        b_tier=merge["b_tier"],
    )


def _format_notify(
    *,
    result: str,
    user_id: int,
    email: str | None,
    a_rw_uuid: str | None,
    a_tier: str,
    b_rw_uuid: str | None,
    b_tier: str,
    chosen: str | None,
    disabled: str | None,
) -> str:
    parts = [f"🔗 <b>Android sub-URL import: {esc(result)}</b>"]
    parts.append(
        f"user: <code>{user_id}</code> {esc(email or '—')} "
        f"rw=<code>{esc(a_rw_uuid or '—')}</code> "
        f"tier=<code>{esc(a_tier)}</code>"
    )
    parts.append(
        f"imported: rw=<code>{esc(b_rw_uuid or '—')}</code> "
        f"tier=<code>{esc(b_tier)}</code>"
    )
    if result != "both_pro_support_needed":
        parts.append(
            f"chosen_uuid=<code>{esc(chosen or '—')}</code> "
            f"disabled_uuid=<code>{esc(disabled or '—')}</code>"
        )
    return "\n".join(parts)
