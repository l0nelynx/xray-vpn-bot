"""Flush request telemetry, probe the APIs, and send deduplicated alerts."""
from __future__ import annotations

import html
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from common_db.api_health import utc_iso
from common_db.models import ApiAlertState, ApiMetricMinute, ApiServiceStatus
from common_db.repo.api_health import apply_retention, compact_minutes, flush_redis_metrics, merge_histograms, percentile_ms
from common_db.repo.runtime import get_runtime_config_dict

from .config import get_config
from .database.session import async_session

logger = logging.getLogger(__name__)
SERVICES = {
    "miniapp": "http://miniapp:8001/bot/miniapp/api/health",
    "bot": "http://bot:5000/bot/health",
    "dashboard": "http://dashboard:8000/bot/dashboard/api/health",
}
DEFAULTS = {
    "enabled": True, "server_error_threshold": 20, "latency_p95_ms": 2000,
    "latency_min_requests": 20, "health_failures": 3, "cooldown_minutes": 30,
}


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def _send_telegram(text: str) -> None:
    cfg = get_config()
    token = str(cfg.get("admin_bot_token") or "")
    chat_id = cfg.get("logs_id") or cfg.get("admin_id")
    if not token or not chat_id:
        logger.warning("API health alert not sent: admin_bot_token/logs_id are not configured")
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
            )
        if response.status_code >= 400:
            logger.warning("API health Telegram returned %s", response.status_code)
    except Exception as exc:
        logger.warning("API health Telegram failed: %s", exc)


async def _transition_alert(session, key: str, triggered: bool, value: float, message: str, recovery: str, cooldown: int) -> None:
    now = datetime.now(timezone.utc)
    row = await session.get(ApiAlertState, key)
    if row is None:
        row = ApiAlertState(key=key, active=False, updated_at=utc_iso(now))
        session.add(row)
    last_sent = _parse_iso(row.last_sent_at)
    can_send = last_sent is None or now - last_sent >= timedelta(minutes=cooldown)
    if triggered and (not row.active or can_send):
        await _send_telegram(message)
        row.last_sent_at = utc_iso(now)
    elif not triggered and row.active:
        await _send_telegram(recovery)
        row.last_sent_at = utc_iso(now)
    row.active = triggered
    row.last_value = value
    row.updated_at = utc_iso(now)


async def _probe_services(session) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(3, connect=2)) as client:
        for service, url in SERVICES.items():
            started = time.perf_counter()
            healthy = False
            error = None
            try:
                response = await client.get(url)
                healthy = response.status_code == 200
                if not healthy:
                    error = f"HTTP {response.status_code}"
            except Exception as exc:
                error = str(exc)[:500]
            elapsed = (time.perf_counter() - started) * 1000
            row = await session.get(ApiServiceStatus, service)
            if row is None:
                row = ApiServiceStatus(service=service, is_healthy=False, checked_at=utc_iso())
                session.add(row)
            row.is_healthy = healthy
            row.checked_at = utc_iso()
            row.response_time_ms = round(elapsed, 2)
            row.last_error = None if healthy else error
            if healthy:
                row.last_ok_at = row.checked_at
                row.consecutive_failures = 0
            else:
                row.consecutive_failures = int(row.consecutive_failures or 0) + 1


async def _evaluate_alerts(session) -> None:
    config = dict(DEFAULTS)
    runtime = await get_runtime_config_dict(session)
    config.update(runtime.get("api_health_alerts") or {})
    if not config["enabled"]:
        return
    since = utc_iso(datetime.now(timezone.utc) - timedelta(minutes=5))
    rows = list((await session.scalars(select(ApiMetricMinute).where(ApiMetricMinute.bucket_start >= since))).all())
    for service in SERVICES:
        own = [r for r in rows if r.service == service]
        total = sum(r.request_count for r in own)
        server_errors = sum(r.request_count for r in own if r.status_code >= 500)
        p95 = percentile_ms(merge_histograms(r.histogram_json for r in own), 0.95)
        await _transition_alert(
            session, f"{service}:5xx", server_errors > int(config["server_error_threshold"]), float(server_errors),
            f"🚨 <b>API 5xx spike</b>\nService: <code>{html.escape(service)}</code>\n5xx in 5 min: <b>{server_errors}</b>\nRequests: {total}",
            f"✅ <b>API recovered</b>\nService: <code>{html.escape(service)}</code>\n5xx rate returned below threshold.",
            int(config["cooldown_minutes"]),
        )
        latency_triggered = total >= int(config["latency_min_requests"]) and p95 > float(config["latency_p95_ms"])
        await _transition_alert(
            session, f"{service}:latency", latency_triggered, p95,
            f"🐢 <b>API latency degraded</b>\nService: <code>{html.escape(service)}</code>\np95: <b>{p95:.0f} ms</b>\nRequests: {total}",
            f"✅ <b>API latency recovered</b>\nService: <code>{html.escape(service)}</code>",
            int(config["cooldown_minutes"]),
        )
    statuses = list((await session.scalars(select(ApiServiceStatus))).all())
    for status in statuses:
        triggered = not status.is_healthy and status.consecutive_failures >= int(config["health_failures"])
        await _transition_alert(
            session, f"{status.service}:availability", triggered, float(status.consecutive_failures),
            f"🔴 <b>API unavailable</b>\nService: <code>{html.escape(status.service)}</code>\nChecks failed: {status.consecutive_failures}\n{html.escape(status.last_error or '')}",
            f"🟢 <b>API available again</b>\nService: <code>{html.escape(status.service)}</code>",
            int(config["cooldown_minutes"]),
        )


async def api_health_tick(ctx) -> None:
    redis = ctx["redis"]
    now = datetime.now(timezone.utc)
    redis_keys_to_delete: list[str] = []
    async with async_session() as session:
        try:
            try:
                _, redis_keys_to_delete = await flush_redis_metrics(session, redis)
            except Exception:
                # Redis is a disposable buffer. Its outage must not suppress
                # API probes or make the worker transaction fail.
                logger.exception("API health Redis flush failed")
            await _probe_services(session)
            await _evaluate_alerts(session)
            await compact_minutes(session, now)
            # Retention is deliberately a daily batch, not a delete scan every minute.
            if now.hour == 3 and now.minute == 0:
                await apply_retention(session, now)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("API health worker tick failed")
            return
    if redis_keys_to_delete:
        try:
            await redis.delete(*redis_keys_to_delete)
        except Exception:
            # PostgreSQL already contains absolute upserts, so retrying these
            # Redis snapshots next minute remains idempotent.
            logger.warning("API health Redis cleanup failed", exc_info=True)
