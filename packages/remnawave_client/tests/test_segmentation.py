"""Tests for CRM segmentation helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from remnawave_client.segmentation import (
    SEGMENT_EXPIRED,
    SEGMENT_EXPIRING_SOON,
    SEGMENT_LIMITED,
    SEGMENT_NEVER_CONNECTED,
    SEGMENT_TRAFFIC_LOW,
    bonus_traffic_limit_gb,
    matches_rw_segment,
    normalize_user_for_crm,
)


def _crm_user(**overrides) -> dict:
    base = {
        "rw_id": 42,
        "status": "active",
        "expire_ts": int((datetime.now(timezone.utc) + timedelta(days=10)).timestamp()),
        "days_left": 10,
        "used_traffic_bytes": 5 * 1024 ** 3,
        "traffic_limit_bytes": 10 * 1024 ** 3,
        "traffic_ratio": 0.5,
        "first_connected_at": datetime.now(timezone.utc).isoformat(),
        "hwid_device_limit": 3,
        "device_count": 1,
        "telegram_id": 123,
        "username": "alice",
        "email": "alice@bot.local",
    }
    base.update(overrides)
    return base


def test_normalize_user_for_crm_from_dict() -> None:
    expire = datetime.now(timezone.utc) + timedelta(days=5)
    raw = {
        "status": "active",
        "expireAt": expire.isoformat(),
        "usedTrafficBytes": 8 * 1024 ** 3,
        "trafficLimitBytes": 10 * 1024 ** 3,
        "firstConnectedAt": None,
        "hwidDeviceLimit": 2,
        "hwidDevices": [{"hwid": "a"}],
        "telegramId": 42,
        "username": "bob",
        "id": 9001,
    }
    out = normalize_user_for_crm(raw)
    assert out["rw_id"] == 9001
    assert out["status"] == "active"
    assert out["days_left"] == 5
    assert out["traffic_ratio"] == 0.8
    assert out["first_connected_at"] is None
    assert out["device_count"] == 1
    assert out["hwid_device_limit"] == 2
    assert out["telegram_id"] == 42


def test_matches_never_connected() -> None:
    assert matches_rw_segment(
        _crm_user(first_connected_at=None), SEGMENT_NEVER_CONNECTED
    )
    assert not matches_rw_segment(
        _crm_user(first_connected_at="2026-01-01T00:00:00Z"),
        SEGMENT_NEVER_CONNECTED,
    )


def test_matches_expired_and_limited() -> None:
    assert matches_rw_segment(_crm_user(status="expired"), SEGMENT_EXPIRED)
    assert matches_rw_segment(_crm_user(status="limited"), SEGMENT_LIMITED)
    assert not matches_rw_segment(_crm_user(status="active"), SEGMENT_EXPIRED)


def test_matches_traffic_low() -> None:
    assert matches_rw_segment(
        _crm_user(traffic_ratio=0.85, used_traffic_bytes=85, traffic_limit_bytes=100),
        SEGMENT_TRAFFIC_LOW,
        traffic_threshold=0.8,
    )
    assert not matches_rw_segment(
        _crm_user(traffic_ratio=0.5, used_traffic_bytes=5, traffic_limit_bytes=10),
        SEGMENT_TRAFFIC_LOW,
        traffic_threshold=0.8,
    )


def test_matches_expiring_soon() -> None:
    assert matches_rw_segment(
        _crm_user(days_left=2, status="active"),
        SEGMENT_EXPIRING_SOON,
        days_threshold=3,
    )
    assert not matches_rw_segment(
        _crm_user(days_left=10, status="active"),
        SEGMENT_EXPIRING_SOON,
        days_threshold=3,
    )


def test_bonus_traffic_limit_gb() -> None:
    current = 10 * 1024 ** 3
    assert bonus_traffic_limit_gb(current, 5) == 15


def test_normalize_status_from_sdk_strenum() -> None:
    """SDK UserStatus is StrEnum with uppercase values (LIMITED, ACTIVE, ...)."""
    from enum import StrEnum

    class UserStatus(StrEnum):
        LIMITED = "LIMITED"
        ACTIVE = "ACTIVE"

    expire = datetime.now(timezone.utc) + timedelta(days=5)

    class FakeUser:
        id = 11
        status = UserStatus.LIMITED
        expire_at = expire
        used_traffic_bytes = 0
        traffic_limit_bytes = 10 * 1024 ** 3
        telegram_id = 42
        username = "limited_user"

    out = normalize_user_for_crm(FakeUser())
    assert out["status"] == "limited"
    assert matches_rw_segment(out, SEGMENT_LIMITED)
    assert not matches_rw_segment(out, SEGMENT_EXPIRED)


def test_normalize_first_connected_from_user_traffic() -> None:
    """SDK 2.8 nests firstConnectedAt under userTraffic, not on the user root."""
    from enum import StrEnum

    class UserStatus(StrEnum):
        ACTIVE = "ACTIVE"

    connected = datetime.now(timezone.utc)
    expire = connected + timedelta(days=30)

    class FakeTraffic:
        first_connected_at = connected

    class FakeUser:
        id = 12
        status = UserStatus.ACTIVE
        expire_at = expire
        used_traffic_bytes = 0
        traffic_limit_bytes = 0
        user_traffic = FakeTraffic()
        telegram_id = 1
        username = "connected"

    out = normalize_user_for_crm(FakeUser())
    assert out["first_connected_at"] == connected
    assert not matches_rw_segment(out, SEGMENT_NEVER_CONNECTED)
