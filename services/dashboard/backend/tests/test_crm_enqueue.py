"""Tests for CRM campaign enqueue (ARQ)."""
from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.models import CrmCampaign
from common_db.repo import crm as crm_repo


def _make_engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:")


async def _setup(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _run(coro):
    return asyncio.run(coro)


def test_enqueue_campaign_calls_arq() -> None:
    enqueue_campaign = pytest.importorskip("dashboard.backend.tasks.crm").enqueue_campaign
    from dashboard.backend.tasks.crm import JOB_NAME

    async def go() -> None:
        pool = AsyncMock()
        await enqueue_campaign(pool, 42)
        pool.enqueue_job.assert_awaited_once_with(JOB_NAME, 42)

    _run(go())


def test_enqueue_campaign_raises_without_pool() -> None:
    enqueue_campaign = pytest.importorskip("dashboard.backend.tasks.crm").enqueue_campaign

    async def go() -> None:
        with pytest.raises(RuntimeError, match="Redis queue is unavailable"):
            await enqueue_campaign(None, 1)

    _run(go())


def test_queue_campaign_sets_status_queued() -> None:
    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                campaign = CrmCampaign(
                    name="launch",
                    segment_type="all_users",
                    message_text="hello",
                    status="draft",
                    created_at=datetime.now().isoformat(timespec="seconds"),
                    created_by="admin",
                )
                session.add(campaign)
                await session.flush()

                await crm_repo.queue_campaign(session, campaign)
                assert campaign.status == "queued"
        finally:
            await engine.dispose()

    _run(go())
