"""Bot feature-flag settings endpoint.

GET  /api/settings/features  — returns current BotFeatureFlags row
PUT  /api/settings/features  — updates BotFeatureFlags row (auth required)

Changing legacy_bot_constructor requires a bot restart to take effect.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth import get_current_user
from ..database.session import async_session
from common_db.repo.system import get_bot_feature_flags

router = APIRouter(prefix="/api/settings", tags=["settings"])


class BotFeatureFlagsResponse(BaseModel):
    legacy_bot_constructor: bool


class BotFeatureFlagsRequest(BaseModel):
    legacy_bot_constructor: bool


@router.get("/features", response_model=BotFeatureFlagsResponse)
async def get_features(_: str = Depends(get_current_user)):
    async with async_session() as session:
        flags = await get_bot_feature_flags(session)
        await session.commit()
        return BotFeatureFlagsResponse(legacy_bot_constructor=flags.legacy_bot_constructor)


@router.put("/features", response_model=BotFeatureFlagsResponse)
async def update_features(body: BotFeatureFlagsRequest, _: str = Depends(get_current_user)):
    async with async_session() as session:
        flags = await get_bot_feature_flags(session)
        flags.legacy_bot_constructor = body.legacy_bot_constructor
        await session.commit()
        return BotFeatureFlagsResponse(legacy_bot_constructor=flags.legacy_bot_constructor)
