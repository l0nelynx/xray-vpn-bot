from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from ..auth import get_current_user
from ..database.models import TariffPlan, TariffPrice
from ..database.session import async_session
from ..schemas.tariffs import (
    TariffPlanSchema, TariffPlanCreate, TariffPlanUpdate,
    ReorderRequest,
)
from ..cache_utils import bump_cache_version

router = APIRouter(prefix="/api/tariffs", tags=["tariffs"])


@router.get("/plans", response_model=list[TariffPlanSchema])
async def list_plans(_: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(TariffPlan)
            .options(selectinload(TariffPlan.prices))
            .order_by(TariffPlan.sort_order)
        )
        plans = result.scalars().all()
        return [TariffPlanSchema.model_validate(p) for p in plans]


@router.get("/plans/{plan_id}", response_model=TariffPlanSchema)
async def get_plan(plan_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(TariffPlan)
            .options(selectinload(TariffPlan.prices))
            .where(TariffPlan.id == plan_id)
        )
        plan = result.scalar_one_or_none()
        if not plan:
            raise HTTPException(404, "Plan not found")
        return TariffPlanSchema.model_validate(plan)


@router.post("/plans", response_model=TariffPlanSchema)
async def create_plan(body: TariffPlanCreate, _: str = Depends(get_current_user)):
    async with async_session() as session:
        plan = TariffPlan(
            slug=body.slug,
            name_ru=body.name_ru,
            name_en=body.name_en,
            days=body.days,
            sort_order=body.sort_order,
            is_active=body.is_active,
            discount_percent=body.discount_percent,
            created_at=datetime.now().isoformat(),
        )
        session.add(plan)
        await session.flush()

        for p in body.prices:
            session.add(TariffPrice(
                tariff_id=plan.id,
                payment_method=p.payment_method,
                price=p.price,
                currency=p.currency,
                is_active=p.is_active,
            ))

        await session.commit()

        result = await session.execute(
            select(TariffPlan)
            .options(selectinload(TariffPlan.prices))
            .where(TariffPlan.id == plan.id)
        )
        await bump_cache_version()
        return TariffPlanSchema.model_validate(result.scalar_one())


@router.put("/plans/reorder")
async def reorder_plans(body: ReorderRequest, _: str = Depends(get_current_user)):
    async with async_session() as session:
        for item in body.items:
            await session.execute(
                update(TariffPlan)
                .where(TariffPlan.id == item.id)
                .values(sort_order=item.sort_order)
            )
        await session.commit()
    await bump_cache_version()
    return {"ok": True}


@router.put("/plans/{plan_id}", response_model=TariffPlanSchema)
async def update_plan(plan_id: int, body: TariffPlanUpdate, _: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(TariffPlan)
            .options(selectinload(TariffPlan.prices))
            .where(TariffPlan.id == plan_id)
        )
        plan = result.scalar_one_or_none()
        if not plan:
            raise HTTPException(404, "Plan not found")

        for field in ("slug", "name_ru", "name_en", "days", "sort_order", "is_active", "discount_percent"):
            val = getattr(body, field, None)
            if val is not None:
                setattr(plan, field, val)

        if body.prices is not None:
            # Remove existing prices and replace
            for existing in list(plan.prices):
                await session.delete(existing)
            await session.flush()

            for p in body.prices:
                session.add(TariffPrice(
                    tariff_id=plan.id,
                    payment_method=p.payment_method,
                    price=p.price,
                    currency=p.currency,
                    is_active=p.is_active,
                ))

        await session.commit()

        result = await session.execute(
            select(TariffPlan)
            .options(selectinload(TariffPlan.prices))
            .where(TariffPlan.id == plan.id)
        )
        await bump_cache_version()
        return TariffPlanSchema.model_validate(result.scalar_one())


@router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(TariffPlan).where(TariffPlan.id == plan_id)
        )
        plan = result.scalar_one_or_none()
        if not plan:
            raise HTTPException(404, "Plan not found")

        plan.is_active = False
        await session.commit()
    await bump_cache_version()
    return {"ok": True}
