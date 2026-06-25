"""Pydantic models for Stage 6 Android read-side endpoints.

Kept in `android/` so the existing miniapp `schemas/` package stays untouched
and so the Android shape (no `tg_id` required, optional Telegram link state)
can diverge from the Telegram-only miniapp schemas.
"""
from __future__ import annotations

from pydantic import BaseModel, EmailStr


class AndroidUserSummary(BaseModel):
    id: int
    email: str | None
    email_verified: bool
    tg_id: int | None
    language: str | None
    has_password: bool = False


class AndroidSubscription(BaseModel):
    tariff: str
    status: str | None
    days_left: int
    expire_iso: str | None
    data_limit_gb: int | None
    traffic_used_gb: int
    devices_count: int
    subscription_url: str | None
    source: str  # "remnawave" | "google_play"


class AndroidLinks(BaseModel):
    bot_url: str
    policy_url: str
    agreement_url: str
    news_url: str = ""
    branding_name: str = ""
    support_bot_link: str = ""


class AndroidMeResponse(BaseModel):
    user: AndroidUserSummary
    subscription: AndroidSubscription | None
    links: AndroidLinks


class AndroidDeviceItem(BaseModel):
    hwid: str
    platform: str | None = None
    os_version: str | None = None
    device_model: str | None = None
    user_agent: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AndroidDevicesResponse(BaseModel):
    total: int
    devices: list[AndroidDeviceItem]


class AndroidSessionItem(BaseModel):
    id: int
    issued_at: str
    expires_at: str
    user_agent: str | None
    ip: str | None
    current: bool | None  # null when access token does not expose family_id


class AndroidSessionsResponse(BaseModel):
    total: int
    sessions: list[AndroidSessionItem]


class AndroidRevokeAllResponse(BaseModel):
    revoked: int


class LinkStartResponse(BaseModel):
    code: str
    expires_in: int
    deep_link: str


class LinkByUrlRequest(BaseModel):
    url: str  # Validated by _parse_short_uuid in the router; plain str
              # avoids Pydantic HttpUrl's strict percent-encoding edge
              # cases (some clients send raw `:` in path).
    email: EmailStr  # Subscription owner's email — must match the email
                     # Remnawave has on file for the URL's owner. See
                     # docs/superpowers/specs/2026-05-21-android-link-by-url-email-design.md.


class LinkByUrlResponse(BaseModel):
    result: str    # merged_pro | merged_free | ok | already_owned | both_pro_support_needed
    a_tier: str    # pro | free | none
    b_tier: str    # pro | free
