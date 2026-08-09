"""Persistence and aggregation helpers for API health telemetry."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api_health import LATENCY_BUCKETS_MS, utc_iso
from ..models import ApiAlertState, ApiErrorEvent, ApiMetricHour, ApiMetricMinute


def histogram(value: str | dict | None) -> dict[str, int]:
    if isinstance(value, dict):
        return {str(k): int(v) for k, v in value.items()}
    try:
        parsed = json.loads(value or "{}")
        return {str(k): int(v) for k, v in parsed.items()}
    except (TypeError, ValueError):
        return {}


def merge_histograms(values: Iterable[str | dict | None]) -> dict[str, int]:
    result: dict[str, int] = defaultdict(int)
    for value in values:
        for key, count in histogram(value).items():
            result[key] += count
    return dict(result)


def percentile_ms(hist: dict[str, int], percentile: float) -> float:
    total = sum(hist.values())
    if total <= 0:
        return 0.0
    target = total * percentile
    cumulative = 0
    ordered = [str(v) for v in LATENCY_BUCKETS_MS] + ["inf"]
    for key in ordered:
        cumulative += int(hist.get(key, 0))
        if cumulative >= target:
            return float(30_000 if key == "inf" else key)
    return 0.0


def histogram_count_over(hist: dict[str, int], threshold_ms: int) -> int:
    """Approximate requests slower than a threshold using the fixed buckets."""
    return sum(count for bound, count in hist.items() if bound == "inf" or int(bound) > threshold_ms)


async def upsert_minute_payload(session: AsyncSession, bucket: str, identity: list[Any], payload: dict[str, Any]) -> None:
    service, method, route, status_code = identity
    row = await session.scalar(select(ApiMetricMinute).where(
        ApiMetricMinute.bucket_start == bucket, ApiMetricMinute.service == service,
        ApiMetricMinute.method == method, ApiMetricMinute.route == route,
        ApiMetricMinute.status_code == int(status_code),
    ))
    if row is None:
        row = ApiMetricMinute(bucket_start=bucket, service=service, method=method, route=route, status_code=int(status_code))
        session.add(row)
    row.request_count = int(payload.get("request_count", 0))
    row.duration_sum_ms = float(payload.get("duration_sum_ms", 0))
    row.duration_max_ms = float(payload.get("duration_max_ms", 0))
    row.request_bytes = int(payload.get("request_bytes", 0))
    row.response_bytes = int(payload.get("response_bytes", 0))
    row.histogram_json = json.dumps(payload.get("histogram") or {}, separators=(",", ":"))
    row.dropped_events = int(payload.get("dropped_events", 0))


async def flush_redis_metrics(session: AsyncSession, redis: Any) -> tuple[int, list[str]]:
    """Upsert Redis snapshots and return old keys safe to delete after commit."""
    flushed = 0
    safe_before = utc_iso(datetime.now(timezone.utc) - timedelta(minutes=2))
    processed_keys: list[str] = []
    async for key in redis.scan_iter(match="api_health:metrics:*"):
        key_text = key.decode() if isinstance(key, bytes) else str(key)
        # ISO timestamps contain colons, so splitting on the last colon would
        # silently turn every bucket into just ``00Z``.
        bucket = key_text.removeprefix("api_health:metrics:")
        values = await redis.hgetall(key)
        for raw_identity, raw_payload in values.items():
            try:
                identity = json.loads(raw_identity.decode() if isinstance(raw_identity, bytes) else raw_identity)
                payload = json.loads(raw_payload.decode() if isinstance(raw_payload, bytes) else raw_payload)
                await upsert_minute_payload(session, bucket, identity, payload)
                flushed += 1
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
        # Keep the current and immediately previous minute to avoid racing a
        # request that crossed the minute boundary and is still being recorded.
        if bucket < safe_before:
            processed_keys.append(key_text)
    return flushed, processed_keys


async def compact_minutes(session: AsyncSession, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    minute_cutoff = utc_iso(now - timedelta(hours=24))
    minute_rows = list((await session.scalars(
        select(ApiMetricMinute).where(ApiMetricMinute.bucket_start < minute_cutoff).order_by(ApiMetricMinute.bucket_start).limit(20_000)
    )).all())
    grouped: dict[tuple[str, str, str, str, int], list[ApiMetricMinute]] = defaultdict(list)
    for row in minute_rows:
        hour = row.bucket_start[:13] + ":00:00Z"
        grouped[(hour, row.service, row.method, row.route, row.status_code)].append(row)
    for key, rows in grouped.items():
        hour, service, method, route, status_code = key
        target = await session.scalar(select(ApiMetricHour).where(
            ApiMetricHour.bucket_start == hour, ApiMetricHour.service == service,
            ApiMetricHour.method == method, ApiMetricHour.route == route, ApiMetricHour.status_code == status_code,
        ))
        if target is None:
            target = ApiMetricHour(bucket_start=hour, service=service, method=method, route=route, status_code=status_code)
            session.add(target)
        target.request_count = int(target.request_count or 0) + sum(r.request_count for r in rows)
        target.duration_sum_ms = float(target.duration_sum_ms or 0) + sum(r.duration_sum_ms for r in rows)
        target.duration_max_ms = max(float(target.duration_max_ms or 0), max((r.duration_max_ms for r in rows), default=0))
        target.request_bytes = int(target.request_bytes or 0) + sum(r.request_bytes for r in rows)
        target.response_bytes = int(target.response_bytes or 0) + sum(r.response_bytes for r in rows)
        target.dropped_events = int(target.dropped_events or 0) + sum(r.dropped_events for r in rows)
        target.histogram_json = json.dumps(
            merge_histograms([target.histogram_json, *(r.histogram_json for r in rows)]), separators=(",", ":")
        )
    if minute_rows:
        # Persist the roll-up before deleting its source rows or applying
        # retention in the same transaction (important with bulk statements).
        await session.flush()
        await session.execute(delete(ApiMetricMinute).where(ApiMetricMinute.id.in_([r.id for r in minute_rows])))


async def apply_retention(session: AsyncSession, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    error_cutoff = utc_iso(now - timedelta(days=7))
    hour_cutoff = utc_iso(now - timedelta(days=90))
    await session.execute(delete(ApiErrorEvent).where(ApiErrorEvent.occurred_at < error_cutoff))
    await session.execute(delete(ApiMetricHour).where(ApiMetricHour.bucket_start < hour_cutoff))
    await session.execute(delete(ApiAlertState).where(ApiAlertState.updated_at < hour_cutoff))


async def compact_and_retain(session: AsyncSession, now: datetime | None = None) -> None:
    """Compatibility helper used by maintenance commands and tests."""
    await compact_minutes(session, now)
    await apply_retention(session, now)
