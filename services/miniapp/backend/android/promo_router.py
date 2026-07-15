"""Promo code endpoints for JWT-authenticated web/android clients."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database.session import async_session
from . import deps
from . import repo as android_repo
from common_db.repo import balance as _repo_balance
from common_db.repo import promos as _repo_promos
from common_db.repo import system as _repo_system

router = APIRouter(prefix="/api/android/promo", tags=["android-promo"])

_REASON_HTTP: dict[str, tuple[int, str]] = {
    _repo_promos.REASON_INVALID: (404, "invalid promo code"),
    _repo_promos.REASON_OWN_CODE: (400, "cannot use your own promo code"),
    _repo_promos.REASON_ALREADY_USED: (409, "you have already used this promo code"),
    _repo_promos.REASON_REFERRAL_ONLY_ONE: (409, "you have already used a referral code"),
    _repo_promos.REASON_REFERRAL_NOT_NEW: (403, "referral codes are for new users only"),
    _repo_promos.REASON_NO_USER: (404, "user not found"),
}


def _promo_tg_id(user: android_repo.UserRow) -> int:
    return user.tg_id if user.tg_id is not None else -int(user.id)


class ActivateRequest(BaseModel):
    promo_code: str = Field(min_length=1, max_length=20)


@router.get("")
async def get_promo_state(
    user: android_repo.UserRow = Depends(deps.get_current_user),
):
    tg_id = _promo_tg_id(user)
    async with async_session() as session:
        balance = await _repo_balance.get_balance(session, user.id)
        latest = await _repo_promos.get_latest_redemption(session, tg_id)
        default_grant = await _repo_system.get_default_credit_grant(session)
        await session.commit()
    return {
        "balance": balance,
        "last_promo_code": latest.promo_code if latest else None,
        "default_credit_grant": default_grant,
    }


@router.post("")
async def activate_promo(
    body: ActivateRequest,
    user: android_repo.UserRow = Depends(deps.get_current_user),
):
    code = body.promo_code.strip().upper()
    if not code:
        raise HTTPException(400, "promo code required")
    tg_id = _promo_tg_id(user)
    async with async_session() as session:
        result = await _repo_promos.redeem_promo(session, tg_id, code)
        if not result.ok:
            await session.rollback()
            status_code, detail = _REASON_HTTP.get(result.reason, (400, "cannot use this promo code"))
            raise HTTPException(status_code, detail)
        await session.commit()
    return {
        "ok": True,
        "promo_code": code,
        "credit_grant": result.credit_grant,
        "balance": result.new_balance,
    }
