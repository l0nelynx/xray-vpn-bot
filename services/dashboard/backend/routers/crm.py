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
from ..crm_event_runner import run_crm_event
from ..crm_runner import resolve_targets
from ..crm_service import scan_segment, segment_catalog
from ..crm_templates import get_template, list_templates
from ..crm_variables import build_message_context, render_crm_message, variable_catalog
from ..database.session import async_session
from ..tasks.crm import enqueue_campaign

from common_db.repo import crm_events as events_repo

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


class MessagePreviewRequest(BaseModel):
    message_text: str
    sample_tg_id: int | None = None


class MessagePreviewResponse(BaseModel):
    rendered_text: str
    sample_tg_id: int | None = None


class CrmEventCreate(BaseModel):
    name: str = ""
    enabled: bool = True
    segment_type: str
    segment_params: dict = Field(default_factory=dict)
    run_at_time: str = "01:00"
    frequency: str = Field(default="daily", pattern="^(daily|weekly)$")
    weekday: int | None = Field(default=None, ge=0, le=6)
    message_text: str
    attach_button: bool = False
    bonus_days: int | None = Field(default=None, ge=0, le=365)
    bonus_traffic_gb: int | None = Field(default=None, ge=0, le=1000)
    repeat_policy: str = Field(default="cooldown", pattern="^(always|once|cooldown)$")
    repeat_cooldown_days: int = Field(default=7, ge=1, le=365)


class CrmEventUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    segment_type: str | None = None
    segment_params: dict | None = None
    run_at_time: str | None = None
    frequency: str | None = Field(default=None, pattern="^(daily|weekly)$")
    weekday: int | None = Field(default=None, ge=0, le=6)
    message_text: str | None = None
    attach_button: bool | None = None
    bonus_days: int | None = Field(default=None, ge=0, le=365)
    bonus_traffic_gb: int | None = Field(default=None, ge=0, le=1000)
    repeat_policy: str | None = Field(default=None, pattern="^(always|once|cooldown)$")
    repeat_cooldown_days: int | None = Field(default=None, ge=1, le=365)


class CrmEventSummary(BaseModel):
    id: int
    name: str
    enabled: bool
    segment_type: str | None
    segment_params: dict
    run_at_time: str
    frequency: str
    weekday: int | None
    message_text: str
    attach_button: bool
    bonus_days: int | None
    bonus_traffic_gb: int | None
    repeat_policy: str
    repeat_cooldown_days: int
    last_run_at: str | None
    next_run_at: str | None
    created_at: str
    updated_at: str
    created_by: str


def _validate_run_at_time(value: str) -> None:
    parts = value.split(":")
    if len(parts) != 2:
        raise HTTPException(400, "run_at_time must be HH:MM (UTC)")
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise HTTPException(400, "run_at_time must be HH:MM (UTC)") from exc
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise HTTPException(400, "run_at_time must be HH:MM (UTC)")


def _validate_event_schedule(body: CrmEventCreate | CrmEventUpdate) -> None:
    if isinstance(body, CrmEventCreate):
        _validate_run_at_time(body.run_at_time)
        if body.frequency == "weekly" and body.weekday is None:
            raise HTTPException(400, "weekday is required for weekly frequency")
        if body.repeat_policy == "cooldown" and not body.repeat_cooldown_days:
            raise HTTPException(400, "repeat_cooldown_days is required for cooldown policy")
    else:
        if body.run_at_time is not None:
            _validate_run_at_time(body.run_at_time)
        if body.frequency == "weekly" and body.weekday is None:
            raise HTTPException(400, "weekday is required for weekly frequency")


