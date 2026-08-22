"""Authenticated multi-subscription API for first-party clients."""
from __future__ import annotations

import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError

from common_db.repo import subscriptions as subscription_repo
from remnawave_client import serialize_managed_subscription

from ..config import get_rw_free_id, get_rw_pro_id
from ..database.session import async_session
from . import deps, repo
from .auth_router import limiter
from .schemas_subscriptions import (
    AttachSubscriptionRequest,
    AttachSubscriptionResponse,
    ManagedSubscription,
    ManagedSubscriptionsResponse,
    SetPrimaryResponse,
)
from . import security

router = APIRouter(prefix="/api/android/subscriptions", tags=["managed-subscriptions"])


async def _serialize(row) -> ManagedSubscription:
    payload = await serialize_managed_subscription(
        row,
        free_squad_id=get_rw_free_id(),
        pro_squad_id=get_rw_pro_id(),
    )
    return ManagedSubscription(**payload)


@router.get("", response_model=ManagedSubscriptionsResponse)
@limiter.limit("60/minute")
async def list_subscriptions(
    request: Request,
    user: repo.UserRow = Depends(deps.get_current_user),
) -> ManagedSubscriptionsResponse:
    async with async_session() as session:
        rows = await subscription_repo.list_for_user(session, user.id)
    resolved = await asyncio.gather(*(_serialize(row) for row in rows))
    return ManagedSubscriptionsResponse(subscriptions=list(resolved))


@router.post("/{subscription_id}/primary", response_model=SetPrimaryResponse)
async def set_primary(
    subscription_id: int,
    user: repo.UserRow = Depends(deps.get_current_user),
) -> SetPrimaryResponse:
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


@router.post("/attach", response_model=AttachSubscriptionResponse)
async def attach_subscription(
    body: AttachSubscriptionRequest,
    user: repo.UserRow = Depends(deps.get_current_user),
) -> AttachSubscriptionResponse:
    try:
        rw_id, _ = security.decode_subscription_context(body.context)
    except security.JWTError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"code": "invalid_context"}
        ) from exc
    async with async_session() as session:
        try:
            linked = await subscription_repo.attach(
                session,
                user_id=user.id,
                rw_id=rw_id,
                source="subscription_page",
                label=body.label,
                make_primary=body.make_primary,
            )
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail={"code": str(exc)}
            ) from exc
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"code": "subscription_already_linked"},
            ) from exc
        await session.commit()
    return AttachSubscriptionResponse(
        subscription_id=linked.id, is_primary=linked.is_primary
    )
