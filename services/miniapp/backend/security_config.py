"""Fail-closed startup checks for the miniapp service.

Mirrors the dashboard's ``validate_security_config()`` pattern: refuse to boot
when credentials that protect JWT issuance or Google Play RTDN are missing or
still at documented placeholder values.
"""

from __future__ import annotations

from common_db.runtime_config import (
    MIN_ANDROID_JWT_SECRET_BYTES,
    android_jwt_secret_error,
)

from .config import (
    get_android_jwt_secret,
    get_google_play_package_name,
    get_google_play_rtdn_token,
)


def validate_security_config() -> None:
    secret = get_android_jwt_secret()
    validation_error = android_jwt_secret_error(secret)
    if validation_error:
        raise RuntimeError(
            f"{validation_error}; configure a strong random value "
            f"(>= {MIN_ANDROID_JWT_SECRET_BYTES} bytes, e.g. `openssl rand -hex 32`) "
            "in Dashboard or config.yml"
        )

    if get_google_play_package_name() and not get_google_play_rtdn_token():
        raise RuntimeError(
            "google_play_package_name is set but google_play_rtdn_token is empty — "
            "configure a shared secret for the RTDN push endpoint or disable IAP "
            "by clearing google_play_package_name"
        )
