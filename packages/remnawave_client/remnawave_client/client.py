import datetime
import logging
import uuid as _uuid
from typing import Optional

import httpx
from pydantic import BaseModel, ConfigDict, Field
from remnawave import RemnawaveSDK
from remnawave.enums import TrafficLimitStrategy, UserStatus
from remnawave.models import (
    CreateUserBodyDto,
    DeleteUserHwidDeviceRequestDto,
    UpdateUserBodyDto,
    UserResponseDto,
)

logger = logging.getLogger(__name__)


class RemnawaveOperationError(RuntimeError):
    """A Remnawave request failed for a reason other than a genuine 404.

    The legacy client returns ``None`` for compatibility. Delivery code can
    opt into this exception so an outage is not confused with "user missing".
    """

    def __init__(self, operation: str, cause: Exception) -> None:
        self.operation = operation
        self.cause = cause
        response = getattr(cause, "response", None)
        self.status_code = getattr(response, "status_code", None)
        self.retryable = (
            isinstance(cause, (httpx.TimeoutException, httpx.NetworkError))
            or self.status_code in {408, 425, 429}
            or (self.status_code is not None and self.status_code >= 500)
        )
        detail = str(cause).strip() or type(cause).__name__
        status = f" http_status={self.status_code}" if self.status_code else ""
        super().__init__(
            f"remnawave_{operation}_failed:{type(cause).__name__}{status}: {detail}"
        )


def _is_not_found_error(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None) == 404


