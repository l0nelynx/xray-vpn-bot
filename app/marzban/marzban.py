from app.settings import secrets

import aiohttp
import json


class MarzbanAsync:
    def __init__(self):
        self.session = None
        self.access_token = None
        self.token_type = None

    async def __aenter__(self):
        """Асинхронный контекстный менеджер для инициализации"""
        self.session = aiohttp.ClientSession()
        await self._get_auth_token()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Гарантированное закрытие сессии при выходе из контекста"""
        await self.session.close()

    async def _get_auth_token(self):
        """Получение токена авторизации"""
        auth_data = {
            "grant_type": "password",
            "username": secrets.get('auth_name'),
            "password": secrets.get('auth_pass'),
            "scope": ""
        }
        async with self.session.post(
                secrets.get('marz_url') + "/api/admin/token",
                data=auth_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
        ) as response:
            if response.status == 200:
                token_data = await response.json()
                self.access_token = token_data["access_token"]
                self.token_type = token_data.get("token_type", "Bearer").capitalize()
                # print(f"Токен получен: {self.access_token}")
            else:
                error_text = await response.text()
                print(f"Ошибка авторизации: {response.status}")
                print(error_text)
                raise Exception("Ошибка аутентификации")

    async def add_user(self, template, name, usrid, limit, res_strat, expire):
        """Создание пользователя"""
        template["username"] = name
        template["id"] = f"id{usrid}"
        template["data_limit"] = limit
        template["data_limit_reset_strategy"] = f"{res_strat}"
        template["expire"] = expire

        headers = {
            "Authorization": f"{self.token_type} {self.access_token}",
            "Content-Type": "application/json"
        }
        async with self.session.post(
                secrets.get('marz_url') + "/api/user",
                data=json.dumps(template),
                headers=headers
        ) as response:
            if response.status == 200:
                print("Успешный запрос!")
                response_data = await response.json()
                print(response_data.get("inbounds", "No inbounds data"))
                return response_data
            #                print("Ответ сервера:", response_data)
            else:
                error_text = await response.text()
                print(f"Ошибка {response.status}: {error_text}")
                return response.status

    async def set_user(self, template, name, limit, res_strat, expire):
        """Создание пользователя"""
        del template["username"]
        template["data_limit"] = limit
        template["data_limit_reset_strategy"] = f"{res_strat}"
        template["expire"] = expire
        headers = {
            "Authorization": f"{self.token_type} {self.access_token}",
            "Content-Type": "application/json"
        }
        async with self.session.put(
                secrets.get('marz_url') + f"/api/user/{name}",
                data=json.dumps(template),
                headers=headers
        ) as response:
            if response.status == 200:
                print("Успешный запрос!")
                response_data = await response.json()
                print(response_data.get("data_limit", "No inbounds data"))
                print(response_data.get("data_limit_reset_strategy", "No inbounds data"))
                #                print("Ответ сервера:", response_data)
                return response_data
            else:
                error_text = await response.text()
                print(f"Ошибка {response.status}: {error_text}")
                return response.status

    async def get_user(self, name):
        headers = {
            "Authorization": f"{self.token_type} {self.access_token}",
            "Content-Type": "application/json"
        }
        async with self.session.get(
                secrets.get('marz_url') + f"/api/user/{name}",
                headers=headers
        ) as response:
            if response.status == 200:
                print("Успешный запрос!")
                response_data = await response.json()
                # print(response_data.get("username", "No inbounds data"))
                print(response_data)
                # print(response_data.get("subscription_url", "No inbounds data"))
                # print(response_data.get("links", "No inbounds data"))
                #                print("Ответ сервера:", response_data)
                return response_data
            else:
                error_text = await response.text()
                print(f"Ошибка {response.status}: {error_text}")
                return response.status
