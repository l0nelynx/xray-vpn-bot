"""Promo / referral endpoints for the Telegram MiniApp.

All rules live in common_db.repo.promos so the bot and miniapp behave
identically (referral codes for new users only, one active promo at a time,
each code once, etc.). This router only adapts repo results to HTTP.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..config import get_bot_url
from ..database.session import async_session
from ..tg_auth import TgUser, get_tg_user

from common_db.repo import promos as _repo_promos
from common_db.repo import system as _repo_system

router = APIRouter(prefix="/api/promo", tags=["promo"])


# Map repo can_redeem reason codes → (HTTP status, user-facing message).
_REASON_HTTP = {
    _repo_promos.REASON_INVALID: (404, "invalid promo code"),
    _repo_promos.REASON_OWN_CODE: (400, "cannot use your own promo code"),
    _repo_promos.REASON_ALREADY_USED: (409, "you have already used this promo code"),
    _repo_promos.REASON_ACTIVE_EXISTS: (409, "a promo is already active — use it first"),
    _repo_promos.REASON_REFERRAL_ONLY_ONE: (409, "you have already used a referral code"),
    _repo_promos.REASON_REFERRAL_NOT_NEW: (
        403,
        "referral codes are for new users only",
    ),
}


class ActivateRequest(BaseModel):
    promo_code: str = Field(min_length=1, max_length=20)


@router.get("")
async def get_promo_state(tg: TgUser = Depends(get_tg_user)):
    """The user's current promo state (active redemption + defaults)."""
    async with async_session() as session:
        active = await _repo_promos.get_active_redemption(session, tg.tg_id)
        default_discount = await _repo_system.get_default_discount_percent(session)
        await session.commit()  # persist auto-seeded PromoSettings
        return {
            "can_activate": active is None,
            "active_promo": active.promo_code if active else None,
            "discount_percent": active.discount_percent if active else 0,
            "default_discount_percent": default_discount,
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
        "active_promo": code,
        "discount_percent": result.discount_percent,
    }


@router.get("/referral")
async def get_referral_state(tg: TgUser = Depends(get_tg_user)):
    """Referral code + deeplink + stats + program rules (for the Invite UI).

    Numbers (discount, reward-per-30, cap) come from promo_settings so the UI
    and the rules text always reflect the configured values.
    """
    async with async_session() as session:
        code = await _repo_promos.get_or_create_referral_code(session, tg.tg_id)
        promo = await _repo_promos.get_promo_by_tg_id(session, tg.tg_id)
        default_discount = await _repo_system.get_default_discount_percent(session)
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
        "discount_percent": default_discount,
        "days_reward_per_30": days_reward_per_30,
        "reward_cap_days": reward_cap_days,
        "days_purchased": days_purchased,
        "days_rewarded": days_rewarded,
    }
