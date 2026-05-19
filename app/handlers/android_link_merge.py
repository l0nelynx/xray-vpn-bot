"""Merge logic for the Android↔Telegram link conflict path.

Called from `android_link.consume_android_link_code` when an Android-side
`users` row and a Telegram-side `users` row both exist and need to be
collapsed into a single row. See
`docs/superpowers/specs/2026-05-19-android-link-conflict-design.md`.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _classify(info: Any) -> str:
    """Return "pro" | "free" | "none" for a Remnawave user dict.

    Matches the project-wide rule used in
    `remnawave_client.scenarios.resolve_scenario` and
    `app/handlers/tools.py:377`: PRO iff status == "active" and data_limit
    is None. 404 sentinel and None map to "none".
    """
    if info is None or info == 404:
        return "none"
    status = info.get("status")
    data_limit = info.get("data_limit")
    if status == "active" and data_limit is None:
        return "pro"
    return "free"


async def _lookup_rw(
    *,
    email: str | None,
    vless_uuid: str | None,
    username: str | None,
) -> tuple[dict | None, dict | None]:
    """Concurrently look up Android-side (by email) and TG-side
    (by uuid → fallback username) in Remnawave.

    Returns (a_info, t_info) where each is the dict from the client or None
    on miss/error. Errors are logged at WARNING and swallowed — the merge
    must continue even if Remnawave is temporarily down.
    """
    import asyncio
    import app.api.remnawave.api as rem

    async def safe(coro):
        try:
            return await coro
        except Exception as exc:
            logger.warning("Remnawave lookup failed: %s", exc)
            return None

    a_task = safe(rem.get_user_from_email(email)) if email else _none()
    if vless_uuid:
        t_task = safe(rem.get_user_from_uuid(vless_uuid))
    elif username:
        t_task = safe(rem.get_user_from_username(username))
    else:
        t_task = _none()

    a_info, t_info = await asyncio.gather(a_task, t_task)
    return a_info, t_info


async def _none():
    return None


class MergeBlocked(Exception):
    """Raised when both sides hold an active PRO subscription — automatic
    resolution would discard a paid subscription, so the caller must surface
    a "contact support" message instead."""

    def __init__(self, details: dict[str, Any]):
        super().__init__("both_pro_support_needed")
        self.details = details


async def merge_android_and_tg(
    session,
    android_user_id: int,
    tg_user_id: int,
    tg_id: int,
) -> dict[str, Any]:
    raise NotImplementedError
