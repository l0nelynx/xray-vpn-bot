"""Authenticated, privacy-limited MiniApp funnel telemetry."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from common_db.models import MiniappUxEvent, Transaction
from common_db.repo import subscriptions as subscription_repo
from common_db.repo import users as user_repo

from ..android.auth_router import limiter
from ..database.session import async_session
from ..tg_auth import TgUser, get_tg_user

router = APIRouter(prefix="/api/ux", tags=["ux"])

EventName = Literal[
    "email_link_started",
    "email_link_succeeded",
    "email_link_failed",
    "onboarding_started",
    "onboarding_completed",
    "onboarding_skipped",
    "invoice_created",
    "payment_awaiting",
    "payment_processing",
    "payment_succeeded",
    "payment_failed",
    "connect_started",
    "app_install_opened",
    "subscription_add_opened",
    "connection_verified",
    "connection_help_opened",
]


class UxEventCreate(BaseModel):
    name: EventName
    onboarding_version: int | None = Field(default=None, ge=1, le=1000)
    subscription_id: int | None = Field(default=None, ge=1)
    transaction_id: str | None = Field(default=None, min_length=1, max_length=100)
    session_id: str | None = Field(default=None, min_length=1, max_length=64)
    platform: str | None = Field(default=None, max_length=32)
    source: str | None = Field(default=None, max_length=32)
    app: str | None = Field(default=None, max_length=64)
    outcome: str | None = Field(default=None, max_length=32)


@router.post("/events", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def create_ux_event(
    body: UxEventCreate,
    request: Request,
    tg: TgUser = Depends(get_tg_user),
) -> Response:
    async with async_session() as session:
        user = await user_repo.get_user_by_tg_id(session, tg.tg_id)
        if not user:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "user_not_found"})

        if body.subscription_id is not None:
            linked = await subscription_repo.get_for_user(
                session, user_id=user.id, subscription_id=body.subscription_id
            )
            if linked is None:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    detail={"code": "subscription_not_found"},
                )

        if body.transaction_id is not None:
            owned_transaction = (
                await session.execute(
                    select(Transaction.transaction_id).where(
                        Transaction.transaction_id == body.transaction_id,
                        Transaction.user_id == user.id,
                    )
                )
            ).scalar_one_or_none()
            if owned_transaction is None:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    detail={"code": "transaction_not_found"},
                )

        metadata = {
            key: value
            for key, value in {"app": body.app, "outcome": body.outcome}.items()
            if value is not None
        }
        session.add(
            MiniappUxEvent(
                user_id=user.id,
                subscription_id=body.subscription_id,
                transaction_id=body.transaction_id,
                name=body.name,
                onboarding_version=body.onboarding_version,
                session_id=body.session_id,
                platform=body.platform,
                source=body.source,
                metadata_json=metadata or None,
                created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
        )
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
