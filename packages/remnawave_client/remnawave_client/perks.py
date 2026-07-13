"""CRM perk application — bonus days / traffic via Remnawave.

Side-effect-free regarding local DB; callers record audit rows separately.
"""

from __future__ import annotations

import logging
from typing import Optional

from .client import RemnawaveClient, get_default_client
from .operations import apply_extend, apply_update
from .segmentation import bonus_traffic_limit_gb

logger = logging.getLogger(__name__)


def _client(client: Optional[RemnawaveClient]) -> RemnawaveClient:
    return client or get_default_client()


async def apply_crm_bonus_days(
    *,
    user_uuid: str,
    username: str,
    bonus_days: int,
    crm_user: dict,
    client: Optional[RemnawaveClient] = None,
) -> bool:
    """Add ``bonus_days`` to an existing subscription."""
    if bonus_days <= 0:
        return True

    status = (crm_user.get("status") or "").lower()
    rw = _client(client)

    try:
        if status == "active":
            current_days = int(crm_user.get("days_left") or 0)
            result = await apply_extend(
                user_uuid=user_uuid,
                username=username,
                days=bonus_days,
                current_days_left=current_days,
                description="CRM bonus days",
                client=rw,
            )
        else:
            limit_gb = 0
            limit_bytes = int(crm_user.get("traffic_limit_bytes") or 0)
            if limit_bytes > 0:
                limit_gb = max(1, limit_bytes // (1024 ** 3))
            if status == "limited":
                await rw.reset_user_traffic(user_uuid)
            result = await apply_update(
                user_uuid=user_uuid,
                username=username,
                days=bonus_days,
                limit_gb=limit_gb,
                status="active",
                description="CRM bonus days",
                client=rw,
            )
        return result is not None
    except Exception as exc:
        logger.error("apply_crm_bonus_days uuid=%s failed: %s", user_uuid, exc)
        return False


async def apply_crm_bonus_traffic(
    *,
    user_uuid: str,
    username: str,
    bonus_gb: int,
    crm_user: dict,
    client: Optional[RemnawaveClient] = None,
) -> bool:
    """Add ``bonus_gb`` to the user's traffic limit."""
    if bonus_gb <= 0:
        return True

    status = (crm_user.get("status") or "").lower()
    rw = _client(client)
    current_limit = int(crm_user.get("traffic_limit_bytes") or 0)
    new_limit_gb = bonus_traffic_limit_gb(current_limit, bonus_gb)

    try:
        if status == "limited":
            await rw.reset_user_traffic(user_uuid)
        days = max(1, int(crm_user.get("days_left") or 1))
        result = await apply_update(
            user_uuid=user_uuid,
            username=username,
            days=days,
            limit_gb=new_limit_gb,
            status="active",
            description="CRM bonus traffic",
            client=rw,
        )
        return result is not None
    except Exception as exc:
        logger.error("apply_crm_bonus_traffic uuid=%s failed: %s", user_uuid, exc)
        return False
