"""CRM router — user segments, campaigns, targeted broadcasts."""

from __future__ import annotations

import asyncio
import json
import logging

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from common_db.repo import crm as crm_repo
from common_db.repo.users import get_users_by_tg_ids

from ..auth import get_current_user
from ..config import get_remnawave_token, get_remnawave_url
from ..crm_service import apply_campaign_perks, scan_segment, segment_catalog
from ..database.session import async_session
from .tg_admin import _tg_send, _tg_url

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/crm", tags=["crm"])


def _rw_client():
    from remnawave_client import configure

    return configure(
        base_url=get_remnawave_url(),
        token=get_remnawave_token(),
        free_squad_id="",
    )


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
    if not body.target_tg_ids:
        raise HTTPException(400, "target_tg_ids is required")

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
            target_tg_ids=body.target_tg_ids,
        )
        await session.commit()
        summary = _campaign_summary(campaign)
    return summary


async def _resolve_targets(
    campaign,
    override_tg_ids: list[int] | None,
) -> list[int]:
    if override_tg_ids:
        return override_tg_ids
    params = json.loads(campaign.segment_params or "{}")
    stored = params.get("target_tg_ids")
    if stored:
        return list(stored)
    return []


async def _run_campaign(campaign_id: int, override_tg_ids: list[int] | None = None):
    rw = _rw_client()
    crm_by_uuid: dict[str, dict] = {}
    try:
        for u in await rw.get_all_users_for_crm():
            if u.get("uuid"):
                crm_by_uuid[u["uuid"]] = u
    except Exception as exc:
        logger.error("CRM campaign %s: bulk RW fetch failed: %s", campaign_id, exc)

    bot_username = ""
    async with async_session() as session:
        campaign = await crm_repo.get_campaign(session, campaign_id)
        if not campaign:
            return

        tg_ids = await _resolve_targets(campaign, override_tg_ids)
        if not tg_ids:
            await crm_repo.update_campaign_status(
                session, campaign, status="failed", completed=True
            )
            await session.commit()
            return

        await crm_repo.update_campaign_status(
            session,
            campaign,
            status="running",
            total_targets=len(tg_ids),
            started=True,
        )
        await session.commit()

        message_text = campaign.message_text
        attach_button = campaign.attach_button
        bonus_days = campaign.bonus_days
        bonus_traffic_gb = campaign.bonus_traffic_gb

    if attach_button:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(_tg_url("getMe"))
            if r.status_code == 200:
                bot_username = r.json().get("result", {}).get("username", "")
        except Exception:
            pass

    reply_markup = None
    if attach_button and bot_username:
        reply_markup = {
            "inline_keyboard": [[
                {"text": "Открыть бота", "url": f"https://t.me/{bot_username}"}
            ]]
        }

    async with async_session() as session:
        users = await get_users_by_tg_ids(session, tg_ids)
        user_by_tg = {u.tg_id: u for u in users if u.tg_id is not None}

    sent = failed = perks_ok = perks_fail = 0

    for i, tg_id in enumerate(tg_ids):
        db_user = user_by_tg.get(tg_id)
        perk_status = "skipped"
        message_status = "failed"
        error_parts: list[str] = []

        if not db_user:
            failed += 1
            async with async_session() as session:
                await crm_repo.add_delivery(
                    session,
                    campaign_id=campaign_id,
                    tg_id=tg_id,
                    vless_uuid=None,
                    perk_status="skipped",
                    message_status="failed",
                    error="user not found",
                )
                await session.commit()
            continue

        crm_user = crm_by_uuid.get(db_user.vless_uuid or "")
        has_perks = bool(bonus_days or bonus_traffic_gb)

        if has_perks and db_user.vless_uuid:
            ok, perk_err = await apply_campaign_perks(
                rw,
                db_user,
                crm_user,
                bonus_days=bonus_days,
                bonus_traffic_gb=bonus_traffic_gb,
            )
            if ok:
                perks_ok += 1
                perk_status = "applied"
            else:
                perks_fail += 1
                perk_status = "failed"
                if perk_err:
                    error_parts.append(perk_err)
        elif has_perks:
            perks_fail += 1
            perk_status = "failed"
            error_parts.append("no vless_uuid for perks")

        ok_msg = await _tg_send(tg_id, message_text, reply_markup)
        if ok_msg:
            sent += 1
            message_status = "sent"
        else:
            failed += 1
            error_parts.append("telegram send failed")

        async with async_session() as session:
            await crm_repo.add_delivery(
                session,
                campaign_id=campaign_id,
                tg_id=tg_id,
                vless_uuid=db_user.vless_uuid,
                perk_status=perk_status,
                message_status=message_status,
                error="; ".join(error_parts) if error_parts else None,
            )
            await session.commit()

        if (i + 1) % 25 == 0:
            await asyncio.sleep(1)

    async with async_session() as session:
        campaign = await crm_repo.get_campaign(session, campaign_id)
        if campaign:
            await crm_repo.update_campaign_status(
                session,
                campaign,
                status="completed",
                messages_sent=sent,
                messages_failed=failed,
                perks_applied=perks_ok,
                perks_failed=perks_fail,
                completed=True,
            )
            await session.commit()

    logger.info(
        "CRM campaign %s done: sent=%d failed=%d perks_ok=%d perks_fail=%d",
        campaign_id,
        sent,
        failed,
        perks_ok,
        perks_fail,
    )


@router.post("/campaigns/{campaign_id}/execute")
async def execute_campaign(
    campaign_id: int,
    body: ExecuteRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(get_current_user),
):
    async with async_session() as session:
        campaign = await crm_repo.get_campaign(session, campaign_id)
        if not campaign:
            raise HTTPException(404, "Campaign not found")
        if campaign.status == "running":
            raise HTTPException(409, "Campaign is already running")
        tg_ids = await _resolve_targets(campaign, body.target_tg_ids)
        total = len(tg_ids)
        await session.commit()

    if not total:
        raise HTTPException(400, "No target users")

    background_tasks.add_task(_run_campaign, campaign_id, body.target_tg_ids)
    return {"status": "started", "total": total}


@router.post("/campaigns/launch", response_model=CampaignSummary)
async def launch_campaign(
    body: CreateCampaignRequest,
    background_tasks: BackgroundTasks,
    user: str = Depends(get_current_user),
):
    """Create a campaign and start execution in one step."""
    if not body.message_text.strip():
        raise HTTPException(400, "message_text is required")
    if not body.target_tg_ids:
        raise HTTPException(400, "target_tg_ids is required")

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
            target_tg_ids=body.target_tg_ids,
        )
        await session.commit()
        summary = _campaign_summary(campaign)

    background_tasks.add_task(_run_campaign, summary.id, None)
    return summary
