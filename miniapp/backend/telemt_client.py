import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from .config import get_telemt_header, get_telemt_server

logger = logging.getLogger(__name__)

_TIMEOUT = 10


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    header = get_telemt_header()
    if header:
        h["Authorization"] = header
    return h


def _base() -> str:
    base = get_telemt_server()
    if not base:
        raise RuntimeError("telemt_server not configured")
    return base


async def get_telemt_user(username: str) -> Optional[dict]:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(f"{_base()}/v1/users/{username}", headers=_headers())
        if r.status_code == 404:
            return None
        r.raise_for_status()
        envelope = r.json()
        return envelope.get("data", envelope)
    except Exception as e:
        logger.error("Telemt get_user(%s) failed: %s", username, e)
        return None


async def create_telemt_user(
    username: str,
    expire_days: int = 30,
    max_tcp_conns: Optional[int] = None,
    max_unique_ips: Optional[int] = None,
    data_quota_bytes: Optional[int] = None,
) -> Optional[dict]:
    payload: dict = {"username": username}
    if expire_days and expire_days > 0:
        expiration = datetime.now(timezone.utc) + timedelta(days=expire_days)
        payload["expiration_rfc3339"] = expiration.isoformat()
    if max_tcp_conns is not None:
        payload["max_tcp_conns"] = max_tcp_conns
    if max_unique_ips is not None:
        payload["max_unique_ips"] = max_unique_ips
    if data_quota_bytes is not None:
        payload["data_quota_bytes"] = data_quota_bytes
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(f"{_base()}/v1/users", headers=_headers(), json=payload)
        if r.status_code >= 400:
            logger.error("Telemt create_user(%s) status=%s", username, r.status_code)
            return None
        return await get_telemt_user(username)
    except Exception as e:
        logger.error("Telemt create_user(%s) failed: %s", username, e)
        return None


def first_link(links: dict | None) -> Optional[str]:
    if not links:
        return None
    for category in ("tls", "secure", "classic"):
        items = links.get(category) or []
        if items:
            return items[0]
    return None
