"""CRM campaign CRUD."""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CrmCampaign, CrmCampaignDelivery


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


async def create_campaign(
    session: AsyncSession,
    *,
    name: str,
    conditions: list[dict],
    actions: list[dict],
    segment_type: str | None,
    segment_params: dict,
    message_text: str,
    attach_button: bool,
    bonus_days: int | None,
    bonus_traffic_gb: int | None,
    created_by: str,
    target_tg_ids: list[int] | None = None,
    event_id: int | None = None,
) -> CrmCampaign:
    params = dict(segment_params)
    if target_tg_ids:
        params["target_tg_ids"] = target_tg_ids

    campaign = CrmCampaign(
        name=name,
        segment_type=segment_type,
        segment_params=json.dumps(params),
        conditions_json=json.dumps(conditions, ensure_ascii=False),
        actions_json=json.dumps(actions, ensure_ascii=False),
        message_text=message_text,
        attach_button=attach_button,
        bonus_days=bonus_days,
        bonus_traffic_gb=bonus_traffic_gb,
        status="draft",
        total_targets=len(target_tg_ids) if target_tg_ids else 0,
        event_id=event_id,
        created_at=_now_iso(),
        created_by=created_by,
    )
    session.add(campaign)
    await session.flush()
    return campaign


async def get_campaign(session: AsyncSession, campaign_id: int) -> CrmCampaign | None:
    return await session.get(CrmCampaign, campaign_id)


async def list_campaigns(
    session: AsyncSession, *, limit: int = 50
) -> list[CrmCampaign]:
    result = await session.scalars(
        select(CrmCampaign).order_by(desc(CrmCampaign.id)).limit(limit)
    )
    return list(result)


async def update_campaign_status(
    session: AsyncSession,
    campaign: CrmCampaign,
    *,
    status: str,
    messages_sent: int | None = None,
    messages_failed: int | None = None,
    perks_applied: int | None = None,
    perks_failed: int | None = None,
    total_targets: int | None = None,
    started: bool = False,
    completed: bool = False,
) -> None:
    campaign.status = status
    if messages_sent is not None:
        campaign.messages_sent = messages_sent
    if messages_failed is not None:
        campaign.messages_failed = messages_failed
    if perks_applied is not None:
        campaign.perks_applied = perks_applied
    if perks_failed is not None:
        campaign.perks_failed = perks_failed
    if total_targets is not None:
        campaign.total_targets = total_targets
    if started:
        campaign.started_at = _now_iso()
    if completed:
        campaign.completed_at = _now_iso()
    await session.flush()


async def queue_campaign(session: AsyncSession, campaign: CrmCampaign) -> None:
    campaign.status = "queued"
    await session.flush()


async def update_campaign_progress(
    session: AsyncSession,
    campaign: CrmCampaign,
    *,
    messages_sent: int,
    messages_failed: int,
    perks_applied: int,
    perks_failed: int,
) -> None:
    campaign.messages_sent = messages_sent
    campaign.messages_failed = messages_failed
    campaign.perks_applied = perks_applied
    campaign.perks_failed = perks_failed
    await session.flush()


async def add_delivery(
    session: AsyncSession,
    *,
    campaign_id: int,
    tg_id: int,
    vless_uuid: str | None,
    perk_status: str,
    message_status: str,
    error: str | None = None,
) -> CrmCampaignDelivery:
    row = CrmCampaignDelivery(
        campaign_id=campaign_id,
        tg_id=tg_id,
        vless_uuid=vless_uuid,
        perk_status=perk_status,
        message_status=message_status,
        error=error,
    )
    session.add(row)
    await session.flush()
    return row
