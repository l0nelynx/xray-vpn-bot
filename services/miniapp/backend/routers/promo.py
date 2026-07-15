"""Promo / referral endpoints for the Telegram MiniApp."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..config import get_bot_url
from ..database.session import async_session
from ..tg_auth import TgUser, get_tg_user

from common_db.repo import balance as _repo_balance
from common_db.repo import promos as _repo_promos
from common_db.repo import system as _repo_system
from common_db.repo import users as _repo_users

router = APIRouter(prefix="/api/promo", tags=["promo"])


_REASON_HTTP = {
    _repo_promos.REASON_INVALID: (404, "invalid promo code"),
    _repo_promos.REASON_OWN_CODE: (400, "cannot use your own promo code"),
    _repo_promos.REASON_ALREADY_USED: (409, "you have already used this promo code"),
    _repo_promos.REASON_REFERRAL_ONLY_ONE: (409, "you have already used a referral code"),
    _repo_promos.REASON_REFERRAL_NOT_NEW: (
        403,
        "referral codes are for new users only",
    ),
    _repo_promos.REASON_NO_USER: (404, "user not registered"),
}


class ActivateRequest(BaseModel):
    promo_code: str = Field(min_length=1, max_length=20)


@router.get("")
async def get_promo_state(tg: TgUser = Depends(get_tg_user)):
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg.tg_id)
        if not user:
            raise HTTPException(404, "user not registered")
        balance = await _repo_balance.get_balance(session, user.id)
        latest = await _repo_promos.get_latest_redemption(session, tg.tg_id)
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
    tg: TgUser = Depends(get_tg_user),
):
    code = body.promo_code.strip().upper()
    if not code:
        raise HTTPException(400, "promo code required")

    async with async_session() as session:
        result = await _repo_promos.redeem_promo(session, tg.tg_id, code)
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


@router.get("/referral")
async def get_referral_state(tg: TgUser = Depends(get_tg_user)):
    async with async_session() as session:
        code = await _repo_promos.get_or_create_referral_code(session, tg.tg_id)
        promo = await _repo_promos.get_promo_by_tg_id(session, tg.tg_id)
        default_grant = await _repo_system.get_default_credit_grant(session)
        days_reward_per_30 = await _repo_system.get_days_reward_per_30(session)
        reward_cap_days = await _repo_system.get_reward_cap_days(session)
        await session.commit()

        days_purchased = promo.days_purchased if promo else 0
        days_rewarded = promo.days_rewarded if promo else 0

    bot_url = (get_bot_url() or "").rstrip("/")
    deeplink = f"{bot_url}?start={code}" if bot_url else ""

    return {
        "code": code,
        "deeplink": deeplink,
        "credit_grant": default_grant,
        "days_reward_per_30": days_reward_per_30,
        "reward_cap_days": reward_cap_days,
        "days_purchased": days_purchased,
        "days_rewarded": days_rewarded,
    }
