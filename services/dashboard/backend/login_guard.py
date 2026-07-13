"""In-memory login throttle for the dashboard admin endpoint.

Stops unlimited password guessing against the single admin credential. State is
per-process; the dashboard runs as one single-worker container, so this is
sufficient (and resets on restart). If the dashboard is ever scaled out, move
this state to Postgres/Redis — see the single-worker note in docs/deployment.md.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request

WINDOW_SECONDS = 900   # rolling 15-minute window for counting failures
MAX_FAILS = 10         # block after this many failures within the window
BLOCK_SECONDS = 900    # 15-minute block once the threshold is crossed

_lock = threading.Lock()
_fails: dict[str, list[float]] = defaultdict(list)   # ip -> failure timestamps
_blocked_until: dict[str, float] = {}                # ip -> unblock epoch


def real_client_ip(request: Request) -> str:
    """Real client IP behind the trusted edge nginx (X-Real-IP), not the socket
    peer — otherwise every admin login appears to come from the nginx container
    and the throttle becomes one shared global bucket."""
    xri = request.headers.get("x-real-ip")
    if xri and xri.strip():
        return xri.strip()
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        hops = [p.strip() for p in fwd.split(",") if p.strip()]
        if hops:
            return hops[-1]
    return request.client.host if request.client else "unknown"


def check(ip: str) -> None:
    """Raise HTTP 429 if the IP is currently blocked or over the fail threshold."""
    now = time.time()
    with _lock:
        unblock_at = _blocked_until.get(ip, 0)
        if unblock_at > now:
            raise HTTPException(
                status_code=429,
                detail={"code": "rate_limited", "retry_after": int(unblock_at - now)},
            )
        _fails[ip] = [t for t in _fails[ip] if now - t < WINDOW_SECONDS]
        if len(_fails[ip]) >= MAX_FAILS:
            _blocked_until[ip] = now + BLOCK_SECONDS
            raise HTTPException(
                status_code=429,
                detail={"code": "rate_limited", "retry_after": BLOCK_SECONDS},
            )


def record_fail(ip: str) -> None:
    """Record one failed login for an IP."""
    with _lock:
        _fails[ip].append(time.time())


def clear(ip: str) -> None:
    """Reset the failure counter for an IP (call on successful login)."""
    with _lock:
        _fails[ip] = []
