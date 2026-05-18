import random
import string

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database.models import Promo
from ..database.session import async_session
from ..tg_auth import TgUser, get_tg_user

# All promo lookups + the discount cascade live in common_db. The
# duplicated cascade in this file used to fall back to `None` when
# PromoSettings was missing (which silently means 0%); the helper now
# auto-seeds the singleton, so a fresh DB always returns 20%.
from common_db.repo import promos as _repo_promos
from common_db.repo import system as _repo_system

router = APIRouter(prefix="/api/promo", tags=["promo"])


class ActivateRequest(BaseModel):
    promo_code: str = Field(min_length=1, max_length=20)


async def _effective_discount(session, promo: Promo) -> int:
    """Owner's override → PromoSettings default. Bound to the caller's
    session so we don't open a second one mid-request."""
    if promo.discount_percent is not None:
        return promo.discount_percent
    return await _repo_system.get_default_discount_percent(session)


@router.get("")
async def get_promo_state(tg: TgUser = Depends(get_tg_user)):
    """Returns the user's current promo state."""
    async with async_session() as session:
        promo = await _repo_promos.get_promo_by_tg_id(session, tg.tg_id)
        default_discount = await _repo_system.get_default_discount_percent(session)

        # No promo or consumed promo → user can activate a new one
        if not promo or not promo.used_promo or promo.used_promo_consumed:
            await session.commit()  # persist auto-seeded PromoSettings
            return {
                "can_activate": True,
                "active_promo": None,
                "discount_percent": 0,
                "default_discount_percent": default_discount,
            }

        owner_promo = await _repo_promos.get_promo_by_code(session, promo.used_promo)
        discount = (
            await _effective_discount(session, owner_promo)
            if owner_promo else default_discount
        )
        await session.commit()
        return {
            "can_activate": False,
            "active_promo": promo.used_promo,
            "discount_percent": discount,
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
        own = await _repo_promos.get_promo_by_tg_id(session, tg.tg_id)

        # Same code can't be used twice by the same user
        if own and own.used_promo == code:
            raise HTTPException(409, "already used this promo code")

        # Active non-consumed promo blocks activation of a different one
        if own and own.used_promo and not own.used_promo_consumed:
            raise HTTPException(409, "promo already active — use it first")

        promo = await _repo_promos.get_promo_by_code(session, code)
        if not promo:
            raise HTTPException(404, "invalid promo code")

        if promo.tg_id == tg.tg_id:
            raise HTTPException(400, "cannot use your own promo code")

        # Read discount before commit so attribute stays accessible
        discount = await _effective_discount(session, promo)

        if own:
            own.used_promo = code
            own.used_promo_consumed = False
        else:
            while True:
                gen = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
                exists = await _repo_promos.get_promo_by_code(session, gen)
                if not exists:
                    break
            session.add(Promo(tg_id=tg.tg_id, promo_code=gen, used_promo=code))

        await session.commit()

    return {
        "ok": True,
        "active_promo": code,
        "discount_percent": discount,
    }
