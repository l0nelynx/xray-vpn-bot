"""CRM user segmentation helpers over Remnawave user DTOs.

Pure functions — no DB, no Telegram. Dashboard CRM joins these dicts with
local ``users`` rows by ``vless_uuid``.
"""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Any

from remnawave.models import UserResponseDto

SEGMENT_NEVER_CONNECTED = "never_connected"
SEGMENT_ALL_USERS = "all_users"
SEGMENT_EXPIRED = "expired"
SEGMENT_LIMITED = "limited"
SEGMENT_TRAFFIC_LOW = "traffic_low"
SEGMENT_EXPIRING_SOON = "expiring_soon"
SEGMENT_UNPAID_INVOICE = "unpaid_invoice"
SEGMENT_TORRENT = "torrent"
SEGMENT_DEVICE_LIMIT = "device_limit"

SEGMENT_IDS = frozenset({
    SEGMENT_NEVER_CONNECTED,
    SEGMENT_ALL_USERS,
    SEGMENT_EXPIRED,
    SEGMENT_LIMITED,
    SEGMENT_TRAFFIC_LOW,
    SEGMENT_EXPIRING_SOON,
    SEGMENT_UNPAID_INVOICE,
    SEGMENT_TORRENT,
    SEGMENT_DEVICE_LIMIT,
})

DEFAULT_DAYS_THRESHOLD = 3
DEFAULT_TRAFFIC_THRESHOLD = 0.8
DEFAULT_INVOICE_MAX_AGE_HOURS = 48
DEFAULT_TORRENT_DAYS = 7

PREVIEW_LIMIT = 500


def _dt_to_ts(value: datetime | None) -> int | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp())


def _get_attr(obj: Any, *names: str) -> Any:
    for name in names:
        if isinstance(obj, dict):
            if name in obj:
                return obj[name]
            # camelCase alias for dict payloads
            parts = name.split("_")
            camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
            if camel in obj:
                return obj[camel]
        else:
            val = getattr(obj, name, None)
            if val is not None:
                return val
    return None


def _status_value(user: Any) -> str | None:
    """Normalize Remnawave ``UserStatus`` (StrEnum, e.g. ``LIMITED``) to lowercase str."""
    raw = _get_attr(user, "status")
    if raw is None:
        return None
    if hasattr(raw, "value"):
        return str(raw.value).lower()
    return str(raw).lower()


def _first_connected_at(user: Any) -> Any:
    """Read firstConnectedAt from SDK v2.8+ ``userTraffic`` or legacy top-level fields."""
    val = _get_attr(user, "first_connected_at", "firstConnectedAt", "first_connected")
    if val is not None:
        return val
    traffic = _get_attr(user, "user_traffic", "userTraffic")
    if traffic is not None:
        return _get_attr(traffic, "first_connected_at", "firstConnectedAt")
    return None


def normalize_user_for_crm(user: UserResponseDto | dict) -> dict:
    """Normalized Remnawave user view for CRM segmentation."""
    uuid = _get_attr(user, "uuid")
    expire_at = _get_attr(user, "expire_at", "expireAt")
    if isinstance(expire_at, str):
        try:
            expire_at = datetime.fromisoformat(expire_at.replace("Z", "+00:00"))
        except ValueError:
            expire_at = None

    expire_ts = _dt_to_ts(expire_at) if isinstance(expire_at, datetime) else None
    days_left = 0
    if expire_ts is not None:
        days_left = max(0, round((expire_ts - time.time()) / 86400))

    used_bytes = int(_get_attr(user, "used_traffic_bytes", "usedTrafficBytes") or 0)
    limit_bytes = int(_get_attr(user, "traffic_limit_bytes", "trafficLimitBytes") or 0)

    first_connected = _first_connected_at(user)
    hwid_limit = _get_attr(user, "hwid_device_limit", "hwidDeviceLimit")

    hwid_devices = _get_attr(user, "hwid_devices", "hwidDevices") or []
    device_count: int | None = None
    if hwid_devices:
        device_count = len(hwid_devices)
    elif _get_attr(user, "hwid_device_count", "hwidDeviceCount") is not None:
        device_count = int(_get_attr(user, "hwid_device_count", "hwidDeviceCount"))

    telegram_id = _get_attr(user, "telegram_id", "telegramId")
    if telegram_id is not None:
        try:
            telegram_id = int(telegram_id)
        except (TypeError, ValueError):
            telegram_id = None

    status = _status_value(user)

    traffic_ratio: float | None = None
    if limit_bytes > 0:
        traffic_ratio = used_bytes / limit_bytes

    rw_id_raw = _get_attr(user, "id")
    rw_id: int | None = None
    if rw_id_raw is not None:
        try:
            rw_id = int(rw_id_raw)
        except (TypeError, ValueError):
            rw_id = None

    return {
        "uuid": str(uuid) if uuid else None,
        "rw_id": rw_id,
        "status": status,
        "expire_ts": expire_ts,
        "days_left": days_left,
        "used_traffic_bytes": used_bytes,
        "traffic_limit_bytes": limit_bytes,
        "traffic_ratio": traffic_ratio,
        "first_connected_at": first_connected,
        "hwid_device_limit": int(hwid_limit) if hwid_limit is not None else None,
        "device_count": device_count,
        "telegram_id": telegram_id,
        "username": _get_attr(user, "username"),
        "email": _get_attr(user, "email"),
    }


