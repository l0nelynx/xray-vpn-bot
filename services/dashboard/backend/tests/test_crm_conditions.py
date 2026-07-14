"""Tests for CRM conditions evaluation."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.models import User


def _run(coro):
    return asyncio.run(coro)


def test_segment_id_from_conditions() -> None:
    from dashboard.backend.crm_conditions import segment_id_from_conditions

    conditions = [
        {"type": "user_type", "value": "free"},
        {"type": "segment", "segment_id": "limited", "params": {}},
    ]
    assert segment_id_from_conditions(conditions) == "limited"


def test_evaluate_conditions_allowlist_intersect() -> None:
    from dashboard.backend.crm_conditions import evaluate_conditions

    async def go() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            Session = async_sessionmaker(engine, expire_on_commit=False)
            rw = MagicMock()

            async with Session() as session:
                session.add_all([
                    User(id=1, tg_id=101, username="a", is_banned=False),
                    User(id=2, tg_id=202, username="b", is_banned=False),
                ])
                await session.flush()

                from dashboard.backend import crm_service

                original = crm_service.scan_segment
                crm_service.scan_segment = AsyncMock(
                    return_value=(
                        [
                            {"tg_id": 101, "username": "a", "vless_uuid": None, "meta": {}},
                            {"tg_id": 202, "username": "b", "vless_uuid": None, "meta": {}},
                            {"tg_id": 303, "username": "c", "vless_uuid": None, "meta": {}},
                        ],
                        3,
                        None,
                    )
                )
                try:
                    conditions = [
                        {"type": "segment", "segment_id": "limited", "params": {}},
                        {"type": "tg_allowlist", "tg_ids": [101, 303]},
                    ]
                    tg_ids, users, total, _ = await evaluate_conditions(
                        session, rw, conditions, preview_limit=None
                    )
                    assert tg_ids == [101, 303]
                    assert len(users) == 2
                    assert total == 2
                finally:
                    crm_service.scan_segment = original
        finally:
            await engine.dispose()

    _run(go())


def test_evaluate_conditions_user_type_in_params() -> None:
    from dashboard.backend.crm_conditions import _segment_from_conditions

    segment_id, params, user_type = _segment_from_conditions([
        {"type": "segment", "segment_id": "expiring_soon", "params": {"days_threshold": 5}},
        {"type": "user_type", "value": "free"},
    ])
    assert segment_id == "expiring_soon"
    assert params["user_type"] == "free"
    assert user_type == "free"
