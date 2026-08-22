import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
from common_db.api_health import ApiHealthMiddleware, MetricAccumulator, error_fingerprint, redact
from common_db.models import ApiErrorEvent, ApiMetricHour, ApiMetricMinute
from common_db.repo.api_health import apply_retention, compact_and_retain, compact_minutes, flush_redis_metrics, histogram_count_over, merge_histograms, percentile_ms


def test_metric_histogram_and_percentiles() -> None:
    metric = MetricAccumulator()
    for value in (8, 20, 45, 90, 240, 900, 1900, 6000):
        metric.add(value, 10, 20)
    data = metric.dump()
    assert data["request_count"] == 8
    assert data["duration_max_ms"] == 6000
    assert percentile_ms(data["histogram"], .5) == 100
    assert percentile_ms(data["histogram"], .95) == 10000


def test_histogram_merge() -> None:
    assert merge_histograms([{"50": 2}, '{"50":3,"100":1}']) == {"50": 5, "100": 1}


def test_redaction_and_stable_fingerprint() -> None:
    value = redact("Authorization: Bearer abc token=secret password=hunter2 init_data=telegram-secret hash=deadbeef")
    assert "abc" not in value
    assert "hunter2" not in value
    assert "telegram-secret" not in value
    assert "deadbeef" not in value
    assert error_fingerprint("miniapp", "/users/{id}", 500, "ValueError", "user 123") == error_fingerprint(
        "miniapp", "/users/{id}", 500, "ValueError", "user 456"
    )


def test_slow_request_histogram_is_approximate() -> None:
    assert histogram_count_over({"2000": 4, "5000": 3, "inf": 2}, 2_000) == 5


class _SpyCollector:
    def __init__(self) -> None:
        self.metrics = []
        self.errors = []

    def add_metric(self, *args) -> None:
        self.metrics.append(args)

    def add_error(self, payload) -> None:
        self.errors.append(payload)


