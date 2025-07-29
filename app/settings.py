from dataclasses import dataclass
from aiogram import Bot
import os
from dotenv import load_dotenv
load_dotenv()


@dataclass
class Secrets:
    token: str = os.environ["TOKEN"]
    admin_id: int = int(os.environ["ADMIN_ID"])
    marz_url: str = os.environ["MARZ_URL"]
    auth_name: str = os.environ["AUTH_NAME"]
    auth_pass: str = os.environ["AUTH_PASS"]





bot = Bot(token=Secrets.token)
