"""FCM token registration for the Android client.

Mounted at `/api/android/fcm`. The client obtains a Firebase Messaging token
and registers it after login; unregister on logout.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from common_db.repo import fcm as fcm_repo

from ..database.session import async_session
from . import deps
from .auth_router import limiter
from .repo import UserRow
from .schemas import SimpleStatus

router = APIRouter(prefix="/api/android/fcm", tags=["android-fcm"])


class FcmTokenRequest(BaseModel):
    token: str = Field(min_length=10, max_length=4096)
    app_version: str | None = Field(default=None, max_length=64)
    platform: str = Field(default="android", max_length=20)


class FcmTokenDeleteRequest(BaseModel):
    token: str = Field(min_length=10, max_length=4096)


@router.post("/token", response_model=SimpleStatus, status_code=status.HTTP_200_OK)
@limiter.limit("30/minute")
async def register_token(
    request: Request,
    body: FcmTokenRequest,
    user: UserRow = Depends(deps.get_current_user),
):
    async with async_session() as session:
        await fcm_repo.upsert_token(
            session,
            user_id=user.id,
            token=body.token.strip(),
            platform=(body.platform or "android").strip() or "android",
            app_version=(body.app_version.strip() if body.app_version else None),
        )
        await session.commit()
    return SimpleStatus()


@router.delete("/token", response_model=SimpleStatus)
@limiter.limit("30/minute")
async def unregister_token(
    request: Request,
    body: FcmTokenDeleteRequest,
    user: UserRow = Depends(deps.get_current_user),
):
    async with async_session() as session:
        await fcm_repo.delete_token(
            session, user_id=user.id, token=body.token.strip()
        )
        await session.commit()
    return SimpleStatus()
