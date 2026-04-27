import logging

from remnawave import RemnawaveSDK
from remnawave.models import UserResponseDto

from .config import get_remnawave_url, get_remnawave_token

logger = logging.getLogger(__name__)

_sdk: RemnawaveSDK | None = None


def _get_sdk() -> RemnawaveSDK:
    global _sdk
    if _sdk is None:
        _sdk = RemnawaveSDK(
            base_url=get_remnawave_url(),
            token=get_remnawave_token(),
        )
    return _sdk


def _normalize_user(user: UserResponseDto) -> dict:
    expire_ts = int(user.expire_at.timestamp()) if user.expire_at else None
    active_squads = []
    raw_squads = getattr(user, "active_internal_squads", None)
    if raw_squads:
        for squad in raw_squads:
            if isinstance(squad, dict):
                active_squads.append(str(squad.get("uuid") or squad.get("id") or ""))
            else:
                uuid_val = getattr(squad, "uuid", None) or getattr(squad, "id", None)
                if uuid_val:
                    active_squads.append(str(uuid_val))
    return {
        "uuid": str(user.uuid),
        "expire": expire_ts,
        "subscription_url": user.subscription_url,
        "status": user.status.value.lower() if user.status else None,
        "data_limit": (
            max(1, user.traffic_limit_bytes // (1024 ** 3))
            if user.traffic_limit_bytes else None
        ),
        "traffic_used": (
            user.used_traffic_bytes // (1024 ** 3)
            if user.used_traffic_bytes else 0
        ),
        "active_squads": active_squads,
    }


async def get_user_from_username(username: str) -> dict | None:
    try:
        sdk = _get_sdk()
        response = await sdk.users.get_user_by_username(username)
        if not response:
            return None
        return _normalize_user(response)
    except Exception as e:
        logger.error("Remnawave get_user_from_username(%s) failed: %s", username, e)
        return None


async def get_user_devices_count(user_uuid: str) -> int:
    try:
        sdk = _get_sdk()
        response = await sdk.users.get_user_hwid_devices(user_uuid)
        if not response:
            return 0
        devices = getattr(response, "devices", None)
        if devices is None and hasattr(response, "root"):
            devices = response.root
        return len(devices) if devices else 0
    except Exception as e:
        logger.error("Remnawave get_user_hwid_devices(%s) failed: %s", user_uuid, e)
        return 0
