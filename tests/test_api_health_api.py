from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
import common_db.models  # noqa: F401
from common_db.api_health import utc_iso
from common_db.models import ApiErrorEvent, ApiMetricMinute, ApiServiceStatus
from dashboard.backend.routers import api_health


def test_api_health_auth_filters_empty_ranges_and_settings(tmp_path, monkeypatch) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'health.db').as_posix()}")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            now = utc_iso(datetime.now(timezone.utc))
            session.add_all([
                ApiMetricMinute(
                    bucket_start=now, service="miniapp", method="GET", route="/users/{id}", status_code=500,
                    request_count=2, duration_sum_ms=5_000, duration_max_ms=3_000,
                    histogram_json='{"2000":1,"5000":1}',
                ),
                ApiServiceStatus(service="miniapp", is_healthy=True, checked_at=now, consecutive_failures=0),
                ApiErrorEvent(
                    occurred_at=now, request_id="request-searchable", service="miniapp", method="GET",
                    route="/users/{id}", status_code=500, duration_ms=3_000, user_id=42, tg_id=100042,
                    client_ip="203.0.113.9", exception_type="RuntimeError", error_message="failure",
                    error_fingerprint="same-fingerprint",
                ),
            ])
            await session.commit()

    asyncio.run(setup())
    monkeypatch.setattr(api_health, "async_session", Session)

    app = FastAPI()
    app.include_router(api_health.router)
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/api-health/summary").status_code in (401, 403)

    app.dependency_overrides[api_health.get_current_user] = lambda: "admin"
    with TestClient(app) as client:
        summary = client.get("/api/api-health/summary?range=1h")
        assert summary.status_code == 200
        assert summary.json()["server_errors"] == 2
        assert summary.json()["slow_requests"] == 1
        assert client.get("/api/api-health/summary?range=invalid").status_code == 400

        found = client.get("/api/api-health/errors", params={"q": "203.0.113.9", "range": "1h"})
        assert found.status_code == 200
        assert found.json()["total"] == 1
        assert found.json()["groups"][0]["affected_users"] == 1
        assert client.get("/api/api-health/errors", params={"q": "missing", "range": "1h"}).json()["items"] == []
        assert client.get("/api/api-health/errors/1").json()["traceback"] is None

        defaults = client.get("/api/api-health/settings")
        assert defaults.status_code == 200 and defaults.json()["enabled"] is True
        updated = {**defaults.json(), "enabled": False, "server_error_threshold": 25}
        saved = client.put("/api/api-health/settings", json=updated)
        assert saved.status_code == 200 and saved.json()["server_error_threshold"] == 25

    asyncio.run(engine.dispose())
