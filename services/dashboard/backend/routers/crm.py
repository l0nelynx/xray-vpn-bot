"""CRM router — user segments, campaigns, targeted broadcasts."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from remnawave_client.segmentation import SEGMENT_ALL_USERS

from common_db.repo import crm as crm_repo

from ..auth import get_current_user
from ..config import get_remnawave_token, get_remnawave_url
from ..crm_runner import resolve_targets
from ..crm_service import scan_segment, segment_catalog
from ..database.session import async_session
from ..tasks.crm import enqueue_campaign

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/crm", tags=["crm"])


def _rw_client():
    from remnawave_client import configure

    return configure(
        base_url=get_remnawave_url(),
        token=get_remnawave_token(),
        free_squad_id="",
    )


def _validate_audience(body: "CreateCampaignRequest") -> None:
    if body.segment_type == SEGMENT_ALL_USERS:
        return
    if not body.target_tg_ids:
        raise HTTPException(400, "target_tg_ids is required")


async def _schedule_campaign(
    request: Request,
    campaign_id: int,
    *,
    total_hint: int | None = None,
) -> dict:
    pool = getattr(request.app.state, "arq_pool", None)
    try:
        await enqueue_campaign(pool, campaign_id)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {
        "status": "queued",
        "total": total_hint,
        "campaign_id": campaign_id,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────────────


class ScanParams(BaseModel):
    days_threshold: int = Field(default=3, ge=1, le=30)
    traffic_threshold: float = Field(default=0.8, ge=0.5, le=0.95)
    invoice_max_age_hours: int = Field(default=48, ge=1, le=168)
    torrent_days: int = Field(default=7, ge=1, le=90)


class ScanUser(BaseModel):
    tg_id: int
    username: str | None
    vless_uuid: str | None
    meta: dict = Field(default_factory=dict)


class ScanResponse(BaseModel):
    segment_id: str
    total: int
    users: list[ScanUser]
    warning: str | None = None


class CreateCampaignRequest(BaseModel):
    name: str = ""
    segment_type: str | None = None
    segment_params: dict = Field(default_factory=dict)
    message_text: str
    attach_button: bool = False
    bonus_days: int | None = Field(default=None, ge=0, le=365)
    bonus_traffic_gb: int | None = Field(default=None, ge=0, le=1000)
    target_tg_ids: list[int] = Field(default_factory=list)


class CampaignSummary(BaseModel):
    id: int
    name: str
    segment_type: str | None
    status: str
    total_targets: int
    messages_sent: int
    messages_failed: int
    perks_applied: int
    perks_failed: int
    bonus_days: int | None
    bonus_traffic_gb: int | None
    created_at: str
    started_at: str | None
    completed_at: str | None
    created_by: str


class CampaignDetail(CampaignSummary):
    message_text: str
    attach_button: bool
    segment_params: dict


class ExecuteRequest(BaseModel):
    target_tg_ids: list[int] | None = None


class LaunchResponse(CampaignSummary):
    queue_status: str = "queued"


# ──────────────────────────────────────────────────────────────────────────────
# Segments
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/segments")
async def list_segments(_: str = Depends(get_current_user)):
    return {"segments": segment_catalog()}


@router.post("/segments/{segment_id}/scan", response_model=ScanResponse)
async def segment_scan(
    segment_id: str,
    body: ScanParams,
    _: str = Depends(get_current_user),
):
    valid_ids = {s["id"] for s in segment_catalog()}
    if segment_id not in valid_ids:
        raise HTTPException(404, f"Unknown segment: {segment_id}")

    rw = _rw_client()
    async with async_session() as session:
        users, total, warning = await scan_segment(
            session,
            rw,
            segment_id,
            days_threshold=body.days_threshold,
            traffic_threshold=body.traffic_threshold,
            invoice_max_age_hours=body.invoice_max_age_hours,
            torrent_days=body.torrent_days,
        )

    return ScanResponse(
        segment_id=segment_id,
        total=total,
        users=[ScanUser(**u) for u in users],
        warning=warning,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Campaigns
# ──────────────────────────────────────────────────────────────────────────────


def _campaign_summary(c) -> CampaignSummary:
    return CampaignSummary(
        id=c.id,
        name=c.name,
        segment_type=c.segment_type,
        status=c.status,
        total_targets=c.total_targets,
        messages_sent=c.messages_sent,
        messages_failed=c.messages_failed,
        perks_applied=c.perks_applied,
        perks_failed=c.perks_failed,
        bonus_days=c.bonus_days,
        bonus_traffic_gb=c.bonus_traffic_gb,
        created_at=c.created_at,
        started_at=c.started_at,
        completed_at=c.completed_at,
        created_by=c.created_by,
    )


@router.get("/campaigns")
async def list_campaigns(_: str = Depends(get_current_user)):
    async with async_session() as session:
        rows = await crm_repo.list_campaigns(session)
        await session.commit()
    return {"campaigns": [_campaign_summary(c) for c in rows]}


@router.get("/campaigns/{campaign_id}", response_model=CampaignDetail)
async def get_campaign(campaign_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        c = await crm_repo.get_campaign(session, campaign_id)
        if not c:
            raise HTTPException(404, "Campaign not found")
        detail = CampaignDetail(
            **_campaign_summary(c).model_dump(),
            message_text=c.message_text,
            attach_button=c.attach_button,
            segment_params=json.loads(c.segment_params or "{}"),
        )
        await session.commit()
    return detail


@router.post("/campaigns", response_model=CampaignSummary)
async def create_campaign(
    body: CreateCampaignRequest,
    user: str = Depends(get_current_user),
):
    if not body.message_text.strip():
        raise HTTPException(400, "message_text is required")
    _validate_audience(body)

    store_targets = (
        None
        if body.segment_type == SEGMENT_ALL_USERS
        else body.target_tg_ids
    )

    async with async_session() as session:
        campaign = await crm_repo.create_campaign(
            session,
            name=body.name or f"CRM {body.segment_type or 'custom'}",
            segment_type=body.segment_type,
            segment_params=body.segment_params,
            message_text=body.message_text,
            attach_button=body.attach_button,
            bonus_days=body.bonus_days,
            bonus_traffic_gb=body.bonus_traffic_gb,
            created_by=user,
            target_tg_ids=store_targets,
        )
        await session.commit()
        summary = _campaign_summary(campaign)
    return summary


@router.post("/campaigns/{campaign_id}/execute")
async def execute_campaign(
    campaign_id: int,
    body: ExecuteRequest,
    request: Request,
    _: str = Depends(get_current_user),
):
    async with async_session() as session:
        campaign = await crm_repo.get_campaign(session, campaign_id)
        if not campaign:
            raise HTTPException(404, "Campaign not found")
        if campaign.status in ("queued", "running"):
            raise HTTPException(409, "Campaign is already queued or running")
        tg_ids = await resolve_targets(session, campaign, body.target_tg_ids)
        if not tg_ids:
            raise HTTPException(400, "No target users")
        await crm_repo.queue_campaign(session, campaign)
        await session.commit()
        total = len(tg_ids)

    return await _schedule_campaign(request, campaign_id, total_hint=total)


@router.post("/campaigns/launch", response_model=LaunchResponse)
async def launch_campaign(
    body: CreateCampaignRequest,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Create a campaign and enqueue execution."""
    if not body.message_text.strip():
        raise HTTPException(400, "message_text is required")
    _validate_audience(body)

    store_targets = (
        None
        if body.segment_type == SEGMENT_ALL_USERS
        else body.target_tg_ids
    )

    async with async_session() as session:
        campaign = await crm_repo.create_campaign(
            session,
            name=body.name or f"CRM {body.segment_type or 'custom'}",
            segment_type=body.segment_type,
            segment_params=body.segment_params,
            message_text=body.message_text,
            attach_button=body.attach_button,
            bonus_days=body.bonus_days,
            bonus_traffic_gb=body.bonus_traffic_gb,
            created_by=user,
            target_tg_ids=store_targets,
        )
        tg_ids = await resolve_targets(session, campaign, None)
        if not tg_ids:
            raise HTTPException(400, "No target users")
        campaign.total_targets = len(tg_ids)
        await crm_repo.queue_campaign(session, campaign)
        await session.commit()
        summary = _campaign_summary(campaign)
        total = len(tg_ids)

    await _schedule_campaign(request, summary.id, total_hint=total)
    return LaunchResponse(**summary.model_dump(), queue_status="queued")