def _event_summary(e) -> CrmEventSummary:
    return CrmEventSummary(
        id=e.id,
        name=e.name,
        enabled=e.enabled,
        segment_type=e.segment_type,
        segment_params=json.loads(e.segment_params or "{}"),
        run_at_time=e.run_at_time,
        frequency=e.frequency,
        weekday=e.weekday,
        message_text=e.message_text,
        attach_button=e.attach_button,
        bonus_days=e.bonus_days,
        bonus_traffic_gb=e.bonus_traffic_gb,
        repeat_policy=e.repeat_policy,
        repeat_cooldown_days=e.repeat_cooldown_days,
        last_run_at=e.last_run_at,
        next_run_at=e.next_run_at,
        created_at=e.created_at,
        updated_at=e.updated_at,
        created_by=e.created_by,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Variables & templates
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/variables")
async def list_variables(_: str = Depends(get_current_user)):
    return {"variables": variable_catalog()}


@router.get("/templates")
async def list_message_templates(
    segment_id: str | None = None,
    _: str = Depends(get_current_user),
):
    return {"templates": list_templates(segment_id=segment_id)}


@router.get("/templates/{template_id}")
async def get_message_template(template_id: str, _: str = Depends(get_current_user)):
    tpl = get_template(template_id)
    if not tpl:
        raise HTTPException(404, "Template not found")
    return tpl


@router.post("/messages/preview", response_model=MessagePreviewResponse)
async def preview_message(
    body: MessagePreviewRequest,
    _: str = Depends(get_current_user),
):
    if not body.message_text.strip():
        raise HTTPException(400, "message_text is required")

    rw = _rw_client()
    crm_by_uuid: dict[str, dict] = {}
    try:
        for u in await rw.get_all_users_for_crm():
            if u.get("uuid"):
                crm_by_uuid[u["uuid"]] = u
    except Exception as exc:
        logger.warning("Preview: RW fetch failed: %s", exc)

    username = None
    crm_user = None
    meta: dict = {}

    if body.sample_tg_id:
        async with async_session() as session:
            from common_db.repo.users import get_users_by_tg_ids

            users = await get_users_by_tg_ids(session, [body.sample_tg_id])
            if users:
                db_user = users[0]
                username = db_user.username
                if db_user.vless_uuid:
                    crm_user = crm_by_uuid.get(db_user.vless_uuid)

    ctx = build_message_context(username=username, crm_user=crm_user, meta=meta)
    rendered = render_crm_message(body.message_text, ctx)
    return MessagePreviewResponse(
        rendered_text=rendered,
        sample_tg_id=body.sample_tg_id,
    )


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


# ──────────────────────────────────────────────────────────────────────────────
# Scheduled events (UTC)
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/events")
async def list_events(_: str = Depends(get_current_user)):
    async with async_session() as session:
        rows = await events_repo.list_events(session)
        await session.commit()
    return {"events": [_event_summary(e) for e in rows]}


@router.post("/events", response_model=CrmEventSummary)
async def create_event(
    body: CrmEventCreate,
    user: str = Depends(get_current_user),
):
    if not body.message_text.strip():
        raise HTTPException(400, "message_text is required")
    _validate_event_schedule(body)

    async with async_session() as session:
        event = await events_repo.create_event(
            session,
            name=body.name or f"Event {body.segment_type}",
            segment_type=body.segment_type,
            segment_params=body.segment_params,
            run_at_time=body.run_at_time,
            frequency=body.frequency,
            weekday=body.weekday,
            message_text=body.message_text,
            attach_button=body.attach_button,
            bonus_days=body.bonus_days,
            bonus_traffic_gb=body.bonus_traffic_gb,
            repeat_policy=body.repeat_policy,
            repeat_cooldown_days=body.repeat_cooldown_days,
            created_by=user,
            enabled=body.enabled,
        )
        await session.commit()
        summary = _event_summary(event)
    return summary


@router.get("/events/{event_id}", response_model=CrmEventSummary)
async def get_event(event_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        event = await events_repo.get_event(session, event_id)
        if not event:
            raise HTTPException(404, "Event not found")
        summary = _event_summary(event)
        await session.commit()
    return summary


@router.patch("/events/{event_id}", response_model=CrmEventSummary)
async def update_event(
    event_id: int,
    body: CrmEventUpdate,
    _: str = Depends(get_current_user),
):
    _validate_event_schedule(body)

    async with async_session() as session:
        event = await events_repo.get_event(session, event_id)
        if not event:
            raise HTTPException(404, "Event not found")

        updates: dict = {}
        for field in (
            "name",
            "enabled",
            "segment_type",
            "message_text",
            "attach_button",
            "bonus_days",
            "bonus_traffic_gb",
            "run_at_time",
            "frequency",
            "weekday",
            "repeat_policy",
            "repeat_cooldown_days",
        ):
            val = getattr(body, field)
            if val is not None:
                updates[field] = val
        if body.segment_params is not None:
            updates["segment_params"] = json.dumps(body.segment_params)

        schedule_changed = any(
            k in updates
            for k in ("run_at_time", "frequency", "weekday")
        )
        await events_repo.update_event(session, event, **updates)

        if schedule_changed:
            event.next_run_at = events_repo.compute_next_run_at(
                run_at_time=event.run_at_time,
                frequency=event.frequency,
                weekday=event.weekday,
            )

        await session.commit()
        summary = _event_summary(event)
    return summary


@router.delete("/events/{event_id}")
async def delete_event(event_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        event = await events_repo.get_event(session, event_id)
        if not event:
            raise HTTPException(404, "Event not found")
        await events_repo.delete_event(session, event)
        await session.commit()
    return {"status": "deleted"}


@router.post("/events/{event_id}/run-now")
async def run_event_now(
    event_id: int,
    request: Request,
    _: str = Depends(get_current_user),
):
    pool = getattr(request.app.state, "arq_pool", None)
    try:
        result = await run_crm_event(event_id, arq_pool=pool, force=True)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    if result.get("status") == "not_found":
        raise HTTPException(404, "Event not found")
    return result


@router.get("/events/{event_id}/campaigns")
async def list_event_campaigns(event_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        event = await events_repo.get_event(session, event_id)
        if not event:
            raise HTTPException(404, "Event not found")
        all_campaigns = await crm_repo.list_campaigns(session, limit=200)
        related = [c for c in all_campaigns if c.event_id == event_id]
        await session.commit()
    return {"campaigns": [_campaign_summary(c) for c in related]}
