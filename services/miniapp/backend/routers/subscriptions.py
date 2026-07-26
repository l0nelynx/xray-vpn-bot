"""Telegram-authenticated account subscription management."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, status

from common_db.repo import subscriptions as subscription_repo

from ..android.managed_subscriptions_router import _serialize
from ..android.schemas_subscriptions import ManagedSubscriptionsResponse, SetPrimaryResponse
from ..database.session import async_session
from ..tg_auth import TgUser, get_tg_user
from common_db.repo import users as user_repo

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


async def _account_user(tg: TgUser):
    async with async_session() as session:
        user = await user_repo.get_user_by_tg_id(session, tg.tg_id)
    if user is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail={"code": "user_not_found"}
        )
    if user.is_banned:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail={"code": "user_banned"}
        )
    return user


@router.get("", response_model=ManagedSubscriptionsResponse)
async def list_subscriptions(
    tg: TgUser = Depends(get_tg_user),
) -> ManagedSubscriptionsResponse:
    user = await _account_user(tg)
    async with async_session() as session:
        rows = await subscription_repo.list_for_user(session, user.id)
    resolved = await asyncio.gather(*(_serialize(row) for row in rows))
    return ManagedSubscriptionsResponse(subscriptions=list(resolved))


@router.post("/{subscription_id}/primary", response_model=SetPrimaryResponse)
async def set_primary(
    subscription_id: int,
    tg: TgUser = Depends(get_tg_user),
) -> SetPrimaryResponse:
    user = await _account_user(tg)
    async with async_session() as session:
        row = await subscription_repo.set_primary(
            session, user_id=user.id, subscription_id=subscription_id
        )
        if row is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"code": "subscription_not_found"},
            )
        await session.commit()
    return SetPrimaryResponse(subscription_id=subscription_id)
