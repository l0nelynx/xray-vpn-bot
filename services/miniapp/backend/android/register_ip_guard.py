"""Sliding-window limit on successful registrations per client IP.

Not a permanent 1-IP-1-account ban: capacity returns as events age out of
the windows. Shared by Android and web register handlers.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict

from fastapi import HTTPException

# Soft burst: 3 successful registers / rolling hour.
HOUR_WINDOW_SECONDS = 3_600
HOUR_MAX = 3

# Daily cap: 10 successful registers / rolling day.
DAY_WINDOW_SECONDS = 86_400
DAY_MAX = 10

_lock = threading.Lock()
_success_ts: dict[str, list[float]] = defaultdict(list)


def _retry_after(events: list[float], *, limit: int, window: float, now: float) -> int:
    """Seconds until the oldest event in a full window falls out."""
    if len(events) < limit:
        return 0
    # After `limit` successes, the next is blocked until events[0] ages out
    # when we consider the last `limit` events in the window.
    oldest_in_cap = events[-limit]
    return max(1, int(oldest_in_cap + window - now) + 1)


def check(ip: str) -> None:
    """Raise 429 if this IP has exhausted the hour or day registration quota."""
    if not ip or ip == "unknown":
        return
    now = time.time()
    with _lock:
        events = [t for t in _success_ts[ip] if now - t < DAY_WINDOW_SECONDS]
        _success_ts[ip] = events

        hour_events = [t for t in events if now - t < HOUR_WINDOW_SECONDS]
        if len(hour_events) >= HOUR_MAX:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "rate_limited",
                    "retry_after": _retry_after(
                        hour_events, limit=HOUR_MAX, window=HOUR_WINDOW_SECONDS, now=now
                    ),
                },
            )
        if len(events) >= DAY_MAX:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "rate_limited",
                    "retry_after": _retry_after(
                        events, limit=DAY_MAX, window=DAY_WINDOW_SECONDS, now=now
                    ),
                },
            )


def record(ip: str) -> None:
    """Record one successful registration for an IP."""
    if not ip or ip == "unknown":
        return
    with _lock:
        _success_ts[ip].append(time.time())


def reset() -> None:
    """Clear all state (tests only)."""
    with _lock:
        _success_ts.clear()
