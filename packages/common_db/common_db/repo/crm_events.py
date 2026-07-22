"""CRM scheduled events CRUD and repeat-policy helpers."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CrmEvent, CrmEventDelivery


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def _parse_time(run_at_time: str) -> tuple[int, int]:
    hour, minute = run_at_time.split(":", 1)
    return int(hour), int(minute)


def compute_next_run_at(
    *,
    run_at_time: str,
    frequency: str,
    weekday: int | None,
    from_dt: datetime | None = None,
) -> str:
    """Next run timestamp (UTC naive ISO) after ``from_dt``."""
    base = from_dt or datetime.now(timezone.utc).replace(tzinfo=None)
    hour, minute = _parse_time(run_at_time)
    candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= base:
        candidate += timedelta(days=1)

    if frequency == "weekly":
        target = weekday if weekday is not None else 0
        while candidate.weekday() != target:
            candidate += timedelta(days=1)

    return candidate.isoformat(timespec="seconds")


async def create_event(
    session: AsyncSession,
    *,
    name: str,
    conditions: list[dict],
    actions: list[dict],
    segment_type: str,
    segment_params: dict,
    message_text: str,
    attach_button: bool,
    bonus_days: int | None,
    bonus_traffic_gb: int | None,
    run_at_time: str,
    frequency: str,
    weekday: int | None,
    repeat_policy: str,
    repeat_cooldown_days: int,
    created_by: str,
    enabled: bool = True,
) -> CrmEvent:
    now = _now_iso()
    event = CrmEvent(
        name=name,
        enabled=enabled,
        segment_type=segment_type,
        segment_params=json.dumps(segment_params),
        conditions_json=json.dumps(conditions, ensure_ascii=False),
        actions_json=json.dumps(actions, ensure_ascii=False),
        run_at_time=run_at_time,
        frequency=frequency,
        weekday=weekday,
        message_text=message_text,
        attach_button=attach_button,
        bonus_days=bonus_days,
        bonus_traffic_gb=bonus_traffic_gb,
        repeat_policy=repeat_policy,
        repeat_cooldown_days=repeat_cooldown_days,
        created_at=now,
        updated_at=now,
        created_by=created_by,
        next_run_at=compute_next_run_at(
            run_at_time=run_at_time,
            frequency=frequency,
            weekday=weekday,
        ),
    )
    session.add(event)
    await session.flush()
    return event


async def get_event(session: AsyncSession, event_id: int) -> CrmEvent | None:
    return await session.get(CrmEvent, event_id)


async def list_events(session: AsyncSession) -> list[CrmEvent]:
    result = await session.scalars(select(CrmEvent).order_by(desc(CrmEvent.id)))
    return list(result)


async def list_due_events(session: AsyncSession, *, now_iso: str | None = None) -> list[CrmEvent]:
    now = now_iso or _now_iso()
    result = await session.scalars(
        select(CrmEvent).where(
            CrmEvent.enabled == True,  # noqa: E712
            CrmEvent.next_run_at.is_not(None),
            CrmEvent.next_run_at <= now,
        )
    )
    return list(result)


async def update_event(
    session: AsyncSession,
    event: CrmEvent,
    **fields,
) -> CrmEvent:
    for key, value in fields.items():
        if value is not None and hasattr(event, key):
            setattr(event, key, value)
    event.updated_at = _now_iso()
    await session.flush()
    return event


async def delete_event(session: AsyncSession, event: CrmEvent) -> None:
    await session.delete(event)
    await session.flush()


async def mark_event_run(
    session: AsyncSession,
    event: CrmEvent,
) -> None:
    now = _now_iso()
    event.last_run_at = now
    event.next_run_at = compute_next_run_at(
        run_at_time=event.run_at_time,
        frequency=event.frequency,
        weekday=event.weekday,
        from_dt=datetime.fromisoformat(now),
    )
    event.updated_at = now
    await session.flush()


async def record_event_delivery(
    session: AsyncSession,
    *,
    event_id: int,
    tg_id: int,
) -> CrmEventDelivery:
    row = CrmEventDelivery(
        event_id=event_id,
        tg_id=tg_id,
        sent_at=_now_iso(),
    )
    session.add(row)
    await session.flush()
    return row


async def get_sent_tg_ids_for_event(
    session: AsyncSession,
    event_id: int,
) -> set[int]:
    result = await session.scalars(
        select(CrmEventDelivery.tg_id).where(CrmEventDelivery.event_id == event_id)
    )
    return {int(tg_id) for tg_id in result}


async def get_recent_sent_tg_ids(
    session: AsyncSession,
    event_id: int,
    *,
    since_iso: str,
) -> set[int]:
    result = await session.scalars(
        select(CrmEventDelivery.tg_id).where(
            CrmEventDelivery.event_id == event_id,
            CrmEventDelivery.sent_at >= since_iso,
        )
    )
    return {int(tg_id) for tg_id in result}


def filter_tg_ids_by_repeat_policy(
    tg_ids: list[int],
    *,
    repeat_policy: str,
    repeat_cooldown_days: int,
    ever_sent: set[int],
    recent_sent: set[int],
) -> list[int]:
    if repeat_policy == "always":
        return tg_ids
    if repeat_policy == "once":
        return [tg_id for tg_id in tg_ids if tg_id not in ever_sent]
    # cooldown
    blocked = recent_sent
    return [tg_id for tg_id in tg_ids if tg_id not in blocked]
