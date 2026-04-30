import datetime
import logging
import uuid

from remnawave import RemnawaveSDK
from remnawave.enums import TrafficLimitStrategy, UserStatus
from remnawave.models import (
    CreateUserRequestDto,
    DeleteUserHwidDeviceRequestDto,
    DeleteUserHwidDeviceResponseDto,
    GetUserHwidDevicesResponseDto,
    UpdateUserRequestDto,
    UserResponseDto,
)

from .config import get_remnawave_token, get_remnawave_url, get_rw_free_id

logger = logging.getLogger(__name__)

_STATUS_MAP = {
    "active": UserStatus.ACTIVE,
    "disabled": UserStatus.DISABLED,
    "limited": UserStatus.LIMITED,
    "expired": UserStatus.EXPIRED,
}

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


def _normalize_device(device) -> dict:
    return {
        "hwid": device.hwid,
        "platform": getattr(device, "platform", None),
        "os_version": getattr(device, "os_version", None),
        "device_model": getattr(device, "device_model", None),
        "user_agent": getattr(device, "user_agent", None),
        "created_at": device.created_at.isoformat() if getattr(device, "created_at", None) else None,
        "updated_at": device.updated_at.isoformat() if getattr(device, "updated_at", None) else None,
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


async def create_user(
    username: str,
    days: int = 30,
    limit_gb: int = 0,
    descr: str = "created by miniapp",
    email: str | None = None,
    telegram_id: int | None = None,
    tag: str | None = None,
    squad_id: str | None = None,
    external_squad_id: str | None = None,
) -> dict | None:
    try:
        sdk = _get_sdk()

        if email is None:
            email = f"{username}@miniapp.xyz"

        new_user = CreateUserRequestDto(
            expire_at=datetime.datetime.now() + datetime.timedelta(days=days),
            username=username,
            created_at=datetime.datetime.now(),
            status=UserStatus.ACTIVE,
            vless_uuid=f"{uuid.uuid4()}",
            traffic_limit_bytes=limit_gb * 1024 * 1024 * 1024 if limit_gb > 0 else 0,
            traffic_limit_strategy=(
                TrafficLimitStrategy.MONTH if limit_gb > 0 else TrafficLimitStrategy.NO_RESET
            ),
            description=descr,
            email=email,
            active_internal_squads=[squad_id] if squad_id else [f"{get_rw_free_id()}"],
            telegram_id=telegram_id,
            external_squad_uuid=external_squad_id,
        )

        if tag:
            new_user.tag = tag

        response: UserResponseDto = await sdk.users.create_user(new_user)

        expire_ts = int(response.expire_at.timestamp()) if response.expire_at else None
        return {
            "uuid": str(response.uuid),
            "expire": expire_ts,
            "subscription_url": response.subscription_url,
            "status": "active",
            "email": response.email,
        }
    except Exception as e:
        logger.error("Remnawave create_user(%s) failed: %s", username, e)
        return None


async def update_user(
    user_uuid: str,
    username: str | None = None,
    days: int | None = None,
    limit_gb: int | None = None,
    descr: str | None = None,
    email: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    squad_id: str | None = None,
    external_squad_id: str | None = None,
) -> dict | None:
    try:
        sdk = _get_sdk()

        update_data: dict = {"uuid": uuid.UUID(user_uuid)}

        if status is not None:
            update_data["status"] = _STATUS_MAP.get(status, UserStatus.ACTIVE)
        if username:
            update_data["username"] = username
        if days:
            update_data["expire_at"] = datetime.datetime.now() + datetime.timedelta(days=days)
        if limit_gb is not None:
            update_data["traffic_limit_bytes"] = limit_gb * 1024 * 1024 * 1024 if limit_gb > 0 else 0
        if descr:
            update_data["description"] = descr
        if email:
            update_data["email"] = email
        if tag:
            update_data["tag"] = tag
        if squad_id:
            update_data["active_internal_squads"] = [squad_id]
        if external_squad_id:
            update_data["external_squad_uuid"] = external_squad_id

        request = UpdateUserRequestDto(**update_data)
        response: UserResponseDto = await sdk.users.update_user(request)

        expire_ts = int(response.expire_at.timestamp()) if response.expire_at else None
        return {
            "expire": expire_ts,
            "subscription_url": response.subscription_url,
            "status": response.status.value.lower() if response.status else None,
        }
    except Exception as e:
        logger.error("Remnawave update_user(%s) failed: %s", user_uuid, e)
        return None


async def delete_user(user_uuid: str) -> bool:
    try:
        sdk = _get_sdk()
        await sdk.users.delete_user(user_uuid)
        return True
    except Exception as e:
        logger.error("Remnawave delete_user(%s) failed: %s", user_uuid, e)
        return False


async def get_user_hwid_devices(user_uuid: str) -> list[dict]:
    try:
        sdk = _get_sdk()
        response: GetUserHwidDevicesResponseDto = await sdk.hwid.get_hwid_user(user_uuid)
        if not response or not response.devices:
            return []
        return [_normalize_device(d) for d in response.devices]
    except Exception as e:
        logger.error("Remnawave get_user_hwid_devices(%s) failed: %s", user_uuid, e)
        return []


async def get_user_devices_count(user_uuid: str) -> int:
    try:
        sdk = _get_sdk()
        response: GetUserHwidDevicesResponseDto = await sdk.hwid.get_hwid_user(user_uuid)
        if not response:
            return 0
        return int(response.total) if response.total else len(response.devices or [])
    except Exception as e:
        logger.error("Remnawave get_user_devices_count(%s) failed: %s", user_uuid, e)
        return 0


async def delete_user_hwid_device(user_uuid: str, hwid: str) -> bool:
    try:
        sdk = _get_sdk()
        request = DeleteUserHwidDeviceRequestDto(user_uuid=user_uuid, hwid=hwid)
        response: DeleteUserHwidDeviceResponseDto = await sdk.hwid.delete_hwid_to_user(request)
        return response is not None
    except Exception as e:
        logger.error("Remnawave delete_user_hwid_device(%s, %s) failed: %s", user_uuid, hwid, e)
        return False
