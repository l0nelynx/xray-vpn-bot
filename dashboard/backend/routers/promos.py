from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete
from sqlalchemy.orm import aliased

from ..auth import get_current_user
from ..database.models import Promo, PromoSettings, User
from ..database.session import async_session

router = APIRouter(prefix="/api/promos", tags=["promos"])


class PromoCreateRequest(BaseModel):
    promo_code: str = Field(min_length=2, max_length=20)
    discount_percent: int | None = Field(default=None, ge=0, le=100)
    owner_tg_id: int | None = None


class PromoSettingsRequest(BaseModel):
    default_discount_percent: int = Field(ge=0, le=100)


@router.get("")
async def list_promos(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _: str = Depends(get_current_user),
):
    async with async_session() as session:
        UsedPromo = aliased(Promo)
        usage_sq = (
            select(func.count())
            .where(UsedPromo.used_promo == Promo.promo_code)
            .correlate(Promo)
            .scalar_subquery()
            .label("usage_count")
        )

        base = (
            select(Promo, User.username, usage_sq)
            .outerjoin(User, Promo.tg_id == User.tg_id)
        )

        total = await session.scalar(select(func.count()).select_from(Promo)) or 0

        offset = (page - 1) * per_page
        result = await session.execute(
            base.order_by(Promo.id).offset(offset).limit(per_page)
        )
        rows = result.all()

        items = []
        for promo, owner_username, usage_count in rows:
            items.append({
                "promo_code": promo.promo_code,
                "owner_username": owner_username,
                "owner_tg_id": promo.tg_id,
                "usage_count": usage_count or 0,
                "days_purchased": promo.days_purchased,
                "days_rewarded": promo.days_rewarded,
                "discount_percent": promo.discount_percent,
            })

    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.post("")
async def create_promo(body: PromoCreateRequest, _: str = Depends(get_current_user)):
    code = body.promo_code.strip().upper()
    if not code:
        raise HTTPException(400, "promo_code required")

    async with async_session() as session:
        existing = await session.scalar(select(Promo).where(Promo.promo_code == code))
        if existing:
            raise HTTPException(409, "promo code already exists")

        # Manually-created promos use a synthetic owner tg_id (negative ids never collide
        # with real Telegram users) unless an explicit owner is provided.
        owner_tg_id = body.owner_tg_id
        if owner_tg_id is None:
            min_tg_id = await session.scalar(select(func.min(Promo.tg_id))) or 0
            owner_tg_id = min(min_tg_id, 0) - 1
        else:
            taken = await session.scalar(select(Promo).where(Promo.tg_id == owner_tg_id))
            if taken:
                raise HTTPException(409, f"tg_id {owner_tg_id} already owns a promo")

        promo = Promo(
            tg_id=owner_tg_id,
            promo_code=code,
            discount_percent=body.discount_percent,
        )
        session.add(promo)
        await session.commit()

    return {
        "promo_code": code,
        "owner_tg_id": owner_tg_id,
        "discount_percent": body.discount_percent,
    }


@router.delete("/{code}")
async def delete_promo(code: str, _: str = Depends(get_current_user)):
    async with async_session() as session:
        promo = await session.scalar(select(Promo).where(Promo.promo_code == code))
        if not promo:
            raise HTTPException(404, "promo not found")
        # Clear used_promo on users who used it
        await session.execute(
            Promo.__table__.update()
            .where(Promo.used_promo == code)
            .values(used_promo=None)
        )
        await session.execute(delete(Promo).where(Promo.promo_code == code))
        await session.commit()
    return {"ok": True}


@router.get("/settings")
async def get_promo_settings(_: str = Depends(get_current_user)):
    async with async_session() as session:
        settings = await session.scalar(select(PromoSettings).where(PromoSettings.id == 1))
        return {
            "default_discount_percent": settings.default_discount_percent if settings else 20,
        }


@router.put("/settings")
async def update_promo_settings(
    body: PromoSettingsRequest,
    _: str = Depends(get_current_user),
):
    async with async_session() as session:
        settings = await session.scalar(select(PromoSettings).where(PromoSettings.id == 1))
        if not settings:
            settings = PromoSettings(id=1, default_discount_percent=body.default_discount_percent)
            session.add(settings)
        else:
            settings.default_discount_percent = body.default_discount_percent
        await session.commit()
    return {"default_discount_percent": body.default_discount_percent}


@router.get("/{code}/users")
async def promo_users(code: str, _: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(Promo.tg_id, User.username)
            .outerjoin(User, Promo.tg_id == User.tg_id)
            .where(Promo.used_promo == code)
        )
        return [{"tg_id": row[0], "username": row[1]} for row in result.all()]
