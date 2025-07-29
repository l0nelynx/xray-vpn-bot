from app.marzban.templates import vless_template
from app.settings import Secrets
from dotenv import load_dotenv
import asyncio
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
            "username": Secrets.auth_name,
            "password": Secrets.auth_pass,
            "scope": ""
        }
        async with self.session.post(
                Secrets.marz_url + "/api/admin/token",
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

    async def add_user(self, template, name, usrid, limit, res_strat):
        """Создание пользователя"""
        template["username"] = name
        template["id"] = f"id{usrid}"
        template["data_limit"] = limit
        template["data_limit_reset_strategy"] = f"{res_strat}"

        headers = {
            "Authorization": f"{self.token_type} {self.access_token}",
            "Content-Type": "application/json"
        }
        async with self.session.post(
                Secrets.marz_url + "/api/user",
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

    async def set_user(self, template, name, limit, res_strat):
        """Создание пользователя"""
        del template["username"]
        template["data_limit"] = limit
        template["data_limit_reset_strategy"] = f"{res_strat}"
        headers = {
            "Authorization": f"{self.token_type} {self.access_token}",
            "Content-Type": "application/json"
        }
        async with self.session.put(
                Secrets.marz_url + f"/api/user/{name}",
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
                Secrets.marz_url + f"/api/user/{name}",
                headers=headers
        ) as response:
            if response.status == 200:
                print("Успешный запрос!")
                response_data = await response.json()
                print(response_data.get("username", "No inbounds data"))
                print(response_data.get("subscription_url", "No inbounds data"))
                print(response_data.get("links", "No inbounds data"))
            #                print("Ответ сервера:", response_data)
                return response_data
            else:
                error_text = await response.text()
                print(f"Ошибка {response.status}: {error_text}")
                return response.status

async def main():
    # Создаем контекст для автоматического управления ресурсами
    async with MarzbanAsync() as marz:
      #  Создаем пользователя
        await marz.add_user(
                   template=vless_template,
                   name="Alice",
                   usrid="12345",
                   limit=5,
                   res_strat="no_reset" # no_reset day week month year
               )
        getresp = await marz.get_user("Alice")
        print(getresp["username"])
        await marz.set_user(name="Alice",template=vless_template,
                            limit=5*1024*1024*1024,res_strat="month")

# Запуск асинхронной функции
if __name__ == "__main__":
    asyncio.run(main())

# Вывод конкретного параметра
# print(data_dict["address"]["city"])
# print(data_dict["hobbies"][0])
# asyncio.run(Marzetto(template=vless_template,name="testuser01",id="000000001"))
