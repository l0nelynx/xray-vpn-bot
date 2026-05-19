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
