import datetime
import logging
import uuid as _uuid
from typing import Optional

from remnawave import RemnawaveSDK
from remnawave.enums import TrafficLimitStrategy, UserStatus
from remnawave.models import (
    CreateUserRequestDto,
    DeleteUserHwidDeviceRequestDto,
    DeleteUserHwidDeviceResponseDto,
    GetUserHwidDevicesResponseDto,
    UpdateUserRequestDto,
    UserResponseDto,
    UsersResponseDto,
)

logger = logging.getLogger(__name__)


_STATUS_MAP = {
    "active": UserStatus.ACTIVE,
    "disabled": UserStatus.DISABLED,
    "limited": UserStatus.LIMITED,
    "expired": UserStatus.EXPIRED,
}


def _normalize_user(user: UserResponseDto) -> dict:
    """SDK user DTO -> normalized dict shared across consumers.

    Superset of fields used by app/miniapp. Callers may ignore extra keys.
    """
    expire_ts = int(user.expire_at.timestamp()) if user.expire_at else None

    active_squads: list[str] = []
    raw_squads = getattr(user, "active_internal_squads", None)
    if raw_squads:
        for squad in raw_squads:
            if isinstance(squad, dict):
                value = squad.get("uuid") or squad.get("id")
            else:
                value = getattr(squad, "uuid", None) or getattr(squad, "id", None)
            if value:
                active_squads.append(str(value))

    return {
        "uuid": str(user.uuid) if user.uuid else None,
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
        "email": getattr(user, "email", None),
    }


