"""Tests for CRM campaign target resolution."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.models import CrmCampaign, User
from remnawave_client.segmentation import SEGMENT_ALL_USERS


def _make_engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:")


async def _setup(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _run(coro):
    return asyncio.run(coro)


def _campaign(*, segment_type: str, segment_params: dict | None = None) -> CrmCampaign:
    return CrmCampaign(
        id=1,
        name="test",
        segment_type=segment_type,
        segment_params=json.dumps(segment_params or {}),
        message_text="hi",
        created_at=datetime.now().isoformat(timespec="seconds"),
        created_by="tester",
    )


def test_resolve_targets_all_users_from_db() -> None:
    import pytest

    resolve_targets = pytest.importorskip("dashboard.backend.crm_runner").resolve_targets

    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add_all([
                    User(id=1, tg_id=101, username="a", is_banned=False),
                    User(id=2, tg_id=202, username="b", is_banned=False),
                    User(id=3, tg_id=303, username="c", is_banned=True),
                ])
                await session.flush()

                campaign = _campaign(segment_type=SEGMENT_ALL_USERS)
                tg_ids = await resolve_targets(session, campaign)
                assert set(tg_ids) == {101, 202}
        finally:
            await engine.dispose()

    _run(go())


def test_resolve_targets_explicit_tg_ids() -> None:
    import pytest

    resolve_targets = pytest.importorskip("dashboard.backend.crm_runner").resolve_targets

    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                campaign = _campaign(
                    segment_type="expiring_soon",
                    segment_params={"target_tg_ids": [1, 2, 3]},
                )
                tg_ids = await resolve_targets(session, campaign)
                assert tg_ids == [1, 2, 3]

                override = await resolve_targets(session, campaign, [99])
                assert override == [99]
        finally:
            await engine.dispose()

    _run(go())
