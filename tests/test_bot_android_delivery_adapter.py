"""Regression tests for the seller-bot Android delivery adapter."""

from __future__ import annotations

import asyncio

import pytest


def test_android_delivery_adapter_forwards_target_rw_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.handlers import android_delivery

    received: dict[str, object] = {}

    async def fake_deliver(**kwargs: object) -> dict[str, str]:
        received.update(kwargs)
        return {"status": "success"}

    monkeypatch.setattr(android_delivery, "_deliver", fake_deliver)

    result = asyncio.run(
        android_delivery.deliver_android_paid(
            transaction_id="tx-1",
            android_user_id=42,
            email=None,
            days=30,
            tariff_slug="sid:1:esid:2",
            delivery_target={"internal_squad_ids": [1]},
            target_rw_id=1031,
        )
    )

    assert result == {"status": "success"}
    assert received["target_rw_id"] == 1031
    assert received["session_factory"] is android_delivery.async_session
    assert received["notifier"] is android_delivery.notify_log
