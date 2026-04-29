import random
import string

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..database.models import Promo, PromoSettings
from ..database.session import async_session
from ..tg_auth import TgUser, get_tg_user

router = APIRouter(prefix="/api/promo", tags=["promo"])


class ActivateRequest(BaseModel):
    promo_code: str = Field(min_length=1, max_length=20)


async def _get_default_discount() -> int:
    async with async_session() as session:
        settings = await session.scalar(select(PromoSettings).where(PromoSettings.id == 1))
        return settings.default_discount_percent if settings else 20


async def _effective_discount(promo: Promo) -> int:
    if promo.discount_percent is not None:
        return promo.discount_percent
    return await _get_default_discount()


@router.get("")
async def get_promo_state(tg: TgUser = Depends(get_tg_user)):
    """Returns the user's current promo state."""
    async with async_session() as session:
        promo = await session.scalar(select(Promo).where(Promo.tg_id == tg.tg_id))

    default_discount = await _get_default_discount()

    # No promo or consumed promo → user can activate a new one
    if not promo or not promo.used_promo or promo.used_promo_consumed:
        return {
            "can_activate": True,
            "active_promo": None,
            "discount_percent": 0,
            "default_discount_percent": default_discount,
        }

    async with async_session() as session:
        owner_promo = await session.scalar(
            select(Promo).where(Promo.promo_code == promo.used_promo)
        )

    discount = await _effective_discount(owner_promo) if owner_promo else await _get_default_discount()
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
        own = await session.scalar(select(Promo).where(Promo.tg_id == tg.tg_id))

        # Same code can't be used twice by the same user
        if own and own.used_promo == code:
            raise HTTPException(409, "already used this promo code")

        # Active non-consumed promo blocks activation of a different one
        if own and own.used_promo and not own.used_promo_consumed:
            raise HTTPException(409, "promo already active — use it first")

        promo = await session.scalar(select(Promo).where(Promo.promo_code == code))
        if not promo:
            raise HTTPException(404, "invalid promo code")

        if promo.tg_id == tg.tg_id:
            raise HTTPException(400, "cannot use your own promo code")

        # Read discount before commit so attribute stays accessible
        discount = await _effective_discount(promo)

        if own:
            own.used_promo = code
            own.used_promo_consumed = False
        else:
            while True:
                gen = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
                exists = await session.scalar(select(Promo).where(Promo.promo_code == gen))
                if not exists:
                    break
            session.add(Promo(tg_id=tg.tg_id, promo_code=gen, used_promo=code))

        await session.commit()

    return {
        "ok": True,
        "active_promo": code,
        "discount_percent": discount,
    }
