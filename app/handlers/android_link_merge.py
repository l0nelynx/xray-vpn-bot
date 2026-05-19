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
