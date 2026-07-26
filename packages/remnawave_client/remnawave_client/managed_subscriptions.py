"""Live view of local account-to-Remnawave subscription links."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from .api import get_user_devices_count_by_id, get_user_from_id


def _tariff(active_squads: list[str], *, free_squad_id: str, pro_squad_id: str) -> str:
    squads = {str(value).lower() for value in active_squads}
    if pro_squad_id and pro_squad_id.lower() in squads:
        return "Premium"
    if free_squad_id and free_squad_id.lower() in squads:
        return "Free"
    return "—"


def _days_left(expire_ts: int | None) -> int:
    if expire_ts is None:
        return 0
    return max(0, round((int(expire_ts) - time.time()) / 86400))


def _expire_iso(expire_ts: int | None) -> str | None:
    if expire_ts is None:
        return None
    return datetime.fromtimestamp(int(expire_ts), tz=timezone.utc).isoformat()


async def serialize_managed_subscription(
    row: Any, *, free_squad_id: str = "", pro_squad_id: str = ""
) -> dict[str, Any]:
    """Resolve one DB link without hiding it when Remnawave is unavailable."""
    rem_result, devices_result = await asyncio.gather(
        get_user_from_id(row.rw_id),
        get_user_devices_count_by_id(row.rw_id),
        return_exceptions=True,
    )
    rem_user = rem_result if isinstance(rem_result, dict) else None
    devices = devices_result if isinstance(devices_result, int) else 0
    base = {
        "id": row.id,
        "rw_id": row.rw_id,
        "label": row.label,
        "product_key": row.product_key,
        "source": row.source,
        "is_primary": row.is_primary,
    }
    if rem_user is None:
        return {
            **base,
            "tariff": "—",
            "status": "unavailable",
            "days_left": 0,
            "expire_iso": None,
            "data_limit_gb": None,
            "traffic_used_gb": 0,
            "devices_count": 0,
            "subscription_url": None,
        }

    expire = rem_user.get("expire")
    return {
        **base,
        "tariff": _tariff(
            rem_user.get("active_squads", []),
            free_squad_id=free_squad_id,
            pro_squad_id=pro_squad_id,
        ),
        "status": rem_user.get("status"),
        "days_left": _days_left(expire),
        "expire_iso": _expire_iso(expire),
        "data_limit_gb": rem_user.get("data_limit"),
        "traffic_used_gb": rem_user.get("traffic_used", 0),
        "devices_count": devices,
        "subscription_url": rem_user.get("subscription_url"),
    }


__all__ = ["serialize_managed_subscription"]
