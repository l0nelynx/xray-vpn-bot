from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func

from ..auth import get_current_user
from ..database.models import SquadProfile, TariffPlan
from ..database.session import async_session
from ..schemas.squads import SquadProfileSchema, SquadProfileCreate, SquadProfileUpdate

router = APIRouter(prefix="/api/squads", tags=["squads"])


@router.get("", response_model=list[SquadProfileSchema])
async def list_squads(_: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(select(SquadProfile).order_by(SquadProfile.id))
        return [SquadProfileSchema.model_validate(s) for s in result.scalars().all()]


@router.post("", response_model=SquadProfileSchema)
async def create_squad(body: SquadProfileCreate, _: str = Depends(get_current_user)):
    async with async_session() as session:
        squad = SquadProfile(
            name=body.name,
            squad_id=body.squad_id,
            external_squad_id=body.external_squad_id,
        )
        session.add(squad)
        await session.commit()
        await session.refresh(squad)
        return SquadProfileSchema.model_validate(squad)


@router.put("/{squad_id}", response_model=SquadProfileSchema)
async def update_squad(squad_id: int, body: SquadProfileUpdate, _: str = Depends(get_current_user)):
    async with async_session() as session:
        squad = await session.get(SquadProfile, squad_id)
        if not squad:
            raise HTTPException(404, "Squad profile not found")

        for field in ("name", "squad_id", "external_squad_id"):
            val = getattr(body, field, None)
            if val is not None:
                setattr(squad, field, val)

        await session.commit()
        await session.refresh(squad)
        return SquadProfileSchema.model_validate(squad)


@router.delete("/{squad_id}")
async def delete_squad(squad_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        squad = await session.get(SquadProfile, squad_id)
        if not squad:
            raise HTTPException(404, "Squad profile not found")

        # Check if any tariff uses this squad profile
        count = await session.scalar(
            select(func.count()).select_from(TariffPlan).where(TariffPlan.squad_profile_id == squad_id)
        )
        if count and count > 0:
            raise HTTPException(409, "Profile is in use by tariffs")

        await session.delete(squad)
        await session.commit()
        return {"ok": True}
