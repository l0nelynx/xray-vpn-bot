"""Promo code endpoints for JWT-authenticated web/android clients.

Mirrors miniapp/backend/routers/promo.py but uses Bearer-JWT auth
(deps.get_current_user) instead of Telegram init-data auth.

Promo redemptions are keyed by tg_id in the DB.  Web-only users have
no real tg_id, so we use the same synthetic id as web_router.py:
  fake_tg_id = -user.id   (negative → never collides with real Telegram IDs)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database.session import async_session
from . import deps
from . import repo as android_repo
from common_db.repo import promos as _repo_promos
from common_db.repo import system as _repo_system

router = APIRouter(prefix="/api/android/promo", tags=["android-promo"])

_REASON_HTTP: dict[str, tuple[int, str]] = {
    _repo_promos.REASON_INVALID:            (404, "invalid promo code"),
    _repo_promos.REASON_OWN_CODE:           (400, "cannot use your own promo code"),
    _repo_promos.REASON_ALREADY_USED:       (409, "you have already used this promo code"),
    _repo_promos.REASON_ACTIVE_EXISTS:      (409, "a promo is already active — use it first"),
    _repo_promos.REASON_REFERRAL_ONLY_ONE:  (409, "you have already used a referral code"),
    _repo_promos.REASON_REFERRAL_NOT_NEW:   (403, "referral codes are for new users only"),
}


def _promo_tg_id(user_id: int) -> int:
    """Synthetic tg_id for promo ops — mirrors web_router._fake_tg_id."""
    return -int(user_id)


class ActivateRequest(BaseModel):
    promo_code: str = Field(min_length=1, max_length=20)


@router.get("")
async def get_promo_state(
    user: android_repo.UserRow = Depends(deps.get_current_user),
):
    """Return the user's current promo state (active redemption + system default)."""
    tg_id = _promo_tg_id(user.id)
    async with async_session() as session:
        active = await _repo_promos.get_active_redemption(session, tg_id)
        default_discount = await _repo_system.get_default_discount_percent(session)
        await session.commit()
    return {
        "can_activate": active is None,
        "active_promo": active.promo_code if active else None,
        "discount_percent": active.discount_percent if active else 0,
        "default_discount_percent": default_discount,
    }


@router.post("")
async def activate_promo(
    body: ActivateRequest,
    user: android_repo.UserRow = Depends(deps.get_current_user),
):
    """Activate a promo code for the authenticated user."""
    code = body.promo_code.strip().upper()
    if not code:
        raise HTTPException(400, "promo code required")
    tg_id = _promo_tg_id(user.id)
    async with async_session() as session:
        result = await _repo_promos.redeem_promo(session, tg_id, code)
        if not result.ok:
            await session.rollback()
            status_code, detail = _REASON_HTTP.get(result.reason, (400, "cannot use this promo code"))
            raise HTTPException(status_code, detail)
        await session.commit()
    return {
        "ok": True,
        "active_promo": code,
        "discount_percent": result.discount_percent,
    }
