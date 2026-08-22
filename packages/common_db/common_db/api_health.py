"""Low-overhead application HTTP telemetry for the FastAPI services.

Successful requests only touch an in-process minute accumulator.  A small
snapshot is periodically copied to Redis; error details are persisted in
bounded batches.  Observability always fails open and can never replace the
application response with a telemetry failure.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
import traceback as traceback_module
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .models import ApiErrorEvent

logger = logging.getLogger(__name__)

LATENCY_BUCKETS_MS = (10, 25, 50, 100, 250, 500, 1000, 2000, 5000, 10000, 30000)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_SECRET_RE = re.compile(
    r"(?i)(authorization|token|password|secret|api[_-]?key|cookie|init[_-]?data|hash)"
    r"(\s*[:=]\s*)[^\s,;]+"
)


def utc_iso(dt: datetime | None = None) -> str:
    return (dt or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def minute_bucket(dt: datetime | None = None) -> str:
    value = (dt or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def redact(value: object, *, limit: int = 16_384) -> str:
    text = _BEARER_RE.sub("Bearer [REDACTED]", str(value))
    text = _SECRET_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", text)
    return text[:limit]


def real_client_ip(request: Request) -> str | None:
    value = request.headers.get("x-real-ip")
    if value and value.strip():
        return value.strip()[:64]
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        hops = [part.strip() for part in forwarded.split(",") if part.strip()]
        if hops:
            return hops[-1][:64]
    return request.client.host[:64] if request.client else None


def route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return str(path)[:255] if path else "__unmatched__"


def client_channel(request: Request, service: str) -> str:
    path = request.url.path
    if service == "bot":
        return "webhook"
    if path.startswith("/bot/dashboard"):
        return "dashboard"
    if "/android/" in path:
        return "android"
    if "/web/" in path:
        return "web"
    return "telegram" if service == "miniapp" else service


def error_fingerprint(service: str, route: str, status: int, exc_type: str | None, message: str | None) -> str:
    normalized = re.sub(r"\b\d+\b", "#", (message or "")[:500])
    raw = "|".join((service, route, str(status), exc_type or "http", normalized))
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:32]


@dataclass
class MetricAccumulator:
    count: int = 0
    duration_sum_ms: float = 0.0
    duration_max_ms: float = 0.0
    request_bytes: int = 0
    response_bytes: int = 0
    histogram: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    dropped_events: int = 0

    def add(self, duration_ms: float, request_bytes: int, response_bytes: int) -> None:
        self.count += 1
        self.duration_sum_ms += duration_ms
        self.duration_max_ms = max(self.duration_max_ms, duration_ms)
        self.request_bytes += request_bytes
        self.response_bytes += response_bytes
        bound = next((b for b in LATENCY_BUCKETS_MS if duration_ms <= b), "inf")
        self.histogram[str(bound)] += 1

    def dump(self) -> dict[str, Any]:
        return {
            "request_count": self.count,
            "duration_sum_ms": round(self.duration_sum_ms, 3),
            "duration_max_ms": round(self.duration_max_ms, 3),
            "request_bytes": self.request_bytes,
            "response_bytes": self.response_bytes,
            "histogram": dict(self.histogram),
            "dropped_events": self.dropped_events,
        }


class ApiHealthCollector:
    def __init__(
        self, service: str, redis_url: str, session_factory: async_sessionmaker,
        *, queue_size: int = 10_000, metric_limit: int = 20_000,
    ):
        self.service = service
        self.redis_url = redis_url
        self.session_factory = session_factory
        self.metrics: dict[tuple[str, str, str, str, int], MetricAccumulator] = {}
        self.metric_limit = metric_limit
        self.error_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=queue_size)
        self.sample_counts: dict[tuple[str, str, int, str], int] = {}
        self.last_flush = 0.0
        self.redis: Any = None
        self.flush_task: asyncio.Task | None = None
        self.writer_task: asyncio.Task | None = None
        self.dropped_events = 0
        self.last_metric_key: tuple[str, str, str, str, int] | None = None

    def _ensure_tasks(self) -> None:
        if self.writer_task is None or self.writer_task.done():
            self.writer_task = asyncio.create_task(self._error_writer())

    def add_metric(self, method: str, route: str, status: int, duration_ms: float, request_bytes: int, response_bytes: int) -> None:
        bucket = minute_bucket()
        key = (bucket, self.service, method, route, status)
        if key not in self.metrics and len(self.metrics) >= self.metric_limit:
            self._record_dropped()
            return
        self.metrics.setdefault(key, MetricAccumulator()).add(duration_ms, request_bytes, response_bytes)
        self.last_metric_key = key
        now = time.monotonic()
        if now - self.last_flush >= 1 and (self.flush_task is None or self.flush_task.done()):
            self.last_flush = now
            self.flush_task = asyncio.create_task(self.flush_metrics())

    async def flush_metrics(self) -> None:
        try:
            if self.redis is None:
                from redis.asyncio import from_url
                self.redis = from_url(self.redis_url, decode_responses=True, socket_timeout=0.5)
            pipe = self.redis.pipeline(transaction=False)
            for (bucket, service, method, route, status), metric in list(self.metrics.items()):
                redis_key = f"api_health:metrics:{bucket}"
                field_name = json.dumps([service, method, route, status], separators=(",", ":"))
                payload = metric.dump()
                pipe.hset(redis_key, field_name, json.dumps(payload, separators=(",", ":")))
                pipe.expire(redis_key, 7200)
            await pipe.execute()
            current = minute_bucket()
            self.metrics = {key: value for key, value in self.metrics.items() if key[0] == current}
        except Exception as exc:
            logger.warning("api health Redis flush failed for %s: %s", self.service, exc)

    def add_error(self, payload: dict[str, Any]) -> None:
        self._ensure_tasks()
        if payload["status_code"] < 500:
            occurred = payload["occurred_at"]
            minute = (int(occurred[14:16]) // 5) * 5
            window = f"{occurred[:14]}{minute:02d}"
            sample_key = (window, payload["route"], payload["status_code"], payload["error_fingerprint"])
            count = self.sample_counts.get(sample_key, 0)
            if count >= 5:
                return
            self.sample_counts[sample_key] = count + 1
            if len(self.sample_counts) > 2_000:
                self.sample_counts = {sample_key: count + 1}
        try:
            self.error_queue.put_nowait(payload)
        except asyncio.QueueFull:
            self._record_dropped()
            logger.error("api health error queue full for %s", self.service)

    def _record_dropped(self, count: int = 1) -> None:
        """Assign dropped events to one request series so aggregate sums stay exact."""
        self.dropped_events += count
        key = self.last_metric_key
        if key is not None and key in self.metrics:
            self.metrics[key].dropped_events += count

    async def _error_writer(self) -> None:
        while True:
            first = await self.error_queue.get()
            batch = [first]
            await asyncio.sleep(0.15)
            while len(batch) < 100:
                try:
                    batch.append(self.error_queue.get_nowait())
                except asyncio.QueueEmpty:
                    break
            try:
                async with self.session_factory() as session:
                    session.add_all(ApiErrorEvent(**item) for item in batch)
                    await session.commit()
            except Exception as exc:
                logger.error("api health error batch persist failed for %s: %s", self.service, exc)
                self._record_dropped(len(batch))
            finally:
                for _ in batch:
                    self.error_queue.task_done()


class ApiHealthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, service: str, redis_url: str, session_factory: async_sessionmaker):
        super().__init__(app)
        self.collector = ApiHealthCollector(service, redis_url, session_factory)
        self.service = service
        self.enabled = os.environ.get("API_HEALTH_ENABLED", "1").strip().lower() not in {"0", "false", "off", "no"}

    @staticmethod
    def _excluded(path: str) -> bool:
        return path == "/health" or path.endswith("/health") or "/api/api-health" in path

    async def dispatch(self, request: Request, call_next: Callable):
        if not self.enabled or self._excluded(request.url.path):
            return await call_next(request)
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        response = None
        status = 500
        caught: Exception | None = None
        try:
            response = await call_next(request)
            status = response.status_code
            caught = getattr(request.state, "api_exception", None)
            return response
        except Exception as exc:
            caught = exc
            status = 500
            raise
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            route = route_template(request)
            request_bytes = int(request.headers.get("content-length") or 0)
            response_bytes = int(response.headers.get("content-length") or 0) if response else 0
            self.collector.add_metric(request.method, route, status, duration_ms, request_bytes, response_bytes)
            if status >= 400:
                message = redact(caught or f"HTTP {status}", limit=2_000)
                exc_type = type(caught).__name__ if caught else None
                tb = redact("".join(traceback_module.format_exception(caught)), limit=16_384) if caught else None
                fingerprint = error_fingerprint(self.service, route, status, exc_type, message)
                self.collector.add_error({
                    "occurred_at": utc_iso(), "request_id": request_id, "service": self.service,
                    "method": request.method, "route": route, "status_code": status,
                    "duration_ms": round(duration_ms, 3), "user_id": getattr(request.state, "api_user_id", None),
                    "tg_id": getattr(request.state, "api_tg_id", None), "actor": getattr(request.state, "api_actor", None),
                    "client_ip": real_client_ip(request), "client_channel": client_channel(request, self.service),
                    "user_agent": (request.headers.get("user-agent") or "")[:512] or None,
                    "app_version": (request.headers.get("x-app-version") or "")[:64] or None,
                    "request_bytes": request_bytes, "response_bytes": response_bytes,
                    "exception_type": exc_type, "error_message": message, "error_fingerprint": fingerprint,
                    "traceback": tb,
                })
            if response is not None:
                response.headers["X-Request-ID"] = request_id
