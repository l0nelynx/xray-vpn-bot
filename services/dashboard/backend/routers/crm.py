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
from ..crm_actions import action_types_catalog
from ..crm_conditions import (
    condition_types_catalog,
    evaluate_conditions,
    segment_id_from_conditions,
    segment_types_catalog,
)
from ..crm_event_runner import run_crm_event
from ..crm_model_adapter import (
    flat_to_actions,
    flat_to_conditions,
    get_actions,
    get_conditions,
    sync_flat_from_model,
    validate_actions,
    validate_conditions,
)
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


def _prepare_crm_payload(
    conditions: list[dict],
    actions: list[dict],
) -> tuple[list[dict], list[dict], dict]:
    validate_conditions(conditions)
    validate_actions(actions)
    flat = sync_flat_from_model(conditions=conditions, actions=actions)
    return conditions, actions, flat


def _legacy_campaign_payload(body: "CreateCampaignRequest") -> tuple[list[dict], list[dict], dict]:
    params = dict(body.segment_params)
    if body.target_tg_ids:
        params["target_tg_ids"] = body.target_tg_ids
    conditions = flat_to_conditions(
        segment_type=body.segment_type,
        segment_params=params,
    )
    actions = flat_to_actions(
        message_text=body.message_text,
        attach_button=body.attach_button,
        bonus_days=body.bonus_days,
        bonus_traffic_gb=body.bonus_traffic_gb,
    )
    return _prepare_crm_payload(conditions, actions)


def _resolve_campaign_payload(body: "LaunchCampaignRequest") -> tuple[list[dict], list[dict], dict]:
    if body.conditions:
        return _prepare_crm_payload(body.conditions, body.actions)
    if body.segment_type:
        legacy = CreateCampaignRequest(
            name=body.name,
            segment_type=body.segment_type,
            segment_params=body.segment_params,
            message_text=body.message_text or "",
            attach_button=body.attach_button,
            bonus_days=body.bonus_days,
            bonus_traffic_gb=body.bonus_traffic_gb,
            target_tg_ids=body.target_tg_ids,
        )
        return _legacy_campaign_payload(legacy)
    raise HTTPException(400, "conditions or legacy segment_type required")


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
    user_type: str = Field(default="all", pattern="^(all|free|paid_vip)$")
    conditions: list[dict] = Field(default_factory=list)


class EvaluateConditionsRequest(BaseModel):
    conditions: list[dict]


class LaunchCampaignRequest(BaseModel):
    name: str = ""
    conditions: list[dict] = Field(default_factory=list)
    actions: list[dict] = Field(default_factory=list)
    # Legacy flat fields (adapter)
    segment_type: str | None = None
    segment_params: dict = Field(default_factory=dict)
    message_text: str = ""
    attach_button: bool = False
    bonus_days: int | None = Field(default=None, ge=0, le=365)
    bonus_traffic_gb: int | None = Field(default=None, ge=0, le=1000)
    target_tg_ids: list[int] = Field(default_factory=list)


class CreateCampaignRequest(LaunchCampaignRequest):
    pass


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
    conditions: list[dict]
    actions: list[dict]


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
    conditions: list[dict] = Field(default_factory=list)
    actions: list[dict] = Field(default_factory=list)
    # Legacy
    segment_type: str | None = None
    segment_params: dict = Field(default_factory=dict)
    message_text: str = ""
    attach_button: bool = False
    bonus_days: int | None = Field(default=None, ge=0, le=365)
    bonus_traffic_gb: int | None = Field(default=None, ge=0, le=1000)
    run_at_time: str = "01:00"
    frequency: str = Field(default="daily", pattern="^(daily|weekly)$")
    weekday: int | None = Field(default=None, ge=0, le=6)
    repeat_policy: str = Field(default="cooldown", pattern="^(always|once|cooldown)$")
    repeat_cooldown_days: int = Field(default=7, ge=1, le=365)


class CrmEventUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    conditions: list[dict] | None = None
    actions: list[dict] | None = None
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
    conditions: list[dict]
    actions: list[dict]
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


