"""Fail-closed startup checks for the miniapp service.

Mirrors the dashboard's ``validate_security_config()`` pattern: refuse to boot
when credentials that protect JWT issuance or Google Play RTDN are missing or
still at documented placeholder values.
"""

from __future__ import annotations

from .config import (
    get_android_jwt_secret,
    get_google_play_package_name,
    get_google_play_rtdn_token,
)

MIN_SECRET_BYTES = 32

INSECURE_ANDROID_JWT_SECRETS = frozenset({
    "",
    "change-me-android-jwt-secret",
})


def validate_security_config() -> None:
    secret = get_android_jwt_secret()
    if not secret:
        raise RuntimeError(
            "android_jwt_secret is not set — add a strong random value "
            f"(>= {MIN_SECRET_BYTES} bytes) to config.yml "
            "(or set env ANDROID_JWT_SECRET)"
        )
    if secret in INSECURE_ANDROID_JWT_SECRETS:
        raise RuntimeError(
            "android_jwt_secret still uses the built-in insecure placeholder — "
            "change it in config.yml (e.g. `openssl rand -hex 32`)"
        )
    if len(secret.encode("utf-8")) < MIN_SECRET_BYTES:
        raise RuntimeError(
            f"android_jwt_secret must be at least {MIN_SECRET_BYTES} bytes (HS256)"
        )

    if get_google_play_package_name() and not get_google_play_rtdn_token():
        raise RuntimeError(
            "google_play_package_name is set but google_play_rtdn_token is empty — "
            "configure a shared secret for the RTDN push endpoint or disable IAP "
            "by clearing google_play_package_name"
        )
