from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.api_health import utc_iso
from common_db.models import ApiMetricMinute, ApiServiceStatus
from dashboard.backend import api_health_worker as worker


def test_alert_rules_threshold_sample_health_and_disabled(monkeypatch) -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        now = utc_iso(datetime.now(timezone.utc))
        async with Session() as session:
            session.add_all([
                ApiMetricMinute(
                    bucket_start=now, service="miniapp", method="GET", route="/boom", status_code=500,
                    request_count=21, duration_sum_ms=105_000, duration_max_ms=5_000,
                    histogram_json=json.dumps({"5000": 21}),
                ),
                ApiServiceStatus(
                    service="miniapp", is_healthy=False, checked_at=now, consecutive_failures=3,
                ),
            ])
            await session.commit()

            transitions: list[tuple[str, bool]] = []

            async def capture(_session, key, triggered, *_args):
                transitions.append((key, triggered))

            monkeypatch.setattr(worker, "_transition_alert", capture)
            monkeypatch.setattr(worker, "get_runtime_config_dict", AsyncMock(return_value={"api_health_alerts": {
                "enabled": True, "server_error_threshold": 20, "latency_p95_ms": 2_000,
                "latency_min_requests": 20, "health_failures": 3, "cooldown_minutes": 30,
            }}))
            await worker._evaluate_alerts(session)
            assert ("miniapp:5xx", True) in transitions
            assert ("miniapp:latency", True) in transitions
            assert ("miniapp:availability", True) in transitions
            assert ("bot:latency", False) in transitions  # minimum sample protects empty/tiny windows

            transitions.clear()
            monkeypatch.setattr(worker, "get_runtime_config_dict", AsyncMock(return_value={"api_health_alerts": {"enabled": False}}))
            await worker._evaluate_alerts(session)
            assert transitions == []
        await engine.dispose()

    asyncio.run(run())


def test_alert_cooldown_and_recovery_message(monkeypatch) -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        sent: list[str] = []

        async def send(text: str) -> None:
            sent.append(text)

        monkeypatch.setattr(worker, "_send_telegram", send)
        async with Session() as session:
            await worker._transition_alert(session, "miniapp:5xx", True, 21, "alert", "recovery", 30)
            await session.flush()
            await worker._transition_alert(session, "miniapp:5xx", True, 22, "duplicate", "recovery", 30)
            await worker._transition_alert(session, "miniapp:5xx", False, 0, "alert", "recovery", 30)
            assert sent == ["alert", "recovery"]
        await engine.dispose()

    asyncio.run(run())
