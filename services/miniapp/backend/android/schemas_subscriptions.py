"""Managed subscription API models shared by Android and Desktop clients."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ManagedSubscription(BaseModel):
    id: int
    rw_id: int
    label: str | None = None
    product_key: str | None = None
    source: str
    is_primary: bool
    tariff: str
    status: str | None = None
    days_left: int = 0
    expire_iso: str | None = None
    data_limit_gb: int | None = None
    traffic_used_gb: int = 0
    devices_count: int = 0
    subscription_url: str | None = None


class ManagedSubscriptionsResponse(BaseModel):
    subscriptions: list[ManagedSubscription] = Field(default_factory=list)


class SetPrimaryResponse(BaseModel):
    status: str = "ok"
    subscription_id: int


class AttachSubscriptionRequest(BaseModel):
    context: str = Field(min_length=20, max_length=4096)
    label: str | None = Field(default=None, max_length=100)
    make_primary: bool = False


class AttachSubscriptionResponse(BaseModel):
    status: str = "attached"
    subscription_id: int
    is_primary: bool