class HwidDeviceCompat(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    hwid: str
    user_id: Optional[int] = Field(None, alias="userId")
    platform: Optional[str] = None
    os_version: Optional[str] = Field(None, alias="osVersion")
    device_model: Optional[str] = Field(None, alias="deviceModel")
    user_agent: Optional[str] = Field(None, alias="userAgent")
    created_at: Optional[datetime.datetime] = Field(None, alias="createdAt")
    updated_at: Optional[datetime.datetime] = Field(None, alias="updatedAt")


class HwidDevicesCompat(BaseModel):
    total: float = 0
    devices: list[HwidDeviceCompat] = []


def _unwrap_response_envelope(data: object) -> object:
    """Remnawave wraps every payload as {"response": {...}}; the SDK's own
    _handle_response() unwraps this before pydantic validation (see
    remnawave.rapid.client.BaseController._handle_response). Since we're
    calling the httpx client directly (bypassing that method), replicate the
    unwrap here so our compat model sees the same shape it normally would."""
    if isinstance(data, dict) and "response" in data:
        return data["response"]
    return data


_STATUS_MAP = {
    "active": UserStatus.ACTIVE,
    "disabled": UserStatus.DISABLED,
    "limited": UserStatus.LIMITED,
    "expired": UserStatus.EXPIRED,
}


def _extract_rw_id(user: UserResponseDto | dict) -> int | None:
    """Remnawave panel numeric user id from SDK DTO or raw dict."""
    if isinstance(user, dict):
        raw = user.get("id")
    else:
        raw = getattr(user, "id", None)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


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
        "rw_id": _extract_rw_id(user),
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
        "telegram_id": getattr(user, "telegram_id", None),
        "username": getattr(user, "username", None),
        "description": getattr(user, "description", None),
        "tag": getattr(user, "tag", None),
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

    async def _get_squads(self, kind: str, *, strict: bool = False) -> list[dict]:
        """List internal/external squads through the SDK-authenticated client."""
        from .segmentation import _get_attr

        try:
            endpoint = f"/{kind}-squads"
            response = await self.sdk.users.client.get(endpoint)
            response.raise_for_status()
            data = _unwrap_response_envelope(response.json())
            items: list = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                keys = (
                    f"{kind}Squads",
                    f"{kind}_squads",
                    "squads",
                    "root",
                )
                for key in keys:
                    raw = data.get(key)
                    if isinstance(raw, list):
                        items = raw
                        break
            squads: list[dict] = []
            for item in items:
                uuid = _get_attr(item, "uuid", "id")
                if not uuid:
                    continue
                squads.append({
                    "uuid": str(uuid),
                    "name": _get_attr(item, "name", "title") or str(uuid),
                })
            return squads
        except Exception as e:
            logger.error("Remnawave get_%s_squads failed: %s", kind, e)
            if strict:
                raise
            return []

    async def get_internal_squads(self, *, strict: bool = False) -> list[dict]:
        """List internal squads from Remnawave panel."""
        return await self._get_squads("internal", strict=strict)

    async def get_external_squads(self, *, strict: bool = False) -> list[dict]:
        """List external squads from Remnawave panel."""
        return await self._get_squads("external", strict=strict)

    async def _stream_users(self, **filters) -> list[UserResponseDto]:
        """Read every v3 cursor page; outages are never converted to not-found."""
        cursor: int | None = None
        users: list[UserResponseDto] = []
        while True:
            page = await self.sdk.users.get_users_stream(
                size=500, cursor=cursor, **filters
            )
            users.extend(page.users)
            if not page.has_more:
                return users
            if page.next_cursor is None or page.next_cursor == cursor:
                raise RuntimeError("remnawave_users_stream_invalid_cursor")
            cursor = page.next_cursor

    async def get_users_by_tag(self, tag: str) -> list[dict]:
        from .segmentation import normalize_user_for_crm

        normalized = tag.strip().upper().replace(" ", "")
        if not normalized:
            return []
        return [
            normalize_user_for_crm(user)
            for user in await self._stream_users(tag=normalized)
            if (user.tag or "").strip().upper() == normalized
        ]

    async def get_all_users_for_crm(self) -> list[dict]:
        """Bulk-fetch every panel user normalized for CRM segmentation."""
        from .segmentation import normalize_user_for_crm

        return [normalize_user_for_crm(user) for user in await self._stream_users()]

    async def get_user_by_username(
        self, username: str, *, raise_on_error: bool = False,
    ) -> dict | None:
        try:
            response = await self.sdk.users.get_user_by_username(username)
            if not response:
                return None
            return _normalize_user(response)
        except Exception as e:
            if _is_not_found_error(e):
                return None
            logger.error("Remnawave get_user_by_username(%s) failed: %s", username, e)
            if raise_on_error:
                raise RemnawaveOperationError("get_user_by_username", e) from e
            return None

    async def get_users_by_email(self, email: str) -> list[dict]:
        normalized = email.strip().casefold()
        if not normalized:
            return []
        try:
            users = await self._stream_users(email=email.strip())
            return [
                _normalize_user(user)
                for user in users
                if (user.email or "").strip().casefold() == normalized
            ]
        except Exception as e:
            logger.error("Remnawave get_user_by_email(%s) failed: %s", email, e)
            raise RemnawaveOperationError("get_user_by_email", e) from e

    async def get_user_by_email(self, email: str) -> dict | None:
        matches = await self.get_users_by_email(email)
        if len(matches) > 1:
            raise RemnawaveOperationError(
                "get_user_by_email_conflict",
                ValueError(f"multiple exact email matches: {email}"),
            )
        return matches[0] if matches else None

    async def get_user_by_id(
        self, rw_id: int, *, raise_on_error: bool = False,
    ) -> dict | None:
        """Fetch a Remnawave user by its stable numeric panel id."""
        try:
            response = await self.sdk.users.get_user_by_id(int(rw_id))
            if not response:
                return None
            return _normalize_user(response)
        except (TypeError, ValueError) as e:
            if raise_on_error:
                raise RemnawaveOperationError("get_user_by_id", e) from e
            return None
        except Exception as e:
            if _is_not_found_error(e):
                return None
            logger.error("Remnawave get_user_by_id(%s) failed: %s", rw_id, e)
            if raise_on_error:
                raise RemnawaveOperationError("get_user_by_id", e) from e
            return None

    async def get_user_by_short_uuid_raw(
        self, short_uuid: str, *, raise_on_error: bool = False,
    ) -> dict | None:
        """Lookup user by Remnawave short_uuid and return the SDK DTO
        serialized as-is (no normalization). Used by the Android
        /check-uuid endpoint to verify ownership of an existing subscription
        before account registration."""
        try:
            response = await self.sdk.users.get_user_by_short_uuid(short_uuid)
            if not response:
                return None
            return response.model_dump(mode="json", by_alias=True, exclude_none=False)
        except Exception as e:
            if _is_not_found_error(e):
                return None
            logger.error("Remnawave get_user_by_short_uuid(%s) failed: %s", short_uuid, e)
            if raise_on_error:
                raise RemnawaveOperationError("get_user_by_short_uuid", e) from e
            return None

    async def get_subscription_link_by_id(self, rw_id: int) -> str | None:
        user = await self.get_user_by_id(rw_id)
        if not user:
            return None
        value = user.get("subscription_url")
        return str(value) if value else None

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
        internal_squad_ids: Optional[list[str]] = None,
        external_squad_id: Optional[str] = None,
        traffic_limit_bytes: Optional[int] = None,
        traffic_limit_strategy: Optional[str] = None,
        raise_on_error: bool = False,
    ) -> dict | None:
        try:
            if email is None:
                email = f"{username}@bot.local"

            effective_squad = squad_id or self.free_squad_id
            active_squads = (
                list(dict.fromkeys(internal_squad_ids))
                if internal_squad_ids is not None
                else ([effective_squad] if effective_squad else [])
            )
            effective_limit = (
                int(traffic_limit_bytes)
                if traffic_limit_bytes is not None
                else (limit_gb * 1024 * 1024 * 1024 if limit_gb > 0 else 0)
            )
            strategy_name = (
                traffic_limit_strategy
                or ("MONTH" if effective_limit > 0 else "NO_RESET")
            ).upper()

            new_user = CreateUserBodyDto(
                expire_at=datetime.datetime.now() + datetime.timedelta(days=days),
                username=username,
                created_at=datetime.datetime.now(),
                status=UserStatus.ACTIVE,
                vless_uuid=_uuid.uuid4(),
                traffic_limit_bytes=effective_limit,
                traffic_limit_strategy=TrafficLimitStrategy(strategy_name),
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
                "rw_id": _extract_rw_id(response),
                "expire": expire_ts,
                "subscription_url": response.subscription_url,
                "status": "active",
                "email": response.email,
                "telegram_id": getattr(response, "telegram_id", None),
                "username": getattr(response, "username", username),
                "description": getattr(response, "description", descr),
                "tag": getattr(response, "tag", tag),
            }
        except Exception as e:
            logger.error("Remnawave create_user(%s) failed: %s", username, e)
            if raise_on_error:
                raise RemnawaveOperationError("create_user", e) from e
            return None

    async def update_user_by_id(
        self,
        rw_id: int,
        username: Optional[str] = None,
        days: Optional[int] = None,
        limit_gb: Optional[int] = None,
        descr: Optional[str] = None,
        email: Optional[str] = None,
        tag: Optional[str] = None,
        status: Optional[str] = None,
        squad_id: Optional[str] = None,
        internal_squad_ids: Optional[list[str]] = None,
        external_squad_id: Optional[str] = None,
        traffic_limit_bytes: Optional[int] = None,
        traffic_limit_strategy: Optional[str] = None,
        raise_on_error: bool = False,
    ) -> dict | None:
        try:
            update_data: dict = {"id": int(rw_id)}

            if status is not None:
                try:
                    update_data["status"] = _STATUS_MAP[status.lower()]
                except KeyError:
                    raise ValueError(f"unknown remnawave status: {status!r}")
            if username:
                update_data["username"] = username
            if days:
                update_data["expire_at"] = (
                    datetime.datetime.now() + datetime.timedelta(days=days)
                )
            if traffic_limit_bytes is not None:
                update_data["traffic_limit_bytes"] = int(traffic_limit_bytes)
            elif limit_gb is not None:
                update_data["traffic_limit_bytes"] = limit_gb * 1024 * 1024 * 1024 if limit_gb > 0 else 0
            if traffic_limit_strategy is not None:
                update_data["traffic_limit_strategy"] = TrafficLimitStrategy(
                    traffic_limit_strategy.upper()
                )
            elif "traffic_limit_bytes" in update_data:
                update_data["traffic_limit_strategy"] = (
                    TrafficLimitStrategy.MONTH
                    if update_data["traffic_limit_bytes"] > 0
                    else TrafficLimitStrategy.NO_RESET
                )
            if descr:
                update_data["description"] = descr
            if email:
                update_data["email"] = email
            if tag:
                update_data["tag"] = tag
            if internal_squad_ids is not None:
                update_data["active_internal_squads"] = list(
                    dict.fromkeys(internal_squad_ids)
                )
            elif squad_id:
                update_data["active_internal_squads"] = [squad_id]
            if external_squad_id:
                update_data["external_squad_uuid"] = external_squad_id

            request = UpdateUserBodyDto(**update_data)
            response: UserResponseDto = await self.sdk.users.update_user(request)

            expire_ts = int(response.expire_at.timestamp()) if response.expire_at else None
            resp_squads: list[str] = []
            for s in (getattr(response, "active_internal_squads", None) or []):
                v = (s.get("uuid") if isinstance(s, dict)
                     else getattr(s, "uuid", None))
                if v:
                    resp_squads.append(str(v))
            logger.info(
                "Remnawave update_user OK rw_id=%s "
                "sent{status=%s expire_at=%s traffic_limit_bytes=%s squads=%s ext_squad=%s} "
                "resp{status=%s expire_at=%s traffic_limit_bytes=%s squads=%s}",
                rw_id,
                update_data.get("status"),
                update_data.get("expire_at"),
                update_data.get("traffic_limit_bytes"),
                update_data.get("active_internal_squads"),
                update_data.get("external_squad_uuid"),
                response.status,
                response.expire_at,
                response.traffic_limit_bytes,
                resp_squads,
            )
            return {
                "rw_id": _extract_rw_id(response),
                "expire": expire_ts,
                "subscription_url": response.subscription_url,
                "status": response.status.value.lower() if response.status else None,
            }
        except Exception as e:
            logger.error("Remnawave update_user_by_id(%s) failed: %s", rw_id, e)
            if raise_on_error:
                raise RemnawaveOperationError("update_user", e) from e
            return None

    async def reset_user_traffic_by_id(self, rw_id: int) -> bool:
        try:
            await self.sdk.users.reset_user_traffic(int(rw_id))
            return True
        except Exception as e:
            logger.error("Remnawave reset_user_traffic_by_id(%s) failed: %s", rw_id, e)
            return False

    async def delete_user_by_id(self, rw_id: int) -> bool:
        try:
            await self.sdk.users.delete_user(int(rw_id))
            return True
        except Exception as e:
            logger.error("Remnawave delete_user_by_id(%s) failed: %s", rw_id, e)
            return False

    # ----- HWID devices -----

    async def get_user_hwid_devices_by_id(
        self, rw_id: int
    ) -> HwidDevicesCompat | None:
        try:
            response = await self.sdk.hwid.get_hwid_user(int(rw_id))
            return HwidDevicesCompat.model_validate(
                response.model_dump(mode="json", by_alias=True)
            )
        except Exception as e:
            logger.error("Remnawave get_user_hwid_devices_by_id(%s) failed: %s", rw_id, e)
            return None

    async def delete_user_hwid_device_by_id(
        self, rw_id: int, hwid: str
    ) -> HwidDevicesCompat | None:
        try:
            request = DeleteUserHwidDeviceRequestDto(user_id=int(rw_id), hwid=hwid)
            response = await self.sdk.hwid.delete_hwid_to_user(request)
            return HwidDevicesCompat.model_validate(
                response.model_dump(mode="json", by_alias=True)
            )
        except Exception as e:
            logger.error(
                "Remnawave delete_user_hwid_device_by_id(%s, %s) failed: %s",
                rw_id, hwid, e,
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
