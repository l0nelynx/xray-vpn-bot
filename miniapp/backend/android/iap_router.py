"""Google Play IAP endpoints for the Android API.

Two paths exist:

1. **Client-driven verify** (`POST /verify`) — called by the Android client
   right after BillingClient hands it a `purchaseToken`. We re-fetch the
   subscription state from Google directly (never trust the client) and
   provision Remnawave on first sight.

2. **Server-driven RTDN** (`POST /rtdn`) — Google's Pub/Sub push delivers
   real-time renewal/cancel/expiry events. Auth is via a shared `?token=`
   query param matching `get_google_play_rtdn_token()`. We always return
   200 OK on benign errors so Pub/Sub doesn't retry indefinitely.

Owner reassignment (a token previously bound to user A appearing under user
B) is rejected — that's almost certainly account abuse. Replays of the same
token by the same user are idempotent.
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from ..config import get_google_play_rtdn_token
from . import deps, iap_repo, repo
from .auth_router import limiter
from .google_play import GooglePlayError, SubscriptionPurchase, acknowledge_subscription, get_subscription

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/android/iap", tags=["android-iap"])


# States in which we consider the entitlement granted. `PENDING` is excluded
# (deferred billing) and so are CANCELED/EXPIRED/ON_HOLD/PAUSED — those drop
# entitlement until the user resolves them in the Play UI.
_GRANTED_STATES = {"ACTIVE", "IN_GRACE_PERIOD"}


# --- Schemas ---------------------------------------------------------------


class SkuInfo(BaseModel):
    product_id: str
    days: int
    squad_id: str
    external_squad_id: str
    display_name: str | None = None


class SkusResponse(BaseModel):
    skus: list[SkuInfo]


class VerifyRequest(BaseModel):
    purchase_token: str = Field(..., min_length=1, max_length=2048)
    product_id: str = Field(..., min_length=1, max_length=200)


class VerifyResponse(BaseModel):
    state: str
    expiry_time: str | None
    auto_renewing: bool
    delivered: bool


# --- Helpers ---------------------------------------------------------------


def _build_tariff_slug(squad_id: str, external_squad_id: str) -> str:
    return f"sid:{squad_id}:esid:{external_squad_id}"


async def _persist_and_maybe_deliver(
    *,
    user_id: int,
    email: str | None,
    sku: iap_repo.SkuRow,
    sub: SubscriptionPurchase,
) -> bool:
    """Upsert the purchase row and, if newly granted, run Remnawave delivery.

    Returns True iff Remnawave delivery ran successfully on this call.
    """
    existing = await iap_repo.find_purchase_by_token(sub.purchase_token)
    if existing is not None and existing.user_id != user_id:
        # Token belongs to a different account — treat as abuse, refuse.
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail={"code": "purchase_owner_mismatch"}
        )

    acked = (sub.acknowledgement_state or "").upper() == "ACKNOWLEDGED"
    await iap_repo.upsert_purchase(
        user_id=user_id,
        product_id=sub.product_id or sku.product_id,
        purchase_token=sub.purchase_token,
        order_id=sub.order_id,
        expiry_time=sub.expiry_time,
        acknowledged=acked,
        state=sub.state,
        auto_renewing=sub.auto_renewing,
        linked_purchase_token=sub.linked_purchase_token,
        subscription_id=sub.subscription_id,
        start_time=sub.start_time,
        raw_payload=sub.raw,
    )

    if sub.state not in _GRANTED_STATES:
        return False

    # Only deliver once per (token, expiry) pair: if the existing row already
    # had this expiry, the user has already been provisioned for this period.
    if existing is not None and existing.expiry_time == sub.expiry_time:
        return False

    delivered = await _deliver_to_remnawave(
        user_id=user_id, email=email, sku=sku, sub=sub
    )

    if delivered and not acked:
        try:
            await acknowledge_subscription(sub.purchase_token)
        except GooglePlayError as exc:
            logger.warning("ack failed for token=...: %s", exc)

    return delivered


async def _deliver_to_remnawave(
    *,
    user_id: int,
    email: str | None,
    sku: iap_repo.SkuRow,
    sub: SubscriptionPurchase,
) -> bool:
    """Bridge into the bot-side delivery helper. Logs but never raises."""
    if not email:
        logger.error("IAP delivery skipped: user %s has no email", user_id)
        return False

    try:
        from app.handlers.android_delivery import deliver_android_paid
    except Exception:  # pragma: no cover — bot package not importable
        logger.exception("IAP delivery: cannot import deliver_android_paid")
        return False

    tariff_slug = _build_tariff_slug(sku.squad_id, sku.external_squad_id)
    # Synthesize a transaction id so delivery has something to log against.
    # Google Play purchases don't flow through the `transactions` table.
    pseudo_tx = f"gplay-{sub.order_id or sub.purchase_token[:24]}-{uuid.uuid4().hex[:8]}"
    try:
        result = await deliver_android_paid(
            transaction_id=pseudo_tx,
            android_user_id=user_id,
            email=email,
            days=sku.days,
            tariff_slug=tariff_slug,
        )
    except Exception:
        logger.exception("IAP delivery raised for user %s", user_id)
        return False
    if (result or {}).get("status") != "success":
        logger.warning("IAP delivery non-success for user %s: %s", user_id, result)
        return False
    return True


# --- Endpoints -------------------------------------------------------------


@router.get("/skus", response_model=SkusResponse)
async def list_skus() -> SkusResponse:
    rows = await iap_repo.list_active_skus()
    return SkusResponse(
        skus=[
            SkuInfo(
                product_id=r.product_id,
                days=r.days,
                squad_id=r.squad_id,
                external_squad_id=r.external_squad_id,
                display_name=r.display_name,
            )
            for r in rows
        ]
    )


@router.post("/verify", response_model=VerifyResponse)
@limiter.limit("10/minute")
async def verify_purchase(
    body: VerifyRequest,
    request: Request,
    user: repo.UserRow = Depends(deps.require_verified_email),
) -> VerifyResponse:
    sku = await iap_repo.get_sku(body.product_id)
    if sku is None or not sku.active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"code": "sku_unknown"}
        )

    try:
        sub = await get_subscription(body.purchase_token)
    except GooglePlayError as exc:
        msg = str(exc)
        if msg in ("purchase_invalid", "purchase_not_found"):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail={"code": msg}
            ) from exc
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail={"code": "play_api_error"}
        ) from exc

    # Defense-in-depth: client claimed `product_id` should match what Play
    # echoes back. Mismatch likely means a tampered request.
    if sub.product_id and sub.product_id != sku.product_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"code": "product_mismatch"}
        )

    delivered = await _persist_and_maybe_deliver(
        user_id=user.id, email=user.email, sku=sku, sub=sub
    )

    return VerifyResponse(
        state=sub.state,
        expiry_time=sub.expiry_time,
        auto_renewing=sub.auto_renewing,
        delivered=delivered,
    )


# --- RTDN (Pub/Sub push) ---------------------------------------------------


def _decode_pubsub_envelope(envelope: dict[str, Any]) -> dict[str, Any] | None:
    """Pub/Sub push wraps the payload as {message: {data: <b64-json>, ...}}.

    Returns the decoded inner JSON dict, or None if malformed (in which case
    the caller should still 200 to avoid retry storms).
    """
    msg = envelope.get("message") or {}
    data_b64 = msg.get("data")
    if not isinstance(data_b64, str):
        return None
    try:
        decoded = base64.b64decode(data_b64).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    try:
        return json.loads(decoded)
    except json.JSONDecodeError:
        return None


@router.post("/rtdn")
async def real_time_developer_notification(
    request: Request,
    token: str | None = Query(default=None),
) -> Response:
    """Google Play Pub/Sub push endpoint.

    https://developer.android.com/google/play/billing/rtdn-reference

    Always returns 200 OK on benign errors — Pub/Sub will retry indefinitely
    on non-2xx, which is bad for transient malformed payloads.
    """
    expected = get_google_play_rtdn_token()
    if expected and token != expected:
        # Wrong shared secret — return 401 so the operator notices in logs;
        # Pub/Sub will retry, but if the secret really is wrong that's the
        # right signal.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad_rtdn_token")

    try:
        envelope = await request.json()
    except Exception:
        logger.warning("RTDN: non-JSON body")
        return Response(status_code=200)

    payload = _decode_pubsub_envelope(envelope)
    if not payload:
        logger.warning("RTDN: undecodable pubsub envelope")
        return Response(status_code=200)

    # Only `subscriptionNotification` is interesting for our subscription
    # model. `testNotification` arrives during Play Console setup; ack 200.
    sub_n = payload.get("subscriptionNotification")
    if not sub_n:
        if "testNotification" in payload:
            logger.info("RTDN: test notification received")
        return Response(status_code=200)

    purchase_token = sub_n.get("purchaseToken")
    notification_type = sub_n.get("notificationType")
    if not purchase_token:
        return Response(status_code=200)

    # Record the latest notification type early so we have telemetry even if
    # the subsequent fetch fails.
    try:
        if isinstance(notification_type, int):
            await iap_repo.update_notification_type(purchase_token, notification_type)
    except Exception:
        logger.exception("RTDN: failed to update notification_type")

    existing = await iap_repo.find_purchase_by_token(purchase_token)
    if existing is None:
        # We've never seen this token — happens if RTDN beats the client's
        # /verify call. Skip; the client's /verify will catch up shortly.
        logger.info("RTDN for unknown token (verify race?)")
        return Response(status_code=200)

    sku = await iap_repo.get_sku(existing.product_id)
    if sku is None:
        logger.error("RTDN: no SKU configured for product=%s", existing.product_id)
        return Response(status_code=200)

    try:
        sub = await get_subscription(purchase_token)
    except GooglePlayError as exc:
        logger.warning("RTDN: Play fetch failed: %s", exc)
        return Response(status_code=200)

    user = await repo.find_user_by_id(existing.user_id)
    if user is None:
        logger.error("RTDN: user %s no longer exists", existing.user_id)
        return Response(status_code=200)

    try:
        await _persist_and_maybe_deliver(
            user_id=existing.user_id, email=user.email, sku=sku, sub=sub
        )
    except HTTPException as exc:
        # Owner mismatch in RTDN context shouldn't happen (token already
        # bound), but log defensively rather than 5xxing back to Pub/Sub.
        logger.error("RTDN: persist refused: %s", exc.detail)

    return Response(status_code=200)
