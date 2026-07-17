"""Push campaign CRUD (Dashboard FCM broadcasts)."""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PushCampaign, PushCampaignDelivery


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


async def create_campaign(
    session: AsyncSession,
    *,
    title: str,
    body: str,
    data: dict | None,
    audience: str,
    audience_params: dict | None,
    created_by: str,
) -> PushCampaign:
    campaign = PushCampaign(
        title=title.strip(),
        body=body.strip(),
        data_json=json.dumps(data or {}, ensure_ascii=False),
        audience=audience,
        audience_params=json.dumps(audience_params or {}, ensure_ascii=False),
        status="draft",
        created_at=_now_iso(),
        created_by=created_by,
    )
    session.add(campaign)
    await session.flush()
    return campaign


async def get_campaign(
    session: AsyncSession, campaign_id: int
) -> PushCampaign | None:
    return await session.get(PushCampaign, campaign_id)


async def list_campaigns(
    session: AsyncSession, *, limit: int = 50, offset: int = 0
) -> list[PushCampaign]:
    result = await session.scalars(
        select(PushCampaign)
        .order_by(desc(PushCampaign.id))
        .offset(offset)
        .limit(limit)
    )
    return list(result)


async def queue_campaign(
    session: AsyncSession, campaign: PushCampaign, *, total_targets: int
) -> None:
    campaign.status = "queued"
    campaign.total_targets = total_targets
    await session.flush()


async def update_campaign_status(
    session: AsyncSession,
    campaign: PushCampaign,
    *,
    status: str,
    sent: int | None = None,
    failed: int | None = None,
    total_targets: int | None = None,
    started: bool = False,
    completed: bool = False,
) -> None:
    campaign.status = status
    if sent is not None:
        campaign.sent = sent
    if failed is not None:
        campaign.failed = failed
    if total_targets is not None:
        campaign.total_targets = total_targets
    if started:
        campaign.started_at = _now_iso()
    if completed:
        campaign.completed_at = _now_iso()
    await session.flush()


async def update_campaign_progress(
    session: AsyncSession,
    campaign: PushCampaign,
    *,
    sent: int,
    failed: int,
) -> None:
    campaign.sent = sent
    campaign.failed = failed
    await session.flush()


async def add_delivery(
    session: AsyncSession,
    *,
    campaign_id: int,
    user_id: int,
    token: str,
    status: str,
    error: str | None = None,
) -> PushCampaignDelivery:
    row = PushCampaignDelivery(
        campaign_id=campaign_id,
        user_id=user_id,
        token=token,
        status=status,
        error=error,
        sent_at=_now_iso() if status == "sent" else None,
    )
    session.add(row)
    await session.flush()
    return row


def get_data(campaign: PushCampaign) -> dict:
    try:
        raw = json.loads(campaign.data_json or "{}")
        return raw if isinstance(raw, dict) else {}
    except json.JSONDecodeError:
        return {}


def get_audience_params(campaign: PushCampaign) -> dict:
    try:
        raw = json.loads(campaign.audience_params or "{}")
        return raw if isinstance(raw, dict) else {}
    except json.JSONDecodeError:
        return {}