class RemnawaveClient:
    """Async wrapper over RemnawaveSDK.

    Reuses a single SDK instance per (base_url, token) so the underlying HTTP
    connection pool is shared. Construct directly or use module-level
    configure()/get_default_client() helpers.
    """

    _instances: dict[tuple[str, str], "RemnawaveClient"] = {}

    def __init__(self, base_url: str, token: str, free_squad_id: Optional[str] = None) -> None:
        self.base_url = base_url
        self.token = token
        self.free_squad_id = free_squad_id
        self._sdk: RemnawaveSDK | None = None

    @classmethod
    def get(
        cls,
        base_url: str,
        token: str,
        free_squad_id: Optional[str] = None,
    ) -> "RemnawaveClient":
        key = (base_url, token)
        inst = cls._instances.get(key)
        if inst is None:
            inst = cls(base_url, token, free_squad_id=free_squad_id)
            cls._instances[key] = inst
        elif free_squad_id and not inst.free_squad_id:
            inst.free_squad_id = free_squad_id
        return inst

    @property
    def sdk(self) -> RemnawaveSDK:
        if self._sdk is None:
            self._sdk = RemnawaveSDK(base_url=self.base_url, token=self.token)
        return self._sdk

    # ----- read -----

    async def get_all_users(self) -> UsersResponseDto:
        response: UsersResponseDto = await self.sdk.users.get_all_users_v2()
        logger.info("Remnawave total users: %s", response.total)
        return response

    async def get_user_by_username(self, username: str) -> dict | None:
        try:
            response = await self.sdk.users.get_user_by_username(username)
            if not response:
                return None
            return _normalize_user(response)
        except Exception as e:
            logger.error("Remnawave get_user_by_username(%s) failed: %s", username, e)
            return None

    async def get_user_by_email(self, email: str) -> dict | None:
        try:
            response = await self.sdk.users.get_users_by_email(email)
            if not response or not response.root:
                return None
            return _normalize_user(response.root[0])
        except Exception as e:
            logger.error("Remnawave get_user_by_email(%s) failed: %s", email, e)
            return None

    async def get_subscription_link(self, user_uuid: str) -> str | None:
        try:
            response: UserResponseDto = await self.sdk.users.get_user_by_uuid(user_uuid)
            return response.subscription_url if response else None
        except Exception as e:
            logger.error("Remnawave get_subscription_link(%s) failed: %s", user_uuid, e)
            return None

    # ----- write -----

    async def create_user(
        self,
        username: str,
        days: int = 30,
        limit_gb: int = 0,
        descr: str = "created by remnawave_client",
        email: Optional[str] = None,
        telegram_id: Optional[int] = None,
        tag: Optional[str] = None,
        squad_id: Optional[str] = None,
        external_squad_id: Optional[str] = None,
    ) -> dict | None:
        try:
            if email is None:
                email = f"{username}@bot.local"

            effective_squad = squad_id or self.free_squad_id
            active_squads = [effective_squad] if effective_squad else []

            new_user = CreateUserRequestDto(
                expire_at=datetime.datetime.now() + datetime.timedelta(days=days),
                username=username,
                created_at=datetime.datetime.now(),
                status=UserStatus.ACTIVE,
                vless_uuid=f"{_uuid.uuid4()}",
                traffic_limit_bytes=limit_gb * 1024 * 1024 * 1024 if limit_gb > 0 else 0,
                traffic_limit_strategy=(
                    TrafficLimitStrategy.MONTH if limit_gb > 0 else TrafficLimitStrategy.NO_RESET
                ),
                description=descr,
                email=email,
                active_internal_squads=active_squads,
                telegram_id=telegram_id,
                external_squad_uuid=external_squad_id,
            )

            if tag:
                new_user.tag = tag

            response: UserResponseDto = await self.sdk.users.create_user(new_user)

            expire_ts = int(response.expire_at.timestamp()) if response.expire_at else None
            return {
                "uuid": str(response.uuid) if response.uuid else None,
                "expire": expire_ts,
                "subscription_url": response.subscription_url,
                "status": "active",
                "email": response.email,
            }
        except Exception as e:
            logger.error("Remnawave create_user(%s) failed: %s", username, e)
            return None

    async def update_user(
        self,
        user_uuid: str,
        username: Optional[str] = None,
        days: Optional[int] = None,
        limit_gb: Optional[int] = None,
        descr: Optional[str] = None,
        email: Optional[str] = None,
        tag: Optional[str] = None,
        status: Optional[str] = None,
        squad_id: Optional[str] = None,
        external_squad_id: Optional[str] = None,
    ) -> dict | None:
        try:
            update_data: dict = {"uuid": _uuid.UUID(user_uuid)}

            if status is not None:
                update_data["status"] = _STATUS_MAP.get(status, UserStatus.ACTIVE)
            if username:
                update_data["username"] = username
            if days:
                update_data["expire_at"] = (
                    datetime.datetime.now() + datetime.timedelta(days=days)
                )
            if limit_gb is not None:
                update_data["traffic_limit_bytes"] = (
                    limit_gb * 1024 * 1024 * 1024 if limit_gb > 0 else 0
                )
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
            response: UserResponseDto = await self.sdk.users.update_user(request)

            expire_ts = int(response.expire_at.timestamp()) if response.expire_at else None
            return {
                "expire": expire_ts,
                "subscription_url": response.subscription_url,
                "status": response.status.value.lower() if response.status else None,
            }
        except Exception as e:
            logger.error("Remnawave update_user(%s) failed: %s", user_uuid, e)
            return None

    async def reset_user_traffic(self, user_uuid: str) -> bool:
        try:
            await self.sdk.users.reset_user_traffic(user_uuid)
            return True
        except Exception as e:
            logger.error("Remnawave reset_user_traffic(%s) failed: %s", user_uuid, e)
            return False

    async def delete_user(self, user_uuid: str) -> bool:
        try:
            await self.sdk.users.delete_user(user_uuid)
            return True
        except Exception as e:
            logger.error("Remnawave delete_user(%s) failed: %s", user_uuid, e)
            return False

    # ----- HWID devices -----

    async def get_user_hwid_devices(
        self, user_uuid: str
    ) -> GetUserHwidDevicesResponseDto | None:
        """Returns the raw SDK response (with .total and .devices). Consumers that
        need a list of dicts should map each device themselves; the SDK DTO is
        intentionally exposed because app/handlers/devices.py uses attribute
        access on device fields including datetime objects."""
        try:
            response: GetUserHwidDevicesResponseDto = await self.sdk.hwid.get_hwid_user(user_uuid)
            return response
        except Exception as e:
            logger.error("Remnawave get_user_hwid_devices(%s) failed: %s", user_uuid, e)
            return None

    async def delete_user_hwid_device(
        self, user_uuid: str, hwid: str
    ) -> DeleteUserHwidDeviceResponseDto | None:
        try:
            request = DeleteUserHwidDeviceRequestDto(user_uuid=user_uuid, hwid=hwid)
            response: DeleteUserHwidDeviceResponseDto = await self.sdk.hwid.delete_hwid_to_user(request)
            return response
        except Exception as e:
            logger.error(
                "Remnawave delete_user_hwid_device(%s, %s) failed: %s", user_uuid, hwid, e
            )
            return None


# ============================================================================
# Module-level default client (lazy, configured by host service at startup)
# ============================================================================

_default: RemnawaveClient | None = None


def configure(base_url: str, token: str, free_squad_id: Optional[str] = None) -> RemnawaveClient:
    """Configure (or reconfigure) the module-level default client. Idempotent
    per (base_url, token); calling again with the same credentials returns the
    same instance and only refreshes free_squad_id if previously unset."""
    global _default
    _default = RemnawaveClient.get(base_url, token, free_squad_id=free_squad_id)
    return _default


def get_default_client() -> RemnawaveClient:
    if _default is None:
        raise RuntimeError(
            "remnawave_client default client is not configured. "
            "Call remnawave_client.configure(base_url, token, free_squad_id=...) at startup."
        )
    return _default
