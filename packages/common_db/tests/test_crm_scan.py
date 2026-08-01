"""CRM scan integration test with mocked Remnawave client."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.models import User


def _make_engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:")


async def _setup(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _run(coro):
    return asyncio.run(coro)


class FakeRwClient:
    async def get_all_users_for_crm(self):
        expire = int((datetime.now(timezone.utc) + timedelta(days=2)).timestamp())
        return [
            {
                "rw_id": 11,
                "status": "active",
                "expire_ts": expire,
                "days_left": 2,
                "used_traffic_bytes": 0,
                "traffic_limit_bytes": 0,
                "traffic_ratio": None,
                "first_connected_at": "2026-01-01",
                "hwid_device_limit": None,
                "device_count": None,
                "telegram_id": 1001,
                "username": "exp_user",
            },
            {
                "rw_id": 22,
                "status": "active",
                "expire_ts": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
                "days_left": 30,
                "used_traffic_bytes": 0,
                "traffic_limit_bytes": 0,
                "traffic_ratio": None,
                "first_connected_at": "2026-01-01",
                "hwid_device_limit": None,
                "device_count": None,
                "telegram_id": 1002,
                "username": "ok_user",
            },
        ]

    async def get_user_hwid_devices_by_id(self, rw_id: int):
        return None


def test_scan_expiring_soon_segment() -> None:
    import pytest

    crm_service = pytest.importorskip("dashboard.backend.crm_service")
    scan_segment = crm_service.scan_segment
    from remnawave_client.segmentation import SEGMENT_EXPIRING_SOON

    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add(
                    User(
                        id=1,
                        tg_id=1001,
                        username="exp_user",
                        rw_id=11,
                        vless_uuid="uuid-expiring",
                        api_provider="remnawave",
                    )
                )
                session.add(
                    User(
                        id=2,
                        tg_id=1002,
                        username="ok_user",
                        rw_id=22,
                        vless_uuid="uuid-ok",
                        api_provider="remnawave",
                    )
                )
                await session.flush()

                users, total, warning = await scan_segment(
                    session,
                    FakeRwClient(),
                    SEGMENT_EXPIRING_SOON,
                    days_threshold=3,
                )
                assert warning is None
                assert total == 1
                assert users[0]["tg_id"] == 1001
        finally:
            await engine.dispose()

    _run(go())


def test_scan_all_users_segment() -> None:
    import pytest

    crm_service = pytest.importorskip("dashboard.backend.crm_service")
    scan_segment = crm_service.scan_segment
    from remnawave_client.segmentation import SEGMENT_ALL_USERS

    async def go() -> None:
        engine = _make_engine()
        try:
            await _setup(engine)
            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                session.add_all([
                    User(id=1, tg_id=1001, username="u1", is_banned=False),
                    User(id=2, tg_id=1002, username="u2", is_banned=False),
                    User(id=3, tg_id=None, username="no_tg", is_banned=False),
                    User(id=4, tg_id=1004, username="banned", is_banned=True),
                ])
                await session.flush()

                users, total, warning = await scan_segment(
                    session,
                    FakeRwClient(),
                    SEGMENT_ALL_USERS,
                )
                assert warning is None
                assert total == 2
                assert {u["tg_id"] for u in users} == {1001, 1002}
        finally:
            await engine.dispose()

    _run(go())
