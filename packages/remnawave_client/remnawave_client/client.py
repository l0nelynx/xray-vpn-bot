import datetime
import logging
import uuid as _uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from remnawave import RemnawaveSDK
from remnawave.enums import TrafficLimitStrategy, UserStatus
from remnawave.models import (
    CreateUserRequestDto,
    DeleteUserHwidDeviceRequestDto,
    UpdateUserRequestDto,
    UserResponseDto,
    UsersResponseDto,
)

logger = logging.getLogger(__name__)


# --- HWID compatibility shim ------------------------------------------------
#
# The installed `remnawave` SDK (pinned remnawave>=2.8.0, currently 2.8.0)
# still models device rows with a required `userUuid: UUID` field
# (remnawave.models.hwid.HwidDeviceDto). Newer Remnawave panels return
# `userId: int` instead, so `sdk.hwid.get_hwid_user()` /
# `sdk.hwid.delete_hwid_to_user()` raise a pydantic ValidationError on every
# call and we fall into the except branches below, returning None. A fix is
# pending upstream (PR under review); until a fixed SDK version is released,
# both HWID device calls bypass the typed SDK methods and go straight through
# the SDK's own authenticated httpx client (`sdk.hwid.client`, a public
# dataclass field — see rapid_api_client.RapidApi), parsing the response with
# this tolerant local model instead.
#
# TODO: once `remnawave` ships a compatible HwidDeviceDto, delete this shim and
# restore `self.sdk.hwid.get_hwid_user(...)` / `self.sdk.hwid.delete_hwid_to_user(...)`.
class HwidDeviceCompat(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    hwid: str
    user_uuid: Optional[_uuid.UUID] = Field(None, alias="userUuid")
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
        "uuid": str(user.uuid) if user.uuid else None,
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

    async def _fetch_users_page(
        self, *, start: int = 0, size: int = 500
    ) -> UsersResponseDto:
        """Paginated users list — works across SDK versions."""
        users_ctrl = self.sdk.users
        fetch_v2 = getattr(users_ctrl, "get_all_users_v2", None)
        if fetch_v2 is not None:
            return await fetch_v2(start=start, size=size)
        try:
            return await users_ctrl.get_all_users(start=start, size=size)
        except TypeError:
            if start != 0:
                raise
            return await users_ctrl.get_all_users()

    async def get_all_users(self) -> UsersResponseDto:
        response = await self._fetch_users_page()
        logger.info("Remnawave total users: %s", response.total)
        return response

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

    async def get_users_by_tag(self, tag: str) -> list[dict]:
        """Fetch panel users with the given tag (uppercase, no spaces)."""
        from .segmentation import normalize_user_for_crm

        normalized = tag.strip().upper().replace(" ", "")
        if not normalized:
            return []
        try:
            response = await self.sdk.users.client.get(
                f"/users/by-tag/{normalized}"
            )
            response.raise_for_status()
            data = _unwrap_response_envelope(response.json())
            items: list = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                for key in ("users", "root"):
                    raw = data.get(key)
                    if isinstance(raw, list):
                        items = raw
                        break
            return [normalize_user_for_crm(u) for u in items]
        except Exception as e:
            logger.error("Remnawave get_users_by_tag(%s) failed: %s", normalized, e)
            raise

    async def get_all_users_for_crm(self) -> list[dict]:
        """Bulk-fetch every panel user normalized for CRM segmentation."""
        from .segmentation import normalize_user_for_crm

        page_size = 500
        start = 0
        total: int | None = None
        normalized: list[dict] = []

        while True:
            response = await self._fetch_users_page(start=start, size=page_size)
            raw_users = (
                getattr(response, "users", None)
                or getattr(response, "root", None)
                or []
            )
            if total is None:
                total = int(getattr(response, "total", None) or len(raw_users))
                logger.info("Remnawave total users: %s", total)

            normalized.extend(normalize_user_for_crm(u) for u in raw_users)
            start += len(raw_users)
            if not raw_users or start >= total:
                break

        return normalized

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

    async def get_user_by_uuid(self, user_uuid: str) -> dict | None:
        try:
            response = await self.sdk.users.get_user_by_uuid(user_uuid)
            if not response:
                return None
            return _normalize_user(response)
        except Exception as e:
            logger.error("Remnawave get_user_by_uuid(%s) failed: %s", user_uuid, e)
            return None

    async def get_user_by_id(self, rw_id: int) -> dict | None:
        """Fetch a Remnawave user by its stable numeric panel id."""
        try:
            response = await self.sdk.users.get_user_by_id(str(int(rw_id)))
            if not response:
                return None
            return _normalize_user(response)
        except (TypeError, ValueError):
            return None
        except Exception as e:
            logger.error("Remnawave get_user_by_id(%s) failed: %s", rw_id, e)
            return None

    async def _uuid_for_id(self, rw_id: int) -> str | None:
        user = await self.get_user_by_id(rw_id)
        if not user:
            return None
        value = user.get("uuid")
        return str(value) if value else None

    async def get_user_by_short_uuid_raw(self, short_uuid: str) -> dict | None:
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
            logger.error("Remnawave get_user_by_short_uuid(%s) failed: %s", short_uuid, e)
            return None

    async def get_subscription_link(self, user_uuid: str) -> str | None:
        try:
            response: UserResponseDto = await self.sdk.users.get_user_by_uuid(user_uuid)
            return response.subscription_url if response else None
        except Exception as e:
            logger.error("Remnawave get_subscription_link(%s) failed: %s", user_uuid, e)
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

            new_user = CreateUserRequestDto(
                expire_at=datetime.datetime.now() + datetime.timedelta(days=days),
                username=username,
                created_at=datetime.datetime.now(),
                status=UserStatus.ACTIVE,
                vless_uuid=f"{_uuid.uuid4()}",
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
                "uuid": str(response.uuid) if response.uuid else None,
                "rw_id": _extract_rw_id(response),
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
        internal_squad_ids: Optional[list[str]] = None,
        external_squad_id: Optional[str] = None,
        traffic_limit_bytes: Optional[int] = None,
        traffic_limit_strategy: Optional[str] = None,
    ) -> dict | None:
        try:
            update_data: dict = {"uuid": _uuid.UUID(user_uuid)}

            if status is None:
                update_data["status"] = UserStatus.ACTIVE
            else:
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

            request = UpdateUserRequestDto(**update_data)
            response: UserResponseDto = await self.sdk.users.update_user(request)

            expire_ts = int(response.expire_at.timestamp()) if response.expire_at else None
            resp_squads: list[str] = []
            for s in (getattr(response, "active_internal_squads", None) or []):
                v = (s.get("uuid") if isinstance(s, dict)
                     else getattr(s, "uuid", None))
                if v:
                    resp_squads.append(str(v))
            logger.info(
                "Remnawave update_user OK uuid=%s "
                "sent{status=%s expire_at=%s traffic_limit_bytes=%s squads=%s ext_squad=%s} "
                "resp{status=%s expire_at=%s traffic_limit_bytes=%s squads=%s}",
                user_uuid,
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
                "uuid": str(response.uuid) if response.uuid else None,
                "rw_id": _extract_rw_id(response),
                "expire": expire_ts,
                "subscription_url": response.subscription_url,
                "status": response.status.value.lower() if response.status else None,
            }
        except Exception as e:
            logger.error("Remnawave update_user(%s) failed: %s", user_uuid, e)
            return None

    async def update_user_by_id(self, rw_id: int, **changes) -> dict | None:
        """ID-first update while the upstream SDK still mutates by UUID."""
        user_uuid = await self._uuid_for_id(rw_id)
        if not user_uuid:
            return None
        return await self.update_user(user_uuid, **changes)

    async def reset_user_traffic(self, user_uuid: str) -> bool:
        try:
            await self.sdk.users.reset_user_traffic(user_uuid)
            return True
        except Exception as e:
            logger.error("Remnawave reset_user_traffic(%s) failed: %s", user_uuid, e)
            return False

    async def reset_user_traffic_by_id(self, rw_id: int) -> bool:
        user_uuid = await self._uuid_for_id(rw_id)
        return bool(user_uuid) and await self.reset_user_traffic(user_uuid)

    async def delete_user(self, user_uuid: str) -> bool:
        try:
            await self.sdk.users.delete_user(user_uuid)
            return True
        except Exception as e:
            logger.error("Remnawave delete_user(%s) failed: %s", user_uuid, e)
            return False

    async def delete_user_by_id(self, rw_id: int) -> bool:
        user_uuid = await self._uuid_for_id(rw_id)
        return bool(user_uuid) and await self.delete_user(user_uuid)

    # ----- HWID devices -----

    async def get_user_hwid_devices(
        self, user_uuid: str
    ) -> HwidDevicesCompat | None:
        """Returns .total and .devices (see HwidDevicesCompat above for why this
        bypasses self.sdk.hwid.get_hwid_user()). Consumers that need a list of
        dicts should map each device themselves; the compat DTO is intentionally
        exposed because app/handlers/devices.py uses attribute access on device
        fields including datetime objects."""
        try:
            response = await self.sdk.hwid.client.get(f"/hwid/devices/{user_uuid}")
            response.raise_for_status()
            data = _unwrap_response_envelope(response.json())
            return HwidDevicesCompat.model_validate(data)
        except Exception as e:
            logger.error("Remnawave get_user_hwid_devices(%s) failed: %s", user_uuid, e)
            return None

    async def get_user_hwid_devices_by_id(
        self, rw_id: int
    ) -> HwidDevicesCompat | None:
        user_uuid = await self._uuid_for_id(rw_id)
        if not user_uuid:
            return None
        return await self.get_user_hwid_devices(user_uuid)

    async def delete_user_hwid_device(
        self, user_uuid: str, hwid: str
    ) -> HwidDevicesCompat | None:
        """See get_user_hwid_devices — the delete response embeds the same
        broken devices list, so it needs the same bypass."""
        try:
            request = DeleteUserHwidDeviceRequestDto(user_uuid=user_uuid, hwid=hwid)
            response = await self.sdk.hwid.client.post(
                "/hwid/devices/delete",
                json=request.model_dump(mode="json", by_alias=True),
            )
            response.raise_for_status()
            data = _unwrap_response_envelope(response.json())
            return HwidDevicesCompat.model_validate(data)
        except Exception as e:
            logger.error(
                "Remnawave delete_user_hwid_device(%s, %s) failed: %s", user_uuid, hwid, e
            )
            return None

    async def delete_user_hwid_device_by_id(
        self, rw_id: int, hwid: str
    ) -> HwidDevicesCompat | None:
        user_uuid = await self._uuid_for_id(rw_id)
        if not user_uuid:
            return None
        return await self.delete_user_hwid_device(user_uuid, hwid)


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
