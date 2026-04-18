import copy
import json
import logging
import time
import uuid
import aiohttp

from app.settings import secrets

logger = logging.getLogger(__name__)

# ============================================================================
# Token cache — avoid re-authenticating on every request
# ============================================================================

_token_cache = {
    "access_token": None,
    "token_type": None,
    "expires_at": 0.0,  # monotonic time
}
_TOKEN_TTL = 25 * 60  # 25 minutes


class MarzbanAsync:
    def __init__(self):
        self.session: aiohttp.ClientSession | None = None
        self.access_token: str | None = None
        self.token_type: str | None = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        await self._ensure_token()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()

    async def _ensure_token(self):
        """Reuse cached token if still valid, otherwise fetch a new one."""
        now = time.monotonic()
        if _token_cache["access_token"] and now < _token_cache["expires_at"]:
            self.access_token = _token_cache["access_token"]
            self.token_type = _token_cache["token_type"]
            return
        await self._fetch_token()

    async def _fetch_token(self):
        """Fetch a new auth token from Marzban."""
        auth_data = {
            "grant_type": "password",
            "username": secrets.get('auth_name'),
            "password": secrets.get('auth_pass'),
            "scope": "",
        }
        async with self.session.post(
            secrets.get('marz_url') + "/api/admin/token",
            data=auth_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ) as response:
            if response.status == 200:
                token_data = await response.json()
                self.access_token = token_data["access_token"]
                self.token_type = token_data.get("token_type", "Bearer").capitalize()
                # Cache the token
                _token_cache["access_token"] = self.access_token
                _token_cache["token_type"] = self.token_type
                _token_cache["expires_at"] = time.monotonic() + _TOKEN_TTL
            else:
                error_text = await response.text()
                logger.error("Marzban auth error %s: %s", response.status, error_text)
                raise Exception("Ошибка аутентификации Marzban")

    def _headers(self) -> dict:
        return {
            "Authorization": f"{self.token_type} {self.access_token}",
            "Content-Type": "application/json",
        }

    async def add_user(self, template, name, usrid, limit, res_strat, expire):
        """Создание пользователя (template не мутируется)."""
        template = copy.deepcopy(template)
        template["username"] = name
        template["proxies"]["vless"]["id"] = f"{uuid.uuid4()}"
        template["data_limit"] = limit
        template["data_limit_reset_strategy"] = f"{res_strat}"
        template["expire"] = expire

        async with self.session.post(
            secrets.get('marz_url') + "/api/user",
            data=json.dumps(template),
            headers=self._headers(),
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                error_text = await response.text()
                logger.error("Marzban add_user error %s: %s", response.status, error_text)
                return response.status

    async def set_user(self, template, name, limit, res_strat, expire):
        """Обновление пользователя (template не мутируется)."""
        template = copy.deepcopy(template)
        template.pop("username", None)
        template["data_limit"] = limit
        template["data_limit_reset_strategy"] = f"{res_strat}"
        template["expire"] = expire

        async with self.session.put(
            secrets.get('marz_url') + f"/api/user/{name}",
            data=json.dumps(template),
            headers=self._headers(),
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                error_text = await response.text()
                logger.error("Marzban set_user error %s: %s", response.status, error_text)
                return response.status

    async def get_user(self, name):
        """Получение информации о пользователе."""
        async with self.session.get(
            secrets.get('marz_url') + f"/api/user/{name}",
            headers=self._headers(),
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                error_text = await response.text()
                logger.error("Marzban get_user error %s: %s", response.status, error_text)
                return response.status
