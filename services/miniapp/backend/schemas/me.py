from typing import Literal

from pydantic import BaseModel, Field


class UserInfo(BaseModel):
    tg_id: int
    username: str | None
    language: str | None


class LanguageUpdate(BaseModel):
    language: Literal["ru", "en"] = Field(..., description="UI language code")


class SubscriptionInfo(BaseModel):
    subscription_id: int | None = None
    label: str | None = None
    tariff: str
    status: str | None
    days_left: int
    expire_iso: str | None
    data_limit_gb: int | None
    traffic_used_gb: int
    devices_count: int
    subscription_url: str | None


class LinksInfo(BaseModel):
    bot_url: str
    policy_url: str
    agreement_url: str
    news_url: str = ""
    branding_name: str = ""
    support_bot_link: str = ""


class MeResponse(BaseModel):
    registered: bool
    user: UserInfo | None = None
    subscription: SubscriptionInfo | None = None
    subscriptions_count: int = 0
    links: LinksInfo
