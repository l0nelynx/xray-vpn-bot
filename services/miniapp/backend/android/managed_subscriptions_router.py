"""Authenticated multi-subscription API for first-party clients."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status

from common_db.repo import subscriptions as subscription_repo
from remnawave_client.api import get_user_devices_count_by_id, get_user_from_id

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


def _tariff(active_squads: list[str]) -> str:
    squads = {str(value).lower() for value in active_squads}
    pro = get_rw_pro_id().lower()
    free = get_rw_free_id().lower()
    if pro and pro in squads:
        return "Premium"
    if free and free in squads:
        return "Free"
    return "—"


def _days_left(expire_ts: int | None) -> int:
    if expire_ts is None:
        return 0
    return max(0, round((int(expire_ts) - time.time()) / 86400))


def _expire_iso(expire_ts: int | None) -> str | None:
    if expire_ts is None:
        return None
    return datetime.fromtimestamp(int(expire_ts), tz=timezone.utc).isoformat()


async def _serialize(row) -> ManagedSubscription | None:
    rem_user, devices = await asyncio.gather(
        get_user_from_id(row.rw_id),
        get_user_devices_count_by_id(row.rw_id),
    )
    if rem_user is None:
        return None
    expire = rem_user.get("expire")
    return ManagedSubscription(
        id=row.id,
        rw_id=row.rw_id,
        label=row.label,
        product_key=row.product_key,
        source=row.source,
        is_primary=row.is_primary,
        tariff=_tariff(rem_user.get("active_squads", [])),
        status=rem_user.get("status"),
        days_left=_days_left(expire),
        expire_iso=_expire_iso(expire),
        data_limit_gb=rem_user.get("data_limit"),
        traffic_used_gb=rem_user.get("traffic_used", 0),
        devices_count=devices,
        subscription_url=rem_user.get("subscription_url"),
    )


@router.get("", response_model=ManagedSubscriptionsResponse)
@limiter.limit("60/minute")
async def list_subscriptions(
    request: Request,
    user: repo.UserRow = Depends(deps.get_current_user),
) -> ManagedSubscriptionsResponse:
    async with async_session() as session:
        rows = await subscription_repo.list_for_user(session, user.id)
    resolved = await asyncio.gather(*(_serialize(row) for row in rows))
    return ManagedSubscriptionsResponse(
        subscriptions=[item for item in resolved if item is not None]
    )


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
        await session.commit()
    return AttachSubscriptionResponse(
        subscription_id=linked.id, is_primary=linked.is_primary
    )
