"""In-memory brute-force / DDoS guard for the web portal.

Tracks failed invite-code validation attempts per source IP.  After
MAX_FAILS failures within WINDOW_SECONDS the IP is blocked for
BLOCK_SECONDS.  State is per-process and resets on container restart;
for a single-container deployment this is sufficient protection.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict

from fastapi import HTTPException

WINDOW_SECONDS = 3_600    # rolling 1-hour window for counting failures
MAX_FAILS = 20            # block threshold within the window
BLOCK_SECONDS = 86_400    # 24-hour block after threshold is crossed

_lock = threading.Lock()
_fail_ts: dict[str, list[float]] = defaultdict(list)  # ip → timestamps of failures
_blocked_until: dict[str, float] = {}                  # ip → unblock epoch


def check(ip: str) -> None:
    """Raise HTTP 429 if the IP is currently blocked or has too many recent failures."""
    now = time.time()
    with _lock:
        unblock_at = _blocked_until.get(ip, 0)
        if unblock_at > now:
            raise HTTPException(
                status_code=429,
                detail={"code": "rate_limited", "retry_after": int(unblock_at - now)},
            )
        # Prune timestamps outside the sliding window
        _fail_ts[ip] = [t for t in _fail_ts[ip] if now - t < WINDOW_SECONDS]
        if len(_fail_ts[ip]) >= MAX_FAILS:
            _blocked_until[ip] = now + BLOCK_SECONDS
            raise HTTPException(
                status_code=429,
                detail={"code": "rate_limited", "retry_after": BLOCK_SECONDS},
            )


def record_fail(ip: str) -> None:
    """Record one failed attempt for an IP."""
    with _lock:
        _fail_ts[ip].append(time.time())


def clear(ip: str) -> None:
    """Reset the failure counter for an IP (call on successful validation)."""
    with _lock:
        _fail_ts[ip] = []