def _request(path: str, route: str | None, headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    scope = {
        "type": "http", "http_version": "1.1", "method": "GET", "scheme": "https",
        "path": path, "raw_path": path.encode(), "query_string": b"secret=must-not-be-stored",
        "headers": headers or [], "client": ("10.0.0.2", 1234), "server": ("test", 443),
    }
    if route is not None:
        scope["route"] = SimpleNamespace(path=route)
    return Request(scope)


def _middleware() -> tuple[ApiHealthMiddleware, _SpyCollector]:
    middleware = ApiHealthMiddleware(lambda scope, receive, send: None, service="miniapp", redis_url="redis://unused", session_factory=None)
    spy = _SpyCollector()
    middleware.collector = spy
    return middleware, spy


@pytest.mark.parametrize("status", [200, 404, 500])
def test_middleware_status_route_request_id_ip_and_identity(status: int) -> None:
    middleware, spy = _middleware()
    route = None if status == 404 else "/users/{id}"
    request = _request(
        "/users/42", route,
        [(b"x-real-ip", b"203.0.113.7"), (b"user-agent", b"MiniApp/2.4"), (b"x-app-version", b"2.4")],
    )

    async def call_next(req: Request) -> Response:
        req.state.api_user_id = 42
        req.state.api_tg_id = 100042
        if status == 500:
            req.state.api_exception = RuntimeError("token=very-secret")
        return Response("payload", status_code=status)

    response = asyncio.run(middleware.dispatch(request, call_next))
    assert response.headers["x-request-id"]
    assert spy.metrics[0][1] == ("__unmatched__" if status == 404 else "/users/{id}")
    assert spy.metrics[0][2] == status
    if status >= 400:
        event = spy.errors[0]
        assert event["request_id"] == response.headers["x-request-id"]
        assert event["client_ip"] == "203.0.113.7"
        assert event["user_id"] == 42 and event["tg_id"] == 100042
        assert "secret" not in (event["error_message"] or "").lower()
        assert "secret=must-not-be-stored" not in str(event)
    else:
        assert not spy.errors


def test_middleware_records_raised_exception_and_fails_open() -> None:
    middleware, spy = _middleware()
    request = _request("/users/42", "/users/{id}")

    async def call_next(_: Request) -> Response:
        raise ValueError("password=do-not-store")

    with pytest.raises(ValueError):
        asyncio.run(middleware.dispatch(request, call_next))
    assert spy.metrics[0][2] == 500
    assert spy.errors[0]["exception_type"] == "ValueError"
    assert "do-not-store" not in spy.errors[0]["traceback"]


def test_middleware_excludes_health_and_api_health_routes() -> None:
    for path in ("/health", "/bot/miniapp/api/health", "/bot/dashboard/api/api-health/summary"):
        middleware, spy = _middleware()
        request = _request(path, path)

        async def call_next(_: Request) -> Response:
            return Response("ok")

        response = asyncio.run(middleware.dispatch(request, call_next))
        assert response.status_code == 200
        assert not spy.metrics and not spy.errors


class _FakeRedis:
    def __init__(self, values: dict[str, dict[str, str]]) -> None:
        self.values = values

    async def scan_iter(self, match: str):
        for key in self.values:
            yield key

    async def hgetall(self, key: str):
        return self.values[key]


def test_flush_is_idempotent_and_compaction_retention_are_safe() -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        old_minute = now - timedelta(hours=25)
        bucket = old_minute.strftime("%Y-%m-%dT%H:%M:%SZ")
        identity = json.dumps(["miniapp", "GET", "/users/{id}", 200], separators=(",", ":"))
        redis = _FakeRedis({f"api_health:metrics:{bucket}": {identity: json.dumps({
            "request_count": 7, "duration_sum_ms": 700, "duration_max_ms": 250,
            "request_bytes": 70, "response_bytes": 140, "histogram": {"100": 7},
            "dropped_events": 1,
        })}})
        async with Session() as session:
            first_count, first_keys = await flush_redis_metrics(session, redis)
            second_count, second_keys = await flush_redis_metrics(session, redis)
            await session.commit()
            assert first_count == second_count == 1
            assert first_keys == second_keys == [f"api_health:metrics:{bucket}"]
            assert await session.scalar(select(func.count()).select_from(ApiMetricMinute)) == 1
            minute = await session.scalar(select(ApiMetricMinute))
            assert minute and minute.request_count == 7 and minute.dropped_events == 1

            session.add(ApiErrorEvent(
                occurred_at=(now - timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                request_id="old-error", service="miniapp", method="GET", route="/users/{id}",
                status_code=500, duration_ms=10, error_fingerprint="fingerprint",
            ))
            session.add(ApiMetricHour(
                bucket_start=(now - timedelta(days=91)).strftime("%Y-%m-%dT%H:00:00Z"),
                service="miniapp", method="GET", route="/old", status_code=200,
            ))
            await session.commit()
            await compact_minutes(session, now)
            await session.flush()
            before_retention = list((await session.scalars(select(ApiMetricHour))).all())
            assert any(row.route == "/users/{id}" for row in before_retention), [
                (row.bucket_start, row.route, row.request_count) for row in before_retention
            ]
            await apply_retention(session, now)
            await session.commit()
            assert await session.scalar(select(func.count()).select_from(ApiMetricMinute)) == 0
            hour = await session.scalar(select(ApiMetricHour).where(ApiMetricHour.route == "/users/{id}"))
            all_hours = list((await session.scalars(select(ApiMetricHour))).all())
            assert hour and hour.request_count == 7 and json.loads(hour.histogram_json) == {"100": 7}, [
                (row.bucket_start, row.route, row.request_count) for row in all_hours
            ]
            assert await session.scalar(select(func.count()).select_from(ApiErrorEvent)) == 0
            assert await session.scalar(select(func.count()).select_from(ApiMetricHour).where(ApiMetricHour.route == "/old")) == 0

            # A repeated maintenance run must not double the hourly values.
            await compact_and_retain(session, now)
            await session.commit()
            hour = await session.scalar(select(ApiMetricHour).where(ApiMetricHour.route == "/users/{id}"))
            assert hour and hour.request_count == 7
        await engine.dispose()

    asyncio.run(run())
