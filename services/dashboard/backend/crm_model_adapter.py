"""Convert between legacy flat CRM fields and conditions/actions JSON."""
from __future__ import annotations

import json
from typing import Any

from common_db.repo import crm_segments as seg_repo

CONDITION_SEGMENT = "segment"
CONDITION_USER_TYPE = "user_type"
CONDITION_TG_ALLOWLIST = "tg_allowlist"

ACTION_SEND_MESSAGE = "send_message"
ACTION_ATTACH_BUTTON = "attach_button"
ACTION_RW_BONUS_DAYS = "rw_bonus_days"
ACTION_RW_BONUS_TRAFFIC = "rw_bonus_traffic"
ACTION_RW_RESET_TRAFFIC = "rw_reset_traffic"
ACTION_RW_SET_STATUS = "rw_set_status"
ACTION_CREDIT_BALANCE = "credit_balance"


def _loads(raw: str | None) -> list[dict]:
    if not raw or raw in ("[]", "{}"):
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def flat_to_conditions(
    *,
    segment_type: str | None,
    segment_params: dict | str | None,
) -> list[dict]:
    if isinstance(segment_params, str):
        try:
            params = json.loads(segment_params or "{}")
        except json.JSONDecodeError:
            params = {}
    else:
        params = dict(segment_params or {})

    if not segment_type:
        return []

    user_type = params.pop("user_type", None)
    target_tg_ids = params.pop("target_tg_ids", None)

    conditions: list[dict] = [
        {
            "type": CONDITION_SEGMENT,
            "segment_id": segment_type,
            "params": params,
        }
    ]
    if user_type and user_type != seg_repo.USER_TYPE_ALL:
        conditions.append({"type": CONDITION_USER_TYPE, "value": user_type})
    if target_tg_ids:
        conditions.append(
            {"type": CONDITION_TG_ALLOWLIST, "tg_ids": list(target_tg_ids)}
        )
    return conditions


def flat_to_actions(
    *,
    message_text: str = "",
    attach_button: bool = False,
    bonus_days: int | None = None,
    bonus_traffic_gb: int | None = None,
) -> list[dict]:
    actions: list[dict] = []
    order = 1
    if bonus_days and bonus_days > 0:
        actions.append(
            {
                "type": ACTION_RW_BONUS_DAYS,
                "enabled": True,
                "order": order,
                "days": bonus_days,
            }
        )
        order += 1
    if bonus_traffic_gb and bonus_traffic_gb > 0:
        actions.append(
            {
                "type": ACTION_RW_BONUS_TRAFFIC,
                "enabled": True,
                "order": order,
                "gb": bonus_traffic_gb,
            }
        )
        order += 1
    if message_text and message_text.strip():
        actions.append(
            {
                "type": ACTION_SEND_MESSAGE,
                "enabled": True,
                "order": order,
                "text": message_text,
            }
        )
        order += 1
    if attach_button:
        actions.append(
            {
                "type": ACTION_ATTACH_BUTTON,
                "enabled": True,
                "order": order,
                "button_type": "open_bot",
            }
        )
    return actions


def get_conditions(entity: Any) -> list[dict]:
    """Read conditions from ORM row; JSON first, flat fallback."""
    stored = _loads(getattr(entity, "conditions_json", None))
    if stored:
        return stored
    return flat_to_conditions(
        segment_type=getattr(entity, "segment_type", None),
        segment_params=getattr(entity, "segment_params", "{}"),
    )


def get_actions(entity: Any) -> list[dict]:
    stored = _loads(getattr(entity, "actions_json", None))
    if stored:
        return stored
    return flat_to_actions(
        message_text=getattr(entity, "message_text", "") or "",
        attach_button=bool(getattr(entity, "attach_button", False)),
        bonus_days=getattr(entity, "bonus_days", None),
        bonus_traffic_gb=getattr(entity, "bonus_traffic_gb", None),
    )


def sync_flat_from_model(
    *,
    conditions: list[dict],
    actions: list[dict],
) -> dict[str, Any]:
    """Derive legacy flat fields from conditions/actions for transition period."""
    segment_type: str | None = None
    segment_params: dict = {}
    target_tg_ids: list[int] | None = None

    for cond in conditions:
        ctype = cond.get("type")
        if ctype == CONDITION_SEGMENT:
            segment_type = cond.get("segment_id")
            segment_params = dict(cond.get("params") or {})
        elif ctype == CONDITION_USER_TYPE:
            segment_params["user_type"] = cond.get("value", seg_repo.USER_TYPE_ALL)
        elif ctype == CONDITION_TG_ALLOWLIST:
            target_tg_ids = list(cond.get("tg_ids") or [])

    message_text = ""
    attach_button = False
    bonus_days: int | None = None
    bonus_traffic_gb: int | None = None

    for act in actions:
        if not act.get("enabled", True):
            continue
        atype = act.get("type")
        if atype == ACTION_SEND_MESSAGE:
            message_text = act.get("text") or ""
        elif atype == ACTION_ATTACH_BUTTON:
            attach_button = True
        elif atype == ACTION_RW_BONUS_DAYS:
            bonus_days = act.get("days")
        elif atype == ACTION_RW_BONUS_TRAFFIC:
            bonus_traffic_gb = act.get("gb")

    if target_tg_ids:
        segment_params["target_tg_ids"] = target_tg_ids

    return {
        "segment_type": segment_type,
        "segment_params": segment_params,
        "message_text": message_text,
        "attach_button": attach_button,
        "bonus_days": bonus_days,
        "bonus_traffic_gb": bonus_traffic_gb,
    }


def validate_conditions(conditions: list[dict]) -> None:
    segments = [c for c in conditions if c.get("type") == CONDITION_SEGMENT]
    if len(segments) != 1:
        raise ValueError("exactly one segment condition is required")


def validate_actions(actions: list[dict]) -> None:
    enabled = [a for a in actions if a.get("enabled", True)]
    if not enabled:
        raise ValueError("at least one enabled action is required")


def normalize_actions(actions: list[dict]) -> list[dict]:
    """Assign order if missing; sort rw before telegram by default."""
    rw_types = {
        ACTION_RW_BONUS_DAYS,
        ACTION_RW_BONUS_TRAFFIC,
        ACTION_RW_RESET_TRAFFIC,
        ACTION_RW_SET_STATUS,
        ACTION_CREDIT_BALANCE,
    }
    tg_types = {ACTION_SEND_MESSAGE, ACTION_ATTACH_BUTTON}

    for i, act in enumerate(actions):
        if act.get("order") is None:
            base = 10 if act.get("type") in rw_types else 100
            act["order"] = base + i

    return sorted(actions, key=lambda a: a.get("order", 999))
