"""
Telemt API client for the bot.
Direct HTTP calls to the Telemt server configured in config.yml.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.settings import secrets

logger = logging.getLogger(__name__)

_TIMEOUT = 10


def _base_url() -> str:
    url = (secrets.get("telemt_server") or "").rstrip("/")
    if not url:
        raise RuntimeError("telemt_server not configured in config.yml")
    return url


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    header = secrets.get("telemt_header")
    if header:
        h["Authorization"] = header
    return h


async def list_telemt_users() -> list[dict]:
    """Get all Telemt users. Returns list of UserInfo dicts."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{_base_url()}/v1/users",
                headers=_headers(),
            )
        r.raise_for_status()
        envelope = r.json()
        data = envelope.get("data", envelope)
        # data may be a list directly or wrapped
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        logger.error("Telemt list_users error: %s", e)
        return []


async def get_telemt_user(username: str) -> Optional[dict]:
    """
    Get a Telemt user by username.
    Returns UserInfo dict or None if not found.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(
                f"{_base_url()}/v1/users/{username}",
                headers=_headers(),
            )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        envelope = r.json()
        # Telemt wraps responses in { ok, data, revision }
        return envelope.get("data", envelope)
    except Exception as e:
        logger.error("Telemt get_user error for %s: %s", username, e)
        return None


async def create_telemt_user(
    username: str,
    expire_days: int = 30,
    max_tcp_conns: Optional[int] = None,
    max_unique_ips: Optional[int] = None,
    data_quota_bytes: Optional[int] = None,
) -> Optional[dict]:
    """
    Create a new Telemt user. Returns UserInfo dict (with links) or None on error.
    """
    payload = {"username": username}

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
            r = await client.post(
                f"{_base_url()}/v1/users",
                headers=_headers(),
                json=payload,
            )
        if r.status_code >= 400:
            data = r.json()
            detail = data.get("error", {}).get("message", r.text)
            logger.error("Telemt create_user error: %s", detail)
            return None
        # POST returns 202 without full user data; fetch the created user to get links
        return await get_telemt_user(username)
    except Exception as e:
        logger.error("Telemt create_user exception: %s", e)
        return None


async def delete_telemt_user(username: str) -> bool:
    """Delete a Telemt user by username."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.delete(
                f"{_base_url()}/v1/users/{username}",
                headers=_headers(),
            )
        return r.status_code < 400
    except Exception as e:
        logger.error("Telemt delete_user error for %s: %s", username, e)
        return False


def format_telemt_links(links: dict) -> str:
    """
    Format UserLinks object into clickable hyperlinks for the user.
    links has keys: tls, secure, classic — each is a list of strings.
    """
    parts = []
    for category in ("tls", "secure", "classic"):
        link_list = links.get(category, [])
        for i, link in enumerate(link_list, 1):
            label = f"CONNECT_TO_PROXY ({category.upper()}" + (f" #{i})" if len(link_list) > 1 else ")")
            parts.append(f"<a href='{link}'>{label}</a>")
    return "\n".join(parts)
