"""Tests for Remnawave client user normalization."""

from __future__ import annotations

from types import SimpleNamespace

from remnawave_client.client import _extract_rw_id, _normalize_user


def test_extract_rw_id_from_dto() -> None:
    user = SimpleNamespace(id=12345, uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    assert _extract_rw_id(user) == 12345


def test_extract_rw_id_from_dict() -> None:
    assert _extract_rw_id({"id": 99}) == 99
    assert _extract_rw_id({"id": None}) is None
    assert _extract_rw_id({}) is None


def test_normalize_user_includes_rw_id() -> None:
    import datetime

    user = SimpleNamespace(
        uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        id=777,
        expire_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        subscription_url="https://example.com/sub",
        status=SimpleNamespace(value="ACTIVE"),
        traffic_limit_bytes=0,
        used_traffic_bytes=0,
        active_internal_squads=None,
        email="u@example.com",
        telegram_id=123,
        username="user01_42",
        description="provisioning:tx-1",
        tag="PAID",
    )
    normalized = _normalize_user(user)
    assert normalized["uuid"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert normalized["rw_id"] == 777
    assert normalized["username"] == "user01_42"
    assert normalized["description"] == "provisioning:tx-1"
    assert normalized["tag"] == "PAID"
