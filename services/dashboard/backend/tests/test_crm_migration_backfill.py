"""Tests for flat → conditions/actions backfill helpers."""
from __future__ import annotations

from dashboard.backend.crm_model_adapter import (
    flat_to_actions,
    flat_to_conditions,
    get_actions,
    get_conditions,
    sync_flat_from_model,
)


def test_flat_to_conditions_with_allowlist() -> None:
    conditions = flat_to_conditions(
        segment_type="limited",
        segment_params={
            "days_threshold": 3,
            "user_type": "free",
            "target_tg_ids": [101, 102],
        },
    )
    types = [c["type"] for c in conditions]
    assert types == ["segment", "user_type", "tg_allowlist"]
    assert conditions[0]["segment_id"] == "limited"
    assert conditions[0]["params"] == {"days_threshold": 3}
    assert conditions[2]["tg_ids"] == [101, 102]


def test_flat_to_actions_message_optional_combo() -> None:
    actions = flat_to_actions(
        message_text="",
        attach_button=False,
        bonus_days=5,
        bonus_traffic_gb=None,
    )
    assert len(actions) == 1
    assert actions[0]["type"] == "rw_bonus_days"
    assert actions[0]["days"] == 5


def test_sync_flat_from_model_roundtrip() -> None:
    conditions = [
        {"type": "segment", "segment_id": "expiring_soon", "params": {"days_threshold": 2}},
        {"type": "user_type", "value": "paid_vip"},
    ]
    actions = [
        {"type": "rw_bonus_days", "enabled": True, "days": 7},
        {"type": "send_message", "enabled": True, "text": "Hi"},
        {"type": "attach_button", "enabled": True, "button_type": "open_bot"},
    ]
    flat = sync_flat_from_model(conditions=conditions, actions=actions)
    assert flat["segment_type"] == "expiring_soon"
    assert flat["segment_params"]["user_type"] == "paid_vip"
    assert flat["bonus_days"] == 7
    assert flat["message_text"] == "Hi"
    assert flat["attach_button"] is True


class _Entity:
    conditions_json = None
    actions_json = None
    segment_type = "limited"
    segment_params = '{"days_threshold": 3}'
    message_text = "legacy"
    attach_button = True
    bonus_days = 2
    bonus_traffic_gb = None


def test_get_conditions_json_priority() -> None:
    entity = _Entity()
    entity.conditions_json = '[{"type": "segment", "segment_id": "all_users", "params": {}}]'
    assert get_conditions(entity)[0]["segment_id"] == "all_users"


def test_get_actions_flat_fallback() -> None:
    entity = _Entity()
    actions = get_actions(entity)
    types = [a["type"] for a in actions if a.get("enabled")]
    assert "send_message" in types
    assert "attach_button" in types
    assert "rw_bonus_days" in types