def _event_payload(body: CrmEventCreate | CrmEventUpdate, *, is_create: bool) -> tuple[list[dict], list[dict], dict]:
    if body.conditions:
        actions = body.actions if body.actions is not None else []
        if is_create and not actions:
            raise HTTPException(400, "actions required")
        return _prepare_crm_payload(body.conditions, actions)
    if is_create and not body.segment_type:
        raise HTTPException(400, "conditions or segment_type required")
    if body.segment_type:
        conditions = flat_to_conditions(
            segment_type=body.segment_type,
            segment_params=body.segment_params or {},
        )
        actions = flat_to_actions(
            message_text=body.message_text or "",
            attach_button=bool(body.attach_button),
            bonus_days=body.bonus_days,
            bonus_traffic_gb=body.bonus_traffic_gb,
        )
        return _prepare_crm_payload(conditions, actions)
    raise HTTPException(400, "conditions required")


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
    conditions = get_conditions(e)
    actions = get_actions(e)
    return CrmEventSummary(
        id=e.id,
        name=e.name,
        enabled=e.enabled,
        segment_type=e.segment_type,
        segment_params=json.loads(e.segment_params or "{}"),
        conditions=conditions,
        actions=actions,
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


@router.get("/conditions/types")
async def list_condition_types(_: str = Depends(get_current_user)):
    return {
        "condition_types": condition_types_catalog(),
        "segment_types": segment_types_catalog(),
    }


@router.get("/actions/types")
async def list_action_types(_: str = Depends(get_current_user)):
    return {"action_types": action_types_catalog()}


@router.post("/conditions/evaluate", response_model=ScanResponse)
async def evaluate_conditions_preview(
    body: EvaluateConditionsRequest,
    _: str = Depends(get_current_user),
):
    rw = _rw_client()
    async with async_session() as session:
        tg_ids, users, total, warning = await evaluate_conditions(
            session, rw, body.conditions
        )
        segment_id = segment_id_from_conditions(body.conditions) or ""
    return ScanResponse(
        segment_id=segment_id,
        total=total,
        users=[ScanUser(**u) for u in users],
        warning=warning,
    )


@router.get("/segments")
async def list_segments(_: str = Depends(get_current_user)):
    return {"segments": segment_types_catalog()}


@router.post("/segments/{segment_id}/scan", response_model=ScanResponse)
async def segment_scan(
    segment_id: str,
    body: ScanParams,
    _: str = Depends(get_current_user),
):
    valid_ids = {s["id"] for s in segment_types_catalog()}
    if segment_id not in valid_ids:
        raise HTTPException(404, f"Unknown segment: {segment_id}")

    rw = _rw_client()
    async with async_session() as session:
        if body.conditions:
            tg_ids, users, total, warning = await evaluate_conditions(
                session, rw, body.conditions
            )
            seg_id = segment_id_from_conditions(body.conditions) or segment_id
        else:
            users, total, warning = await scan_segment(
                session,
                rw,
                segment_id,
                days_threshold=body.days_threshold,
                traffic_threshold=body.traffic_threshold,
                invoice_max_age_hours=body.invoice_max_age_hours,
                torrent_days=body.torrent_days,
                user_type=body.user_type,
            )
            seg_id = segment_id

    return ScanResponse(
        segment_id=seg_id,
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
            conditions=get_conditions(c),
            actions=get_actions(c),
        )
        await session.commit()
    return detail


@router.post("/campaigns", response_model=CampaignSummary)
async def create_campaign(
    body: CreateCampaignRequest,
    user: str = Depends(get_current_user),
):
    try:
        conditions, actions, flat = _resolve_campaign_payload(body)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    store_targets = body.target_tg_ids or flat.get("segment_params", {}).get("target_tg_ids")

    async with async_session() as session:
        campaign = await crm_repo.create_campaign(
            session,
            name=body.name or f"CRM {flat.get('segment_type') or 'custom'}",
            conditions=conditions,
            actions=actions,
            segment_type=flat.get("segment_type"),
            segment_params=dict(flat.get("segment_params") or {}),
            message_text=flat.get("message_text") or "",
            attach_button=bool(flat.get("attach_button")),
            bonus_days=flat.get("bonus_days"),
            bonus_traffic_gb=flat.get("bonus_traffic_gb"),
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
    body: LaunchCampaignRequest,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Create a campaign and enqueue execution."""
    try:
        conditions, actions, flat = _resolve_campaign_payload(body)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if body.target_tg_ids:
        conditions = [c for c in conditions if c.get("type") != "tg_allowlist"]
        conditions.append({"type": "tg_allowlist", "tg_ids": body.target_tg_ids})

    async with async_session() as session:
        campaign = await crm_repo.create_campaign(
            session,
            name=body.name or f"CRM {flat.get('segment_type') or 'custom'}",
            conditions=conditions,
            actions=actions,
            segment_type=flat.get("segment_type"),
            segment_params=dict(flat.get("segment_params") or {}),
            message_text=flat.get("message_text") or "",
            attach_button=bool(flat.get("attach_button")),
            bonus_days=flat.get("bonus_days"),
            bonus_traffic_gb=flat.get("bonus_traffic_gb"),
            created_by=user,
            target_tg_ids=body.target_tg_ids or None,
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
    _validate_event_schedule(body)
    try:
        conditions, actions, flat = _event_payload(body, is_create=True)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    async with async_session() as session:
        event = await events_repo.create_event(
            session,
            name=body.name or f"Event {flat.get('segment_type') or 'crm'}",
            conditions=conditions,
            actions=actions,
            segment_type=flat.get("segment_type") or "",
            segment_params=dict(flat.get("segment_params") or {}),
            run_at_time=body.run_at_time,
            frequency=body.frequency,
            weekday=body.weekday,
            message_text=flat.get("message_text") or "",
            attach_button=bool(flat.get("attach_button")),
            bonus_days=flat.get("bonus_days"),
            bonus_traffic_gb=flat.get("bonus_traffic_gb"),
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
            "run_at_time",
            "frequency",
            "weekday",
            "repeat_policy",
            "repeat_cooldown_days",
        ):
            val = getattr(body, field)
            if val is not None:
                updates[field] = val

        if body.conditions is not None or body.actions is not None:
            conditions = body.conditions if body.conditions is not None else get_conditions(event)
            actions = body.actions if body.actions is not None else get_actions(event)
            try:
                _, _, flat = _prepare_crm_payload(conditions, actions)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            updates["conditions_json"] = json.dumps(conditions, ensure_ascii=False)
            updates["actions_json"] = json.dumps(actions, ensure_ascii=False)
            updates["segment_type"] = flat.get("segment_type")
            updates["segment_params"] = json.dumps(flat.get("segment_params") or {})
            updates["message_text"] = flat.get("message_text") or ""
            updates["attach_button"] = bool(flat.get("attach_button"))
            updates["bonus_days"] = flat.get("bonus_days")
            updates["bonus_traffic_gb"] = flat.get("bonus_traffic_gb")
        elif body.segment_type is not None:
            conditions = flat_to_conditions(
                segment_type=body.segment_type,
                segment_params=body.segment_params or {},
            )
            actions = flat_to_actions(
                message_text=body.message_text or event.message_text,
                attach_button=body.attach_button if body.attach_button is not None else event.attach_button,
                bonus_days=body.bonus_days if body.bonus_days is not None else event.bonus_days,
                bonus_traffic_gb=body.bonus_traffic_gb if body.bonus_traffic_gb is not None else event.bonus_traffic_gb,
            )
            _, _, flat = _prepare_crm_payload(conditions, actions)
            updates["conditions_json"] = json.dumps(conditions, ensure_ascii=False)
            updates["actions_json"] = json.dumps(actions, ensure_ascii=False)
            updates["segment_type"] = flat.get("segment_type")
            updates["segment_params"] = json.dumps(flat.get("segment_params") or {})
            updates["message_text"] = flat.get("message_text") or ""
            updates["attach_button"] = bool(flat.get("attach_button"))
            updates["bonus_days"] = flat.get("bonus_days")
            updates["bonus_traffic_gb"] = flat.get("bonus_traffic_gb")

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
