"""Google Play Developer API client for subscription verification.

Wraps the sync `googleapiclient` SDK in `asyncio.to_thread` so we don't
block the event loop. The SDK is constructed lazily and reused — its
internal `Credentials` object refreshes its token automatically.

Failures (auth, network, 404 from Play) are surfaced as `GooglePlayError`
so the router can return a generic 4xx without leaking internals.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass
from typing import Any

from ..config import (
    get_google_play_package_name,
    get_google_play_service_account_path,
)

logger = logging.getLogger(__name__)

_PLAY_SCOPE = "https://www.googleapis.com/auth/androidpublisher"


class GooglePlayError(Exception):
    pass


@dataclass(frozen=True)
class SubscriptionPurchase:
    """Normalized subset of subscriptionsv2.get response."""
    purchase_token: str
    product_id: str
    subscription_id: str | None
    state: str  # ACTIVE | CANCELED | IN_GRACE_PERIOD | ON_HOLD | PAUSED | EXPIRED | PENDING
    auto_renewing: bool
    start_time: str | None      # RFC3339
    expiry_time: str | None     # RFC3339
    linked_purchase_token: str | None
    order_id: str | None
    acknowledgement_state: str | None
    raw: dict


_SDK_LOCK = threading.Lock()
_SDK_CACHE: dict[str, Any] = {}


def _build_sdk():
    path = get_google_play_service_account_path()
    if not path:
        raise GooglePlayError("google_play_service_account_path is not configured")
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as exc:  # pragma: no cover — runtime dep
        raise GooglePlayError(
            "google-auth / google-api-python-client are not installed"
        ) from exc

    creds = service_account.Credentials.from_service_account_file(
        path, scopes=[_PLAY_SCOPE]
    )
    # cache_discovery=False avoids a noisy warning when /tmp isn't writable.
    return build("androidpublisher", "v3", credentials=creds, cache_discovery=False)


def _get_sdk():
    with _SDK_LOCK:
        sdk = _SDK_CACHE.get("sdk")
        if sdk is None:
            sdk = _build_sdk()
            _SDK_CACHE["sdk"] = sdk
        return sdk


def _normalize_v2(token: str, payload: dict) -> SubscriptionPurchase:
    """Map subscriptionsv2.get response -> SubscriptionPurchase.

    The v2 schema groups offers under `lineItems`; for our single-SKU model
    we read the first lineItem's productId. `subscriptionState` is already
    a string ("SUBSCRIPTION_STATE_ACTIVE" etc.) — strip the prefix.
    """
    line_items = payload.get("lineItems") or []
    line0 = line_items[0] if line_items else {}
    product_id = line0.get("productId") or payload.get("productId") or ""
    expiry_time = line0.get("expiryTime") or payload.get("expiryTime")

    state_raw = payload.get("subscriptionState") or ""
    state = state_raw.replace("SUBSCRIPTION_STATE_", "")

    auto_renewing = bool(line0.get("autoRenewingPlan", {}).get("autoRenewEnabled"))
    return SubscriptionPurchase(
        purchase_token=token,
        product_id=product_id,
        subscription_id=line0.get("offerDetails", {}).get("basePlanId") or product_id,
        state=state,
        auto_renewing=auto_renewing,
        start_time=payload.get("startTime"),
        expiry_time=expiry_time,
        linked_purchase_token=payload.get("linkedPurchaseToken"),
        order_id=payload.get("latestOrderId"),
        acknowledgement_state=payload.get("acknowledgementState"),
        raw=payload,
    )


async def get_subscription(purchase_token: str) -> SubscriptionPurchase:
    """Fetch + normalize subscription state from Play. Raises GooglePlayError."""
    package = get_google_play_package_name()
    if not package:
        raise GooglePlayError("google_play_package_name is not configured")

    def _call() -> dict:
        try:
            from googleapiclient.errors import HttpError
        except ImportError as exc:  # pragma: no cover
            raise GooglePlayError("googleapiclient not installed") from exc

        sdk = _get_sdk()
        try:
            return (
                sdk.purchases()
                .subscriptionsv2()
                .get(packageName=package, token=purchase_token)
                .execute()
            )
        except HttpError as exc:
            status_code = getattr(exc.resp, "status", None)
            if status_code in (400, 410):
                raise GooglePlayError("purchase_invalid") from exc
            if status_code == 404:
                raise GooglePlayError("purchase_not_found") from exc
            logger.error("Play API HTTP %s: %s", status_code, exc)
            raise GooglePlayError(f"play_api_error:{status_code}") from exc
        except Exception as exc:
            logger.exception("Play API unexpected error")
            raise GooglePlayError("play_api_error") from exc

    payload = await asyncio.to_thread(_call)
    return _normalize_v2(purchase_token, payload)


async def acknowledge_subscription(purchase_token: str) -> None:
    """Acknowledge a subscription so Play doesn't auto-refund after 3 days.

    Per docs, Play also returns `acknowledgementState=ACKNOWLEDGED` once the
    in-app billing client acks; we still call this server-side as a safety
    net for clients that fail to ack locally.
    """
    package = get_google_play_package_name()
    if not package:
        raise GooglePlayError("google_play_package_name is not configured")

    def _call() -> None:
        try:
            from googleapiclient.errors import HttpError
        except ImportError as exc:  # pragma: no cover
            raise GooglePlayError("googleapiclient not installed") from exc

        sdk = _get_sdk()
        try:
            (
                sdk.purchases()
                .subscriptions()
                .acknowledge(
                    packageName=package,
                    subscriptionId="",  # required by sig but ignored for v2 tokens
                    token=purchase_token,
                    body={},
                )
                .execute()
            )
        except HttpError as exc:
            status_code = getattr(exc.resp, "status", None)
            # 400 with "already acknowledged" is benign.
            if status_code == 400:
                logger.info("Play ack returned 400 (likely already acked)")
                return
            logger.error("Play ack HTTP %s: %s", status_code, exc)
            raise GooglePlayError(f"play_ack_error:{status_code}") from exc

    await asyncio.to_thread(_call)