def matches_rw_segment(
    crm_user: dict,
    segment_id: str,
    *,
    days_threshold: int = DEFAULT_DAYS_THRESHOLD,
    traffic_threshold: float = DEFAULT_TRAFFIC_THRESHOLD,
    torrent_uuids: set[str] | None = None,
) -> bool:
    """Return True when a normalized CRM user matches a Remnawave-backed segment."""
    if segment_id not in SEGMENT_IDS or segment_id in (
        SEGMENT_UNPAID_INVOICE,
        SEGMENT_TORRENT,
    ):
        return False

    status = crm_user.get("status")
    uuid = crm_user.get("uuid")

    if segment_id == SEGMENT_NEVER_CONNECTED:
        return crm_user.get("first_connected_at") is None

    if segment_id == SEGMENT_EXPIRED:
        return status == "expired"

    if segment_id == SEGMENT_LIMITED:
        return status == "limited"

    if segment_id == SEGMENT_TRAFFIC_LOW:
        ratio = crm_user.get("traffic_ratio")
        limit = crm_user.get("traffic_limit_bytes") or 0
        return limit > 0 and ratio is not None and ratio >= traffic_threshold

    if segment_id == SEGMENT_EXPIRING_SOON:
        if status not in ("active", "limited"):
            return False
        days_left = crm_user.get("days_left")
        return days_left is not None and days_left <= days_threshold

    if segment_id == SEGMENT_DEVICE_LIMIT:
        limit = crm_user.get("hwid_device_limit")
        count = crm_user.get("device_count")
        if limit is None or count is None or limit <= 0:
            return False
        return count >= limit

    if segment_id == SEGMENT_TORRENT:
        return bool(uuid and torrent_uuids and uuid in torrent_uuids)

    return False


def segment_meta(crm_user: dict) -> dict:
    """Compact metrics for CRM scan preview rows."""
    meta: dict[str, Any] = {}
    if crm_user.get("status"):
        meta["status"] = crm_user["status"]
    if crm_user.get("days_left") is not None:
        meta["days_left"] = crm_user["days_left"]
    if crm_user.get("traffic_ratio") is not None:
        meta["traffic_percent"] = round(crm_user["traffic_ratio"] * 100, 1)
    if crm_user.get("device_count") is not None:
        meta["devices"] = crm_user["device_count"]
    if crm_user.get("hwid_device_limit") is not None:
        meta["device_limit"] = crm_user["hwid_device_limit"]
    if crm_user.get("first_connected_at") is None:
        meta["never_connected"] = True
    return meta


def bonus_traffic_limit_gb(
    current_limit_bytes: int,
    bonus_gb: int,
) -> int:
    """Compute new traffic limit in GB after adding bonus_gb."""
    if bonus_gb <= 0:
        return max(0, math.ceil(current_limit_bytes / (1024 ** 3)))
    total_bytes = current_limit_bytes + bonus_gb * (1024 ** 3)
    return max(1, math.ceil(total_bytes / (1024 ** 3)))
