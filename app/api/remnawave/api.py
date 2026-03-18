import logging
import uuid
import datetime

from app.settings import secrets
from remnawave.enums import TrafficLimitStrategy, UserStatus
from remnawave import RemnawaveSDK
from remnawave.models import (
    UsersResponseDto,
    UserResponseDto,
    CreateUserRequestDto,
    UpdateUserRequestDto,
    GetUserHwidDevicesResponseDto,
    DeleteUserHwidDeviceResponseDto,
    DeleteUserHwidDeviceRequestDto,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Singleton SDK instance — reuses HTTP connection pool across all calls
# ============================================================================

_sdk: RemnawaveSDK | None = None


def _get_sdk() -> RemnawaveSDK:
    global _sdk
    if _sdk is None:
        _sdk = RemnawaveSDK(
            base_url=secrets.get('remnawave_url'),
            token=secrets.get('remnawave_token'),
        )
    return _sdk


# ============================================================================
# Helper: normalize UserResponseDto → dict
# ============================================================================

def _normalize_user(user: UserResponseDto) -> dict:
    """Convert SDK response to a normalized dict compatible with the rest of the codebase."""
    expire_timestamp = int(user.expire_at.timestamp()) if user.expire_at else None
    return {
        "uuid": user.uuid,
        "expire": expire_timestamp,
        "subscription_url": user.subscription_url,
        "status": user.status.value.lower(),
        "data_limit": (
            max(1, user.traffic_limit_bytes // (1024 * 1024 * 1024))
            if user.traffic_limit_bytes else None
        ),
        "traffic_used": (
            user.used_traffic_bytes // (1024 * 1024 * 1024)
            if user.used_traffic_bytes else 0
        ),
    }


# ============================================================================
# Public API
# ============================================================================

async def get_all_users():
    """Получает список всех пользователей из RemnaWave"""
    sdk = _get_sdk()
    response: UsersResponseDto = await sdk.users.get_all_users_v2()
    logger.info("Total users: %s", response.total)
    return response


async def get_user_from_username(username: str) -> dict | None:
    try:
        sdk = _get_sdk()
        response: UserResponseDto = await sdk.users.get_user_by_username(username)
        if not response:
            return None
        return _normalize_user(response)
    except Exception as e:
        logger.error("Error getting user %s from RemnaWave: %s", username, e)
        return None


async def get_user_from_email(email: str) -> dict | None:
    try:
        sdk = _get_sdk()
        response = await sdk.users.get_users_by_email(email)
        if not response or not response.root:
            return None
        return _normalize_user(response.root[0])
    except Exception as e:
        logger.error("Error getting user by email %s from RemnaWave: %s", email, e)
        return None


async def create_user(
    username: str,
    days: int = 30,
    limit_gb: int = 0,
    descr: str = "created by backend v2",
    email: str = None,
    telegram_id: int = None,
    tag: str = None,
    squad_id: str = None,
    external_squad_id: str = None,
) -> dict | None:
    """Создает нового пользователя в RemnaWave."""
    try:
        sdk = _get_sdk()

        if email is None:
            email = f"{username}@bot.local"

        new_user = CreateUserRequestDto(
            expire_at=datetime.datetime.now() + datetime.timedelta(days=days),
            username=username,
            created_at=datetime.datetime.now(),
            status=UserStatus.ACTIVE,
            vless_uuid=f"{uuid.uuid4()}",
            traffic_limit_bytes=limit_gb * 1024 * 1024 * 1024 if limit_gb > 0 else 0,
            traffic_limit_strategy=TrafficLimitStrategy.MONTH if limit_gb > 0 else TrafficLimitStrategy.NO_RESET,
            description=descr,
            email=email,
            active_internal_squads=[squad_id] if squad_id else [f"{secrets.get('rw_free_id')}"],
            telegram_id=telegram_id,
            external_squad_uuid=external_squad_id,
        )

        if tag:
            new_user.tag = tag

        response: UserResponseDto = await sdk.users.create_user(new_user)

        expire_timestamp = int(response.expire_at.timestamp())
        return {
            "uuid": response.uuid,
            "expire": expire_timestamp,
            "subscription_url": response.subscription_url,
            "status": "active",
            "email": response.email,
        }
    except Exception as e:
        logger.error("Error creating user %s in RemnaWave: %s", username, e)
        return None


async def update_user(
    user_uuid: str,
    username: str = None,
    days: int = None,
    limit_gb: int = None,
    descr: str = None,
    email: str = None,
    tag: str = None,
    status: str = None,
    squad_id: str = None,
    external_squad_id: str = None,
) -> dict | None:
    """Обновляет информацию пользователя в RemnaWave."""
    try:
        sdk = _get_sdk()

        update_data = {
            "uuid": uuid.UUID(user_uuid),
            "status": UserStatus.ACTIVE if status != "disabled" else UserStatus.DISABLED,
        }

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

        user = UpdateUserRequestDto(**update_data)
        response: UserResponseDto = await sdk.users.update_user(user)

        expire_timestamp = int(response.expire_at.timestamp())
        return {
            "expire": expire_timestamp,
            "subscription_url": response.subscription_url,
            "status": response.status.value.lower(),
        }
    except Exception as e:
        logger.error("Error updating user %s in RemnaWave: %s", user_uuid, e)
        return None


async def reset_user_traffic(user_uuid: str) -> bool:
    """Сбрасывает использованный трафик пользователя."""
    try:
        sdk = _get_sdk()
        await sdk.users.reset_user_traffic(user_uuid)
        return True
    except Exception as e:
        logger.error("Error resetting traffic for user %s: %s", user_uuid, e)
        return False


async def delete_user(user_uuid: str) -> bool:
    """Удаляет пользователя из RemnaWave."""
    try:
        sdk = _get_sdk()
        await sdk.users.delete_user(user_uuid)
        return True
    except Exception as e:
        logger.error("Error deleting user %s from RemnaWave: %s", user_uuid, e)
        return False


async def get_user_subscription_link(user_uuid: str) -> str | None:
    """Получает ссылку на подписку для пользователя."""
    try:
        sdk = _get_sdk()
        response: UserResponseDto = await sdk.users.get_user_by_uuid(user_uuid)
        return response.subscription_url if response else None
    except Exception as e:
        logger.error("Error getting subscription link for user %s: %s", user_uuid, e)
        return None


async def get_user_hwid_devices(user_uuid: str) -> GetUserHwidDevicesResponseDto | None:
    """Получает список HWID-устройств пользователя."""
    try:
        sdk = _get_sdk()
        response: GetUserHwidDevicesResponseDto = await sdk.hwid.get_hwid_user(user_uuid)
        return response
    except Exception as e:
        logger.error("Error getting HWID devices for user %s: %s", user_uuid, e)
        return None


async def delete_user_hwid_device(user_uuid: str, hwid: str) -> DeleteUserHwidDeviceResponseDto | None:
    """Удаляет определённое HWID-устройство пользователя."""
    try:
        sdk = _get_sdk()
        request = DeleteUserHwidDeviceRequestDto(user_uuid=user_uuid, hwid=hwid)
        response: DeleteUserHwidDeviceResponseDto = await sdk.hwid.delete_hwid_to_user(request)
        return response
    except Exception as e:
        logger.error("Error deleting HWID device %s for user %s: %s", hwid, user_uuid, e)
        return None
