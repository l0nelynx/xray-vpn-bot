from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import aliased

from ..auth import get_current_user
from ..database.models import Promo, User
from ..database.session import async_session

router = APIRouter(prefix="/api/promos", tags=["promos"])


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
            })

    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/{code}/users")
async def promo_users(code: str, _: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(Promo.tg_id, User.username)
            .outerjoin(User, Promo.tg_id == User.tg_id)
            .where(Promo.used_promo == code)
        )
        return [{"tg_id": row[0], "username": row[1]} for row in result.all()]
