"""Stage 6 — read-side endpoints for the Android client.

Mounted at `/api/android` (same prefix as auth/email/payments/iap routers).

Subscription resolution path: Android users may have no Telegram link, so we
derive the Remnawave username from `provisioning.email_to_username(email)`
rather than `tg_id`. The free/paid provisioning code paths use the same
algorithm, so the username stays consistent across signup, IAP, and reads.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from ..config import (
    get_agreement_url,
    get_bot_url,
    get_branding_name,
    get_news_url,
    get_policy_url,
    get_rw_free_id,
    get_rw_pro_id,
    get_support_bot_link,
)
from ..remnawave_client import (
    delete_user_hwid_device,
    get_user_devices_count,
    get_user_hwid_devices,
    resolve_remnawave_user,
)
from . import deps, iap_repo, repo
from .provisioning import email_to_username
from .schemas_data import (
    AndroidDeviceItem,
    AndroidDevicesResponse,
    AndroidLinks,
    AndroidMeResponse,
    AndroidRevokeAllResponse,
    AndroidSessionItem,
    AndroidSessionsResponse,
    AndroidSubscription,
    AndroidUserSummary,
)

router = APIRouter(prefix="/api/android", tags=["android-data"])
logger = logging.getLogger(__name__)


def _links() -> AndroidLinks:
    return AndroidLinks(
        bot_url=get_bot_url(),
        policy_url=get_policy_url(),
        agreement_url=get_agreement_url(),
        news_url=get_news_url(),
        branding_name=get_branding_name(),
        support_bot_link=get_support_bot_link(),
    )


def _resolve_tariff(active_squads: list[str]) -> str:
    pro_id = get_rw_pro_id()
    free_id = get_rw_free_id()
    squads_lower = {s.lower() for s in active_squads}
    if pro_id and pro_id.lower() in squads_lower:
        return "Premium"
    if free_id and free_id.lower() in squads_lower:
        return "Free"
    return "—"


def _days_left(expire_ts: int | None) -> int:
    if expire_ts is None:
        return 0
    diff = round((expire_ts - time.time()) / 86400)
    return max(0, diff)


def _expire_iso(expire_ts: int | None) -> str | None:
    if expire_ts is None:
        return None
    return datetime.fromtimestamp(expire_ts, tz=timezone.utc).isoformat()


def _user_summary(user: repo.UserRow) -> AndroidUserSummary:
    return AndroidUserSummary(
        id=user.id,
        email=user.email,
        email_verified=bool(user.email_verified_at),
        tg_id=user.tg_id,
        language=user.language,
    )


async def _resolve_remnawave_uuid(user: repo.UserRow) -> str | None:
    """Resolve the Remnawave UUID via the fallback chain
    (vless_uuid → email → username-from-email). Going through
    `resolve_remnawave_user` guarantees the same lookup priority as
    `/me` so /devices doesn't disagree with what the user sees on the
    account screen."""
    if not (user.vless_uuid or user.email):
        return None
    rem_user = await resolve_remnawave_user(
        vless_uuid=user.vless_uuid,
        email=user.email,
        username=email_to_username(user.email) if user.email else None,
    )
    if not rem_user:
        return None
    return rem_user.get("uuid")


@router.get("/me", response_model=AndroidMeResponse)
async def get_me(
    user: repo.UserRow = Depends(deps.get_current_user),
) -> AndroidMeResponse:
    links = _links()
    summary = _user_summary(user)

    if not (user.vless_uuid or user.email):
        return AndroidMeResponse(user=summary, subscription=None, links=links)

    rem_user = await resolve_remnawave_user(
        vless_uuid=user.vless_uuid,
        email=user.email,
        username=email_to_username(user.email) if user.email else None,
    )

    if not rem_user:
        return AndroidMeResponse(user=summary, subscription=None, links=links)

    uuid = rem_user.get("uuid")
    devices_count = await get_user_devices_count(uuid) if uuid else 0
    rem_expire_ts = rem_user.get("expire")

    # If a Google Play subscription extends beyond the Remnawave expiry,
    # surface that — the Android UI uses `source` to decide whether to show
    # "manage in Google Play" vs in-bot extend buttons.
    source = "remnawave"
    iap_row = await iap_repo.find_user_active_subscription(user.id)
    if iap_row and iap_row.expiry_time:
        try:
            iap_expire_dt = datetime.fromisoformat(
                iap_row.expiry_time.replace("Z", "+00:00")
            )
            iap_expire_ts = int(iap_expire_dt.timestamp())
            if rem_expire_ts is None or iap_expire_ts > int(rem_expire_ts):
                source = "google_play"
        except (ValueError, TypeError):
            logger.warning(
                "iap row %s has unparseable expiry_time=%r",
                iap_row.id, iap_row.expiry_time,
            )

    subscription = AndroidSubscription(
        tariff=_resolve_tariff(rem_user.get("active_squads", [])),
        status=rem_user.get("status"),
        days_left=_days_left(rem_expire_ts),
        expire_iso=_expire_iso(rem_expire_ts),
        data_limit_gb=rem_user.get("data_limit"),
        traffic_used_gb=rem_user.get("traffic_used", 0),
        devices_count=devices_count,
        subscription_url=rem_user.get("subscription_url"),
        source=source,
    )
    return AndroidMeResponse(user=summary, subscription=subscription, links=links)


@router.get("/devices", response_model=AndroidDevicesResponse)
async def list_devices(
    user: repo.UserRow = Depends(deps.get_current_user),
) -> AndroidDevicesResponse:
    uuid = await _resolve_remnawave_uuid(user)
    if not uuid:
        return AndroidDevicesResponse(total=0, devices=[])
    devices = await get_user_hwid_devices(uuid)
    items = [AndroidDeviceItem(**d) for d in devices]
    return AndroidDevicesResponse(total=len(items), devices=items)


@router.delete("/devices/{hwid}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_device(
    hwid: str,
    user: repo.UserRow = Depends(deps.get_current_user),
) -> None:
    uuid = await _resolve_remnawave_uuid(user)
    if not uuid:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "no_subscription"})
    ok = await delete_user_hwid_device(uuid, hwid)
    if not ok:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail={"code": "device_delete_failed"}
        )
    return None


@router.get("/sessions", response_model=AndroidSessionsResponse)
async def list_sessions(
    user: repo.UserRow = Depends(deps.get_current_user),
) -> AndroidSessionsResponse:
    rows = await repo.list_active_sessions(user.id)
    # The access token does not currently carry family_id (see
    # AccessClaims in security.py), so we cannot mark which row belongs to
    # the calling token. Return None and let the client treat it as unknown.
    items = [
        AndroidSessionItem(
            id=r["id"],
            issued_at=r["issued_at"],
            expires_at=r["expires_at"],
            user_agent=r["user_agent"],
            ip=r["ip"],
            current=None,
        )
        for r in rows
    ]
    return AndroidSessionsResponse(total=len(items), sessions=items)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: int,
    user: repo.UserRow = Depends(deps.get_current_user),
) -> None:
    rows = await repo.list_active_sessions(user.id)
    if not any(r["id"] == session_id for r in rows):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail={"code": "session_not_found"}
        )
    await repo.revoke_refresh_by_id(session_id)
    return None


@router.post("/sessions/revoke-all", response_model=AndroidRevokeAllResponse)
async def revoke_all_sessions(
    user: repo.UserRow = Depends(deps.get_current_user),
) -> AndroidRevokeAllResponse:
    # The current access token continues to work until its 15-min TTL —
    # intentional: revoke-all is for "kill all my refresh families", not
    # "log me out of this device immediately".
    revoked = await repo.revoke_all_user_tokens(user.id)
    return AndroidRevokeAllResponse(revoked=revoked)
