from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete

from ..auth import get_current_user
from ..database.models import Promo, PromoRedemption, User
from ..database.session import async_session

# Shared promo lookups + singleton PromoSettings helper. The settings
# helper auto-seeds the row on first access, so /api/promos/settings GET
# now returns the configured default (20%) on a fresh DB instead of a
# silent 0%.
from common_db.repo import promos as _repo_promos
from common_db.repo import system as _repo_system
from common_db.models.promos import PROMO_TYPE_PROMOTIONAL, PROMO_TYPE_REFERRAL

router = APIRouter(prefix="/api/promos", tags=["promos"])

_VALID_TYPES = {PROMO_TYPE_REFERRAL, PROMO_TYPE_PROMOTIONAL}


class PromoCreateRequest(BaseModel):
    promo_code: str = Field(min_length=2, max_length=20)
    discount_percent: int | None = Field(default=None, ge=0, le=100)
    owner_tg_id: int | None = None
    promo_type: str = Field(default=PROMO_TYPE_PROMOTIONAL)


class PromoSettingsRequest(BaseModel):
    default_discount_percent: int = Field(ge=0, le=100)
    days_reward_per_30: int = Field(ge=0, le=365)
    reward_cap_days: int = Field(ge=0, le=3650)


@router.get("")
async def list_promos(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _: str = Depends(get_current_user),
):
    async with async_session() as session:
        # Shared 1-based paginated query (counts redemptions for usage_count).
        items, total = await _repo_promos.list_promos_paginated(
            session, page, per_page
        )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.post("")
async def create_promo(body: PromoCreateRequest, _: str = Depends(get_current_user)):
    code = body.promo_code.strip().upper()
    if not code:
        raise HTTPException(400, "promo_code required")

    promo_type = body.promo_type if body.promo_type in _VALID_TYPES else PROMO_TYPE_PROMOTIONAL

    async with async_session() as session:
        existing = await _repo_promos.get_promo_by_code(session, code)
        if existing:
            raise HTTPException(409, "promo code already exists")

        # Manually-created promos use a synthetic owner tg_id (negative ids never collide
        # with real Telegram users) unless an explicit owner is provided.
        owner_tg_id = body.owner_tg_id
        if owner_tg_id is None:
            min_tg_id = await session.scalar(select(func.min(Promo.tg_id))) or 0
            owner_tg_id = min(min_tg_id, 0) - 1
        else:
            taken = await _repo_promos.get_promo_by_tg_id(session, owner_tg_id)
            if taken:
                raise HTTPException(409, f"tg_id {owner_tg_id} already owns a promo")

        promo = Promo(
            tg_id=owner_tg_id,
            promo_code=code,
            discount_percent=body.discount_percent,
            promo_type=promo_type,
        )
        session.add(promo)
        await session.commit()

    return {
        "promo_code": code,
        "owner_tg_id": owner_tg_id,
        "discount_percent": body.discount_percent,
        "promo_type": promo_type,
    }


@router.delete("/{code}")
async def delete_promo(code: str, _: str = Depends(get_current_user)):
    async with async_session() as session:
        promo = await _repo_promos.get_promo_by_code(session, code)
        if not promo:
            raise HTTPException(404, "promo not found")
        # Drop redemption history for the code, then the catalog row.
        await session.execute(
            delete(PromoRedemption).where(PromoRedemption.promo_code == code)
        )
        await session.execute(delete(Promo).where(Promo.promo_code == code))
        await session.commit()
    return {"ok": True}


@router.get("/settings")
async def get_promo_settings(_: str = Depends(get_current_user)):
    async with async_session() as session:
        # Auto-seeds the singleton on first access — no more silent 0%.
        settings = await _repo_system.get_promo_settings(session)
        await session.commit()
        return {
            "default_discount_percent": settings.default_discount_percent,
            "days_reward_per_30": settings.days_reward_per_30,
            "reward_cap_days": settings.reward_cap_days,
        }


@router.put("/settings")
async def update_promo_settings(
    body: PromoSettingsRequest,
    _: str = Depends(get_current_user),
):
    async with async_session() as session:
        settings = await _repo_system.get_promo_settings(session)
        settings.default_discount_percent = body.default_discount_percent
        settings.days_reward_per_30 = body.days_reward_per_30
        settings.reward_cap_days = body.reward_cap_days
        await session.commit()
    return {
        "default_discount_percent": body.default_discount_percent,
        "days_reward_per_30": body.days_reward_per_30,
        "reward_cap_days": body.reward_cap_days,
    }


@router.get("/{code}/users")
async def promo_users(code: str, _: str = Depends(get_current_user)):
    async with async_session() as session:
        return await _repo_promos.get_promo_redeemers(session, code)
