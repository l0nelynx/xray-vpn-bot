"""FCM HTTP v1 sender for Dashboard push campaigns.

Uses a Google service-account JSON (scope firebase.messaging) and httpx —
same pattern as the miniapp Google Play client, without the firebase-admin SDK.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any

import httpx

from .config import (
    get_fcm_project_id,
    get_fcm_sa_json,
    get_fcm_service_account_path,
)

logger = logging.getLogger(__name__)

_FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_DEAD_TOKEN_ERRORS = frozenset({
    "UNREGISTERED",
    "INVALID_ARGUMENT",
    "NOT_FOUND",
})

_CREDS_LOCK = threading.Lock()
_CREDS_CACHE: dict[str, Any] = {}


class FcmError(Exception):
    """Raised when FCM is misconfigured or the request cannot be sent."""


@dataclass(frozen=True)
class FcmSendResult:
    ok: bool
    error_code: str | None = None
    error_message: str | None = None
    dead_token: bool = False


def fcm_configured() -> bool:
    return bool(get_fcm_project_id() and (get_fcm_sa_json() or get_fcm_service_account_path()))


def _get_credentials():
    sa_json = get_fcm_sa_json()
    path = get_fcm_service_account_path()
    cache_key = f"json:{hash(sa_json)}" if sa_json else f"path:{path}"
    if not sa_json and not path:
        raise FcmError("FCM service account is not configured (JSON or path)")
    with _CREDS_LOCK:
        cached = _CREDS_CACHE.get(cache_key)
        if cached is not None:
            return cached
        try:
            from google.oauth2 import service_account
        except ImportError as exc:  # pragma: no cover
            raise FcmError(
                "google-auth is required for FCM (pip install google-auth)"
            ) from exc
        if sa_json:
            import json as _json

            try:
                info = _json.loads(sa_json)
            except _json.JSONDecodeError as exc:
                raise FcmError("fcm_sa_json is not valid JSON") from exc
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=[_FCM_SCOPE]
            )
        else:
            creds = service_account.Credentials.from_service_account_file(
                path, scopes=[_FCM_SCOPE]
            )
        _CREDS_CACHE[cache_key] = creds
        return creds


def _access_token() -> str:
    creds = _get_credentials()
    if not creds.valid:
        from google.auth.transport.requests import Request as GoogleRequest

        creds.refresh(GoogleRequest())
    if not creds.token:
        raise FcmError("Failed to obtain FCM access token")
    return creds.token


def _stringify_data(data: dict | None) -> dict[str, str]:
    if not data:
        return {}
    out: dict[str, str] = {}
    for key, value in data.items():
        if value is None:
            continue
        out[str(key)] = value if isinstance(value, str) else str(value)
    return out


async def send_notification(
    *,
    token: str,
    title: str,
    body: str,
    data: dict | None = None,
) -> FcmSendResult:
    """Send one FCM notification to a device token."""
    project_id = get_fcm_project_id()
    if not project_id:
        raise FcmError("fcm_project_id is not configured")
    if not token:
        return FcmSendResult(
            ok=False, error_code="INVALID_ARGUMENT", error_message="empty token",
            dead_token=True,
        )

    message: dict[str, Any] = {
        "token": token,
        "notification": {"title": title, "body": body},
    }
    data_payload = _stringify_data(data)
    if data_payload:
        message["data"] = data_payload

    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    try:
        bearer = _access_token()
    except FcmError:
        raise
    except Exception as exc:
        raise FcmError(f"FCM credentials error: {exc}") from exc

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {bearer}",
                    "Content-Type": "application/json",
                },
                json={"message": message},
            )
    except httpx.HTTPError as exc:
        logger.warning("FCM network error for token …%s: %s", token[-8:], exc)
        return FcmSendResult(
            ok=False, error_code="NETWORK", error_message=str(exc)[:500]
        )

    if resp.status_code in (200, 201):
        return FcmSendResult(ok=True)

    error_code = None
    error_message = None
    try:
        payload = resp.json()
        err = (payload.get("error") or {}) if isinstance(payload, dict) else {}
        error_message = (err.get("message") or resp.text)[:500]
        details = err.get("details") or []
        for detail in details:
            if isinstance(detail, dict) and detail.get("errorCode"):
                error_code = str(detail["errorCode"])
                break
        if not error_code and err.get("status"):
            error_code = str(err["status"])
    except Exception:
        error_message = (resp.text or "")[:500]

    dead = bool(error_code and error_code.upper() in _DEAD_TOKEN_ERRORS)
    # Some INVALID_ARGUMENT responses are payload issues, not dead tokens;
    # treat UNREGISTERED / NOT_FOUND as always dead; INVALID_ARGUMENT only
    # when the message mentions the registration token.
    if error_code and error_code.upper() == "INVALID_ARGUMENT":
        msg_l = (error_message or "").lower()
        dead = "token" in msg_l or "registration" in msg_l

    logger.info(
        "FCM send failed status=%s code=%s token=…%s msg=%s",
        resp.status_code,
        error_code,
        token[-8:],
        error_message,
    )
    return FcmSendResult(
        ok=False,
        error_code=error_code,
        error_message=error_message,
        dead_token=dead,
    )
