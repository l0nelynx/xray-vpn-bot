from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete, or_

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
    credit_grant: int | None = Field(default=None, ge=0, le=3650)
    owner_tg_id: int | None = None
    promo_type: str = Field(default=PROMO_TYPE_PROMOTIONAL)


class PromoSettingsRequest(BaseModel):
    default_credit_grant: int = Field(ge=0, le=3650)
    points_reward_per_30: int = Field(ge=0, le=3650)
    reward_cap_points: int = Field(ge=0, le=365_000)


@router.get("")
async def list_promos(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort: str = Query("id"),
    order: str = Query("desc"),
    search: str = Query(""),
    type: str = Query("all"),
    _: str = Depends(get_current_user),
):
    """Paginated promo catalog with per-column sort, type filter and
    code/owner search. Mirrors the shared list_promos_paginated shape but
    adds the dashboard-only controls."""
    usage_sq = (
        select(func.count())
        .select_from(PromoRedemption)
        .where(PromoRedemption.promo_code == Promo.promo_code)
        .correlate(Promo)
        .scalar_subquery()
        .label("usage_count")
    )
    sort_columns = {
        "id": Promo.id,
        "promo_code": Promo.promo_code,
        "promo_type": Promo.promo_type,
        "owner_username": User.username,
        "owner_tg_id": Promo.tg_id,
        "usage_count": usage_sq,
        "days_purchased": Promo.days_purchased,
        "points_rewarded": Promo.points_rewarded,
        "discount_percent": Promo.discount_percent,
        "credit_grant": Promo.credit_grant,
    }

    async with async_session() as session:
        base = select(Promo, User.username, usage_sq).outerjoin(
            User, Promo.tg_id == User.tg_id
        )

        if type in _VALID_TYPES:
            base = base.where(Promo.promo_type == type)
        if search:
            like = f"%{search.strip()}%"
            conds = [Promo.promo_code.ilike(like), User.username.ilike(like)]
            if search.strip().lstrip("-").isdigit():
                conds.append(Promo.tg_id == int(search.strip()))
            base = base.where(or_(*conds))

        total = await session.scalar(
            select(func.count()).select_from(base.subquery())
        ) or 0

        sort_col = sort_columns.get(sort, Promo.id)
        base = base.order_by(sort_col.asc() if order == "asc" else sort_col.desc())

        offset = (page - 1) * per_page
        rows = (await session.execute(base.offset(offset).limit(per_page))).all()
        items = [
            {
                "promo_code": promo.promo_code,
                "promo_type": promo.promo_type,
                "owner_username": owner_username,
                "owner_tg_id": promo.tg_id,
                "usage_count": usage_count or 0,
                "days_purchased": promo.days_purchased,
                "points_rewarded": promo.points_rewarded,
                "discount_percent": promo.discount_percent,
                "credit_grant": promo.credit_grant,
            }
            for promo, owner_username, usage_count in rows
        ]
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
            credit_grant=body.credit_grant,
            promo_type=promo_type,
        )
        session.add(promo)
        await session.commit()

    return {
        "promo_code": code,
        "owner_tg_id": owner_tg_id,
        "credit_grant": body.credit_grant,
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
            "default_credit_grant": settings.default_credit_grant,
            "default_discount_percent": settings.default_discount_percent,
            "points_reward_per_30": settings.points_reward_per_30,
            "reward_cap_points": settings.reward_cap_points,
        }


@router.put("/settings")
async def update_promo_settings(
    body: PromoSettingsRequest,
    _: str = Depends(get_current_user),
):
    async with async_session() as session:
        settings = await _repo_system.get_promo_settings(session)
        settings.default_credit_grant = body.default_credit_grant
        settings.points_reward_per_30 = body.points_reward_per_30
        settings.reward_cap_points = body.reward_cap_points
        await session.commit()
    return {
        "default_credit_grant": body.default_credit_grant,
        "points_reward_per_30": body.points_reward_per_30,
        "reward_cap_points": body.reward_cap_points,
    }


@router.get("/{code}/users")
async def promo_users(code: str, _: str = Depends(get_current_user)):
    async with async_session() as session:
        return await _repo_promos.get_promo_redeemers(session, code)
