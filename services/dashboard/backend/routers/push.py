"""Dashboard FCM push campaigns — compose, preview, launch, history."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field

from common_db.repo import fcm as fcm_repo
from common_db.repo import push as push_repo

from ..auth import get_current_user
from ..database.session import async_session
from ..fcm_sender import fcm_configured
from ..tasks.push import enqueue_push_campaign

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/push", tags=["push"])

_VALID_AUDIENCES = frozenset({"all_tokens", "user_ids"})


class PushCampaignCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)
    data: dict[str, str] | None = None
    audience: str = Field(default="all_tokens")
    user_ids: list[int] | None = None


class PushPreviewRequest(BaseModel):
    audience: str = Field(default="all_tokens")
    user_ids: list[int] | None = None


class PushCampaignSummary(BaseModel):
    id: int
    title: str
    body: str
    data: dict
    audience: str
    audience_params: dict
    status: str
    total_targets: int
    sent: int
    failed: int
    created_at: str
    started_at: str | None
    completed_at: str | None
    created_by: str


def _summary(campaign) -> PushCampaignSummary:
    return PushCampaignSummary(
        id=campaign.id,
        title=campaign.title or "",
        body=campaign.body or "",
        data=push_repo.get_data(campaign),
        audience=campaign.audience or "all_tokens",
        audience_params=push_repo.get_audience_params(campaign),
        status=campaign.status,
        total_targets=campaign.total_targets or 0,
        sent=campaign.sent or 0,
        failed=campaign.failed or 0,
        created_at=campaign.created_at,
        started_at=campaign.started_at,
        completed_at=campaign.completed_at,
        created_by=campaign.created_by or "",
    )


def _normalize_audience(audience: str, user_ids: list[int] | None) -> tuple[str, dict]:
    aud = (audience or "all_tokens").strip()
    if aud not in _VALID_AUDIENCES:
        raise HTTPException(400, f"Invalid audience: {audience}")
    params: dict = {}
    if aud == "user_ids":
        ids = [int(x) for x in (user_ids or []) if x is not None]
        if not ids:
            raise HTTPException(400, "user_ids required for audience=user_ids")
        params["user_ids"] = ids
    return aud, params


async def _count_for_audience(session, audience: str, params: dict) -> int:
    if audience == "user_ids":
        tokens = await fcm_repo.list_tokens_for_users(
            session, list(params.get("user_ids") or [])
        )
        return len(tokens)
    return await fcm_repo.count_tokens(session)


async def _schedule_campaign(request: Request, campaign_id: int) -> None:
    pool = getattr(request.app.state, "arq_pool", None)
    try:
        await enqueue_push_campaign(pool, campaign_id)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.get("/stats")
async def push_stats(_: str = Depends(get_current_user)):
    async with async_session() as session:
        token_count = await fcm_repo.count_tokens(session)
    return {
        "token_count": token_count,
        "fcm_configured": fcm_configured(),
    }


@router.post("/preview-count")
async def preview_count(
    body: PushPreviewRequest,
    _: str = Depends(get_current_user),
):
    audience, params = _normalize_audience(body.audience, body.user_ids)
    async with async_session() as session:
        count = await _count_for_audience(session, audience, params)
    return {"count": count, "audience": audience}


@router.get("/campaigns")
async def list_campaigns(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: str = Depends(get_current_user),
):
    async with async_session() as session:
        rows = await push_repo.list_campaigns(session, limit=limit, offset=offset)
    return {"campaigns": [_summary(c) for c in rows]}


@router.get("/campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: int,
    _: str = Depends(get_current_user),
):
    async with async_session() as session:
        campaign = await push_repo.get_campaign(session, campaign_id)
        if not campaign:
            raise HTTPException(404, "Campaign not found")
        return _summary(campaign)


@router.post("/campaigns", response_model=PushCampaignSummary)
async def create_campaign(
    body: PushCampaignCreate,
    user: str = Depends(get_current_user),
):
    audience, params = _normalize_audience(body.audience, body.user_ids)
    data = body.data or {}
    # FCM data values must be strings
    data_str = {str(k): str(v) for k, v in data.items()}
    async with async_session() as session:
        campaign = await push_repo.create_campaign(
            session,
            title=body.title,
            body=body.body,
            data=data_str,
            audience=audience,
            audience_params=params,
            created_by=user,
        )
        await session.commit()
        await session.refresh(campaign)
        return _summary(campaign)


@router.post("/campaigns/{campaign_id}/launch", response_model=PushCampaignSummary)
async def launch_campaign(
    campaign_id: int,
    request: Request,
    _: str = Depends(get_current_user),
):
    if not fcm_configured():
        raise HTTPException(
            503,
            "FCM is not configured (fcm_project_id / fcm_service_account_path)",
        )

    async with async_session() as session:
        campaign = await push_repo.get_campaign(session, campaign_id)
        if not campaign:
            raise HTTPException(404, "Campaign not found")
        if campaign.status not in ("draft", "failed"):
            raise HTTPException(
                409, f"Campaign cannot be launched from status={campaign.status}"
            )

        params = push_repo.get_audience_params(campaign)
        total = await _count_for_audience(session, campaign.audience, params)
        if total == 0:
            raise HTTPException(400, "No FCM tokens match this audience")

        await push_repo.queue_campaign(session, campaign, total_targets=total)
        await session.commit()
        summary = _summary(campaign)

    await _schedule_campaign(request, campaign_id)
    return summary


@router.post("/campaigns/launch", response_model=PushCampaignSummary)
async def create_and_launch(
    body: PushCampaignCreate,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Create a draft and enqueue it in one step (Dashboard Compose)."""
    if not fcm_configured():
        raise HTTPException(
            503,
            "FCM is not configured (fcm_project_id / fcm_service_account_path)",
        )

    audience, params = _normalize_audience(body.audience, body.user_ids)
    data_str = {str(k): str(v) for k, v in (body.data or {}).items()}

    async with async_session() as session:
        total = await _count_for_audience(session, audience, params)
        if total == 0:
            raise HTTPException(400, "No FCM tokens match this audience")

        campaign = await push_repo.create_campaign(
            session,
            title=body.title,
            body=body.body,
            data=data_str,
            audience=audience,
            audience_params=params,
            created_by=user,
        )
        await push_repo.queue_campaign(session, campaign, total_targets=total)
        await session.commit()
        campaign_id = campaign.id
        summary = _summary(campaign)

    await _schedule_campaign(request, campaign_id)
    return summary
