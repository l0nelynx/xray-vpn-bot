"""Tests for crm_events repository."""
from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.repo import crm_events as events_repo


def _run(coro):
    return asyncio.run(coro)


def test_create_and_list_due_events() -> None:
    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                event = await events_repo.create_event(
                    session,
                    name="test",
                    segment_type="limited",
                    segment_params={},
                    run_at_time="01:00",
                    frequency="daily",
                    weekday=None,
                    message_text="hi",
                    attach_button=False,
                    bonus_days=None,
                    bonus_traffic_gb=None,
                    repeat_policy="cooldown",
                    repeat_cooldown_days=7,
                    created_by="tester",
                )
                assert event.id is not None
                assert event.next_run_at is not None

                # Force due
                event.next_run_at = "2000-01-01T00:00:00"
                await session.flush()

                due = await events_repo.list_due_events(
                    session, now_iso="2026-01-01T00:00:00"
                )
                assert len(due) == 1
                assert due[0].id == event.id

                await events_repo.record_event_delivery(
                    session, event_id=event.id, tg_id=12345
                )
                sent = await events_repo.get_sent_tg_ids_for_event(session, event.id)
                assert 12345 in sent

                await session.commit()
        finally:
            await engine.dispose()

    _run(go())
