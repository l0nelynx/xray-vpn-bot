"""Connect-page app-catalog endpoint.

Serves the VPN-app installation catalog consumed by the `/connect` page in the
Telegram MiniApp and the web portal. The format is the Remnawave
subscription-page `app-config.json` schema:

    platforms -> <os> -> apps[] -> blocks[] -> buttons[]

Buttons carry the placeholders ``{{SUBSCRIPTION_LINK}}`` / ``{{USERNAME}}`` which
the frontend substitutes per-user (the backend never sees the user's
subscription URL here — it stays in the authenticated `/me` response).

Resolution order:
  1. operator override file  (config `connect_app_config_path`, default
     ``/app/app-config.json``) — mount it like ``config.yml``; or
  2. the bundled default shipped inside the image.

The parsed JSON is cached in-process and invalidated by file mtime, so editing
the mounted override and restarting the miniapp container is enough — no
frontend rebuild. The catalog is non-sensitive, so the endpoint is public and
cacheable by the edge nginx.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..config import get_connect_app_config_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/connect", tags=["connect"])

_DEFAULT_PATH = Path(__file__).parent / "app_config.default.json"

# Simple (path, mtime) -> parsed-JSON cache.
_cache: dict | None = None
_cache_key: tuple[str, float] | None = None


def _resolve_path() -> Path:
    override = get_connect_app_config_path()
    if override:
        p = Path(override)
        if p.is_file():
            return p
    return _DEFAULT_PATH


def load_app_config() -> dict:
    """Return the active app catalog, served from cache unless the source file
    changed on disk. Falls back to the bundled default if a mounted override is
    unreadable/invalid."""
    global _cache, _cache_key
    path = _resolve_path()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    key = (str(path), mtime)
    if _cache is not None and _cache_key == key:
        return _cache

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.error("connect app-config load failed from %s: %s", path, exc)
        if path != _DEFAULT_PATH:
            logger.warning("falling back to bundled default app-config")
            data = json.loads(_DEFAULT_PATH.read_text(encoding="utf-8"))
            key = (str(_DEFAULT_PATH), 0.0)
        else:
            raise

    _cache, _cache_key = data, key
    return data


@router.get("/app-config")
async def get_app_config() -> JSONResponse:
    return JSONResponse(
        content=load_app_config(),
        headers={"Cache-Control": "public, max-age=300"},
    )
