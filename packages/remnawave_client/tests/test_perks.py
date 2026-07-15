"""Tests for CRM perk application."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from remnawave_client.perks import apply_crm_bonus_days, is_free_tier_user


def test_is_free_tier_user_with_traffic_limit() -> None:
    assert is_free_tier_user({"traffic_limit_bytes": 10 * 1024 ** 3}) is True
    assert is_free_tier_user({"traffic_limit_bytes": 0}) is False


def test_apply_crm_bonus_days_resets_traffic_for_active_free_user() -> None:
    async def go() -> None:
        rw = MagicMock()
        rw.reset_user_traffic = AsyncMock(return_value=True)

        with patch(
            "remnawave_client.perks.apply_extend",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as extend:
            ok = await apply_crm_bonus_days(
                user_uuid="uuid-1",
                username="alice",
                bonus_days=3,
                crm_user={
                    "status": "active",
                    "days_left": 5,
                    "traffic_limit_bytes": 5 * 1024 ** 3,
                },
                client=rw,
            )

        assert ok is True
        rw.reset_user_traffic.assert_awaited_once_with("uuid-1")
        extend.assert_awaited_once()

    asyncio.run(go())


def test_apply_crm_bonus_days_no_reset_for_unlimited_paid() -> None:
    async def go() -> None:
        rw = MagicMock()
        rw.reset_user_traffic = AsyncMock(return_value=True)

        with patch(
            "remnawave_client.perks.apply_extend",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ):
            ok = await apply_crm_bonus_days(
                user_uuid="uuid-2",
                username="bob",
                bonus_days=3,
                crm_user={
                    "status": "active",
                    "days_left": 30,
                    "traffic_limit_bytes": 0,
                },
                client=rw,
            )

        assert ok is True
        rw.reset_user_traffic.assert_not_awaited()

    asyncio.run(go())
