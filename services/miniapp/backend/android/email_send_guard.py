"""Cooldown-send cooldown keyed independently by email and by IP.

Rules per key:
  * 3 consecutive sends → block 5 minutes
  * 10 sends in a rolling 24h → block 48 hours
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field

from fastapi import HTTPException

CONSECUTIVE_LIMIT = 3
CONSECUTIVE_BLOCK_SECONDS = 5 * 60

DAY_LIMIT = 10
DAY_WINDOW_SECONDS = 86_400
DAY_BLOCK_SECONDS = 48 * 3_600


@dataclass
class _Bucket:
    send_ts: list[float] = field(default_factory=list)
    consecutive: int = 0
    blocked_until: float = 0.0


_lock = threading.Lock()
_buckets: dict[str, _Bucket] = defaultdict(_Bucket)


def _key_email(email: str) -> str:
    return f"email:{(email or '').strip().lower()}"


def _key_ip(ip: str) -> str:
    return f"ip:{(ip or '').strip()}"


def _raise_if_blocked(bucket: _Bucket, *, now: float) -> None:
    if bucket.blocked_until > now:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "rate_limited",
                "retry_after": max(1, int(bucket.blocked_until - now)),
            },
        )


def _check_one(key: str, *, now: float) -> None:
    bucket = _buckets[key]
    _raise_if_blocked(bucket, now=now)
    bucket.send_ts = [t for t in bucket.send_ts if now - t < DAY_WINDOW_SECONDS]
    if len(bucket.send_ts) >= DAY_LIMIT:
        bucket.blocked_until = max(bucket.blocked_until, now + DAY_BLOCK_SECONDS)
        _raise_if_blocked(bucket, now=now)


def _record_one(key: str, *, now: float) -> None:
    bucket = _buckets[key]
    bucket.send_ts = [t for t in bucket.send_ts if now - t < DAY_WINDOW_SECONDS]
    bucket.send_ts.append(now)
    bucket.consecutive += 1

    if len(bucket.send_ts) >= DAY_LIMIT:
        bucket.blocked_until = max(bucket.blocked_until, now + DAY_BLOCK_SECONDS)
        bucket.consecutive = 0
    elif bucket.consecutive >= CONSECUTIVE_LIMIT:
        # 3 sends allowed, then cool down; reset streak so the next window
        # grants another burst of CONSECUTIVE_LIMIT after the block expires.
        bucket.blocked_until = max(
            bucket.blocked_until, now + CONSECUTIVE_BLOCK_SECONDS
        )
        bucket.consecutive = 0


def check(*, email: str | None = None, ip: str | None = None) -> None:
    """Raise 429 if email and/or IP is currently limited."""
    now = time.time()
    with _lock:
        if email:
            _check_one(_key_email(email), now=now)
        if ip and ip != "unknown":
            _check_one(_key_ip(ip), now=now)


def record(*, email: str | None = None, ip: str | None = None) -> None:
    """Record a code-send attempt for email and/or IP."""
    now = time.time()
    with _lock:
        if email:
            _record_one(_key_email(email), now=now)
        if ip and ip != "unknown":
            _record_one(_key_ip(ip), now=now)


def clear_consecutive(*, email: str | None = None) -> None:
    """Reset the consecutive-send counter after a successful code consume."""
    if not email:
        return
    with _lock:
        bucket = _buckets.get(_key_email(email))
        if bucket is not None:
            bucket.consecutive = 0


def reset() -> None:
    """Clear all state (tests only)."""
    with _lock:
        _buckets.clear()
