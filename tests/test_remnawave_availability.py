"""Incident transitions, opt-in, durable retries and SDK failure observation."""
import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
from common_db.models import RemnawaveAvailability, RemnawaveNotice, RemnawaveRecoverySubscription, User
from miniapp.backend import remnawave_availability as monitor
from miniapp.backend.tg_auth import TgUser, get_tg_user
from remnawave_client import availability as observer
from remnawave_client.client import RemnawaveClient


@pytest.fixture
def setup_monitor(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'availability.db').as_posix()}")
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def seed():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with factory() as session:
            session.add_all([RemnawaveAvailability(id=1), User(id=1, tg_id=123), User(id=2, tg_id=456, is_banned=True)])
            await session.commit()

    asyncio.run(seed())
    monkeypatch.setattr(monitor, "async_session", factory)
    monkeypatch.setattr(monitor, "get_remnawave_url", lambda: "https://panel.example")
    monkeypatch.setattr(monitor, "get_remnawave_token", lambda: "panel-test-token")
    monkeypatch.setattr(monitor, "get_bot_token", lambda: "user-test-token")
    monkeypatch.setattr(monitor, "get_admin_bot_token", lambda: "admin-test-token")
    monkeypatch.setattr(monitor, "get_admin_id", lambda: -100123)
    yield factory
    observer.set_failure_observer(None)
    asyncio.run(engine.dispose())


async def due(factory):
    async with factory() as session:
        state = await session.get(RemnawaveAvailability, 1)
        state.next_probe_at = 0
        await session.commit()


def test_outage_deduplicated_recovery_notifies_once_and_new_outage(setup_monitor, monkeypatch):
    factory = setup_monitor

    async def run():
        await monitor.record_failure()
        await monitor.record_failure()
        tg = TgUser(123, None, "en", 0)
        assert (await monitor.subscribe(monitor.RecoveryRequest(language="en"), tg))["subscribed"]
        await monitor.subscribe(monitor.RecoveryRequest(language="en"), tg)
        async with factory() as session:
            assert await session.scalar(select(func.count()).select_from(RemnawaveRecoverySubscription)) == 1
            assert await session.scalar(select(func.count()).select_from(RemnawaveNotice)) == 1
        monkeypatch.setattr(monitor, "probe", AsyncMock())
        await due(factory)
        await monitor.check_availability()
        await monitor.check_availability()
        async with factory() as session:
            notices = (await session.scalars(select(RemnawaveNotice))).all()
            assert {n.key for n in notices} == {"outage:1", "recovery:1", "user:1:123"}
            assert next(n for n in notices if n.tg_id == 123).text.startswith("The maintenance")
            assert await session.scalar(select(func.count()).select_from(RemnawaveRecoverySubscription)) == 0
        assert await monitor.subscribe(monitor.RecoveryRequest(), tg) == {"unavailable": False, "subscribed": False}
        await monitor.record_failure()
        assert await monitor.availability(tg) == {"unavailable": True, "subscribed": False}
        async with factory() as session:
            assert (await session.get(RemnawaveAvailability, 1)).incident == 2

    asyncio.run(run())


def test_background_probe_without_users_and_interval(setup_monitor, monkeypatch):
    async def run():
        probe = AsyncMock(side_effect=httpx.ConnectError("offline"))
        monkeypatch.setattr(monitor, "probe", probe)
        await monitor.check_availability()
        await monitor.check_availability()
        assert probe.await_count == 1
        async with setup_monitor() as session:
            assert (await session.get(RemnawaveAvailability, 1)).unavailable
        await due(setup_monitor)
        await monitor.check_availability()
        async with setup_monitor() as session:
            assert await session.scalar(select(func.count()).select_from(RemnawaveNotice)) == 1

    asyncio.run(run())


