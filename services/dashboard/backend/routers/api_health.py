"""Authenticated API Health read model and alert settings."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import String, case, cast, func, or_, select

from common_db.api_health import utc_iso
from common_db.models import ApiErrorEvent, ApiMetricHour, ApiMetricMinute, ApiServiceStatus
from common_db.repo.api_health import histogram_count_over, merge_histograms, percentile_ms
from common_db.repo.runtime import get_runtime_config_dict, save_runtime_config
from common_db.runtime_config import invalidate_local

from ..auth import get_current_user
from ..database.session import async_session

router = APIRouter(prefix="/api/api-health", tags=["api-health"])
RANGES = {"1h": 1, "6h": 6, "24h": 24, "7d": 168, "30d": 720, "90d": 2160}
SERVICES = ("miniapp", "bot", "dashboard")
DEFAULT_SETTINGS = {
    "enabled": True, "server_error_threshold": 20, "latency_p95_ms": 2000,
    "latency_min_requests": 20, "health_failures": 3, "cooldown_minutes": 30,
}


class AlertSettings(BaseModel):
    enabled: bool = True
    server_error_threshold: int = Field(20, ge=1, le=100_000)
    latency_p95_ms: int = Field(2000, ge=50, le=120_000)
    latency_min_requests: int = Field(20, ge=1, le=100_000)
    health_failures: int = Field(3, ge=1, le=30)
    cooldown_minutes: int = Field(30, ge=1, le=1440)


def _start(range_name: str) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=RANGES.get(range_name, 24))


async def _metric_rows(session, range_name: str, service: str | None = None):
    now = datetime.now(timezone.utc)
    start = (now - timedelta(hours=RANGES.get(range_name, 24))).replace(second=0, microsecond=0)
    cutoff = (now - timedelta(hours=24)).replace(second=0, microsecond=0)
    rows = []
    if start < cutoff:
        query = select(ApiMetricHour).where(ApiMetricHour.bucket_start >= utc_iso(start), ApiMetricHour.bucket_start < utc_iso(cutoff))
        if service:
            query = query.where(ApiMetricHour.service == service)
        rows.extend((await session.scalars(query)).all())
    query = select(ApiMetricMinute).where(ApiMetricMinute.bucket_start >= utc_iso(max(start, cutoff)))
    if service:
        query = query.where(ApiMetricMinute.service == service)
    rows.extend((await session.scalars(query)).all())
    return list(rows)


def _stats(rows) -> dict:
    total = sum(r.request_count for r in rows)
    c4 = sum(r.request_count for r in rows if 400 <= r.status_code < 500)
    c5 = sum(r.request_count for r in rows if r.status_code >= 500)
    durations = sum(r.duration_sum_ms for r in rows)
    hist = merge_histograms(r.histogram_json for r in rows)
    return {
        "requests": total,
        "success_rate": round((total - c4 - c5) / total * 100, 2) if total else 100.0,
        "client_errors": c4, "server_errors": c5,
        "error_rate": round((c4 + c5) / total * 100, 2) if total else 0.0,
        "avg_ms": round(durations / total, 2) if total else 0.0,
        "p50_ms": percentile_ms(hist, .50), "p95_ms": percentile_ms(hist, .95),
        "p99_ms": percentile_ms(hist, .99),
        "max_ms": round(max((r.duration_max_ms for r in rows), default=0), 2),
        "client_error_rate": round(c4 / total * 100, 2) if total else 0.0,
        "server_error_rate": round(c5 / total * 100, 2) if total else 0.0,
        "slow_requests": histogram_count_over(hist, 2_000),
        "dropped_events": sum(r.dropped_events for r in rows),
    }


@router.get("/summary")
async def summary(
    range: str = Query("24h"), service: str | None = Query(None),
    _: str = Depends(get_current_user),
):
    if range not in RANGES or (service and service not in SERVICES):
        raise HTTPException(400, "invalid range or service")
    async with async_session() as session:
        rows = await _metric_rows(session, range, service)
        statuses = list((await session.scalars(select(ApiServiceStatus).order_by(ApiServiceStatus.service))).all())
    stats = _stats(rows)
    stats["avg_rps"] = round(stats["requests"] / (RANGES[range] * 3600), 3)
    stats["last_telemetry_at"] = max((r.bucket_start for r in rows), default=None)
    stats["services"] = [{
        "service": s.service, "is_healthy": s.is_healthy, "checked_at": s.checked_at,
        "last_ok_at": s.last_ok_at, "last_error": s.last_error,
        "consecutive_failures": s.consecutive_failures, "response_time_ms": s.response_time_ms,
    } for s in statuses]
    return stats


def _series_key(value: str, range_name: str) -> str:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    hours = RANGES[range_name]
    if hours <= 6:
        minute = (dt.minute // 5) * 5
        dt = dt.replace(minute=minute, second=0, microsecond=0)
    elif hours <= 24:
        dt = dt.replace(minute=0, second=0, microsecond=0)
    else:
        dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return utc_iso(dt)


@router.get("/series")
async def series(range: str = Query("24h"), service: str | None = Query(None), _: str = Depends(get_current_user)):
    if range not in RANGES or (service and service not in SERVICES):
        raise HTTPException(400, "invalid range or service")
    async with async_session() as session:
        rows = await _metric_rows(session, range, service)
    grouped = defaultdict(list)
    for row in rows:
        grouped[_series_key(row.bucket_start, range)].append(row)
    result = []
    for bucket, values in sorted(grouped.items()):
        stat = _stats(values)
        result.append({"bucket": bucket, "requests": stat["requests"], "status_2xx": sum(r.request_count for r in values if 200 <= r.status_code < 300),
            "status_3xx": sum(r.request_count for r in values if 300 <= r.status_code < 400), "status_4xx": stat["client_errors"],
            "status_5xx": stat["server_errors"], "error_rate": stat["error_rate"], "p50_ms": stat["p50_ms"],
            "p95_ms": stat["p95_ms"], "p99_ms": stat["p99_ms"]})
    return result


@router.get("/endpoints")
async def endpoints(range: str = Query("24h"), service: str | None = Query(None), _: str = Depends(get_current_user)):
    if range not in RANGES or (service and service not in SERVICES):
        raise HTTPException(400, "invalid range or service")
    async with async_session() as session:
        rows = await _metric_rows(session, range, service)
        grouped = defaultdict(list)
        for row in rows:
            grouped[(row.service, row.method, row.route)].append(row)
        error_query = select(
            ApiErrorEvent.service, ApiErrorEvent.method, ApiErrorEvent.route, func.max(ApiErrorEvent.occurred_at)
        ).where(ApiErrorEvent.occurred_at >= utc_iso(_start(range)))
        if service:
            error_query = error_query.where(ApiErrorEvent.service == service)
        last_errors = list((await session.execute(
            error_query.group_by(ApiErrorEvent.service, ApiErrorEvent.method, ApiErrorEvent.route)
        )).all())
    error_map = {(r.service, r.method, r.route): r[3] for r in last_errors}
    result = []
    for key, values in grouped.items():
        stat = _stats(values)
        result.append({"service": key[0], "method": key[1], "route": key[2], **stat, "last_error_at": error_map.get(key)})
    return sorted(result, key=lambda item: (item["server_errors"], item["requests"]), reverse=True)


@router.get("/errors")
async def errors(
    range: str = Query("24h"), page: int = Query(1, ge=1), per_page: int = Query(25, ge=1, le=100),
    service: str | None = None, status_class: Literal["4xx", "5xx"] | None = None,
    route: str | None = None, user_id: int | None = None, tg_id: int | None = None,
    ip: str | None = None, request_id: str | None = None, fingerprint: str | None = None,
    q: str | None = Query(None, max_length=200),
    _: str = Depends(get_current_user),
):
    if range not in RANGES:
        raise HTTPException(400, "invalid range")
    filters = [ApiErrorEvent.occurred_at >= utc_iso(_start(range))]
    for value, column in ((service, ApiErrorEvent.service), (route, ApiErrorEvent.route), (user_id, ApiErrorEvent.user_id),
                          (tg_id, ApiErrorEvent.tg_id), (ip, ApiErrorEvent.client_ip), (request_id, ApiErrorEvent.request_id),
                          (fingerprint, ApiErrorEvent.error_fingerprint)):
        if value is not None and value != "": filters.append(column == value)
    if status_class == "4xx": filters.extend((ApiErrorEvent.status_code >= 400, ApiErrorEvent.status_code < 500))
    if status_class == "5xx": filters.append(ApiErrorEvent.status_code >= 500)
    if q and q.strip():
        needle = f"%{q.strip()}%"
        filters.append(or_(
            ApiErrorEvent.route.ilike(needle), ApiErrorEvent.request_id.ilike(needle),
            ApiErrorEvent.client_ip.ilike(needle), ApiErrorEvent.error_fingerprint.ilike(needle),
            cast(ApiErrorEvent.user_id, String).ilike(needle), cast(ApiErrorEvent.tg_id, String).ilike(needle),
        ))
    async with async_session() as session:
        total = await session.scalar(select(func.count()).select_from(ApiErrorEvent).where(*filters)) or 0
        items = list((await session.scalars(select(ApiErrorEvent).where(*filters).order_by(ApiErrorEvent.occurred_at.desc()).offset((page - 1) * per_page).limit(per_page))).all())
        identity = case(
            (ApiErrorEvent.user_id.is_not(None), cast(ApiErrorEvent.user_id, String)),
            else_=cast(ApiErrorEvent.tg_id, String),
        )
        groups = list((await session.execute(
            select(
                ApiErrorEvent.error_fingerprint, func.max(ApiErrorEvent.service),
                func.max(ApiErrorEvent.route), func.max(ApiErrorEvent.status_code),
                func.max(ApiErrorEvent.exception_type), func.max(ApiErrorEvent.error_message),
                func.count(), func.count(func.distinct(identity)), func.max(ApiErrorEvent.occurred_at),
            ).where(*filters).group_by(ApiErrorEvent.error_fingerprint).order_by(func.count().desc()).limit(20)
        )).all())
    return {
        "items": [_error_dict(row, include_traceback=False) for row in items],
        "groups": [{
            "fingerprint": row[0], "service": row[1], "route": row[2], "status_code": row[3],
            "exception_type": row[4], "message": row[5], "count": row[6],
            "affected_users": row[7], "last_seen_at": row[8],
        } for row in groups],
        "total": total, "page": page, "per_page": per_page,
    }


def _error_dict(row: ApiErrorEvent, *, include_traceback: bool) -> dict:
    data = {c.name: getattr(row, c.name) for c in row.__table__.columns if c.name != "traceback"}
    if include_traceback: data["traceback"] = row.traceback
    return data


@router.get("/errors/{error_id}")
async def error_detail(error_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        row = await session.get(ApiErrorEvent, error_id)
    if row is None: raise HTTPException(404, "error event not found")
    return _error_dict(row, include_traceback=True)


@router.get("/settings", response_model=AlertSettings)
async def get_settings(_: str = Depends(get_current_user)):
    async with async_session() as session: runtime = await get_runtime_config_dict(session)
    return AlertSettings(**{**DEFAULT_SETTINGS, **(runtime.get("api_health_alerts") or {})})


@router.put("/settings", response_model=AlertSettings)
async def put_settings(body: AlertSettings, user: str = Depends(get_current_user)):
    async with async_session() as session:
        await save_runtime_config(session, {"api_health_alerts": body.model_dump()}, updated_by=user)
        await session.commit()
    invalidate_local()
    return body
