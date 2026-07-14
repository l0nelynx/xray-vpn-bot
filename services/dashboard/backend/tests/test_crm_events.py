"""Tests for CRM events repeat policy and schedule helpers."""
from __future__ import annotations

from datetime import datetime

from common_db.repo.crm_events import (
    compute_next_run_at,
    filter_tg_ids_by_repeat_policy,
)


def test_filter_repeat_always() -> None:
    tg_ids = [1, 2, 3]
    assert filter_tg_ids_by_repeat_policy(
        tg_ids,
        repeat_policy="always",
        repeat_cooldown_days=7,
        ever_sent={2},
        recent_sent={3},
    ) == [1, 2, 3]


def test_filter_repeat_once() -> None:
    assert filter_tg_ids_by_repeat_policy(
        [1, 2, 3],
        repeat_policy="once",
        repeat_cooldown_days=7,
        ever_sent={2},
        recent_sent=set(),
    ) == [1, 3]


def test_filter_repeat_cooldown() -> None:
    assert filter_tg_ids_by_repeat_policy(
        [1, 2, 3],
        repeat_policy="cooldown",
        repeat_cooldown_days=7,
        ever_sent=set(),
        recent_sent={2},
    ) == [1, 3]


def test_compute_next_run_at_daily() -> None:
    base = datetime(2026, 7, 14, 10, 30, 0)
    nxt = compute_next_run_at(
        run_at_time="01:00",
        frequency="daily",
        weekday=None,
        from_dt=base,
    )
    assert nxt.startswith("2026-07-15T01:00:00")


def test_compute_next_run_at_weekly() -> None:
    # 2026-07-14 is Tuesday (weekday=1)
    base = datetime(2026, 7, 14, 10, 0, 0)
    nxt = compute_next_run_at(
        run_at_time="09:00",
        frequency="weekly",
        weekday=0,  # Monday
        from_dt=base,
    )
    assert nxt.startswith("2026-07-20T09:00:00")