def test_notice_retries_and_uses_ticket_chat_and_user_bot(setup_monitor, monkeypatch):
    requests = []
    fail = True

    def handler(request):
        import json
        requests.append((request.url.path, json.loads(request.content)))
        return httpx.Response(500 if fail else 200, json={"ok": not fail})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(monitor.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))

    async def run():
        nonlocal fail
        await monitor.record_failure()
        await monitor.deliver_notices()
        await monitor.deliver_notices()
        assert len(requests) == 1
        async with setup_monitor() as session:
            notice = await session.get(RemnawaveNotice, "outage:1")
            assert notice is not None
            notice.next_attempt_at = 0
            session.add(RemnawaveNotice(key="user:1:123", admin=False, tg_id=123, text="restored"))
            await session.commit()
        fail = False
        await monitor.deliver_notices()
        assert requests[1][0] == "/botadmin-test-token/sendMessage"
        assert requests[1][1]["chat_id"] == -100123
        assert requests[2][0] == "/botuser-test-token/sendMessage"
        assert requests[2][1]["chat_id"] == 123
        async with setup_monitor() as session:
            assert await session.scalar(select(func.count()).select_from(RemnawaveNotice)) == 0

    asyncio.run(run())


def test_routes_auth_and_opt_in(setup_monitor):
    app = FastAPI()
    app.include_router(monitor.router)
    client = TestClient(app)
    base = "/api/remnawave"
    assert client.get(base + "/availability").status_code in (401, 422)
    app.dependency_overrides[get_tg_user] = lambda: TgUser(123, None, "ru", 0)
    asyncio.run(monitor.record_failure())
    assert client.post(base + "/recovery-notification", json={"language": "ru"}).json()["subscribed"]
    assert client.get(base + "/availability").json() == {"unavailable": True, "subscribed": True}
    app.dependency_overrides[get_tg_user] = lambda: TgUser(456, None, "ru", 0)
    assert client.post(base + "/recovery-notification", json={}).status_code == 403


@pytest.mark.parametrize("status", [400, 404, 409, 422, 429])
def test_business_errors_not_outages(status):
    async def run():
        callback = AsyncMock()
        observer.set_failure_observer(callback)
        request = httpx.Request("GET", "https://panel.example/users/1")
        await observer.report_failure(httpx.HTTPStatusError("error", request=request, response=httpx.Response(status)))
        callback.assert_not_awaited()
        observer.set_failure_observer(None)

    asyncio.run(run())


@pytest.mark.parametrize("status", [0, 401, 403, 408, 500, 502, 503, 504])
def test_sdk_status_codes_record_outages(status):
    async def run():
        from remnawave.exceptions import ApiError, ApiErrorResponse
        callback = AsyncMock()
        observer.set_failure_observer(callback)
        await observer.report_failure(ApiError(status, ApiErrorResponse(message="failure")))
        callback.assert_awaited_once()
        observer.set_failure_observer(None)

    asyncio.run(run())


def test_swallowed_sdk_error_still_records_incident(setup_monitor):
    async def run():
        from types import SimpleNamespace
        client = RemnawaveClient("https://panel.example", "test")
        client._sdk = SimpleNamespace(users=SimpleNamespace(get_user_by_id=AsyncMock(side_effect=httpx.ReadTimeout("offline"))))
        observer.set_failure_observer(monitor.record_failure)
        assert await client.get_user_by_id(1) is None
        async with setup_monitor() as session:
            assert (await session.get(RemnawaveAvailability, 1)).unavailable

    asyncio.run(run())


def test_monitor_shutdown_cancels_delivery_and_clears_observers(setup_monitor, monkeypatch):
    async def run():
        monkeypatch.setattr(monitor, "check_availability", AsyncMock())
        monkeypatch.setattr(monitor, "deliver_notices", AsyncMock())
        task = asyncio.create_task(monitor.monitor_loop())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert monitor._wake is None
        assert monitor._notice_wake is None
        monitor.check_availability.assert_awaited()
        monitor.deliver_notices.assert_awaited()

    asyncio.run(run())


def test_remnawave_exception_handler_returns_safe_maintenance_code(monkeypatch):
    from pathlib import Path
    monkeypatch.setenv("CONFIG_PATH", str(Path(__file__).resolve().parents[1] / "config-example.yml"))
    from miniapp.backend import main
    from remnawave_client.client import RemnawaveOperationError
    app = FastAPI()
    app.add_exception_handler(RemnawaveOperationError, main._remnawave_error)

    @app.get("/me")
    async def unavailable():
        raise RemnawaveOperationError("get_user", httpx.ConnectError("sensitive upstream detail"))

    with TestClient(app) as client:
        response = client.get("/me")
        assert response.status_code == 503
        assert response.json() == {"detail": "remnawave_unavailable"}
