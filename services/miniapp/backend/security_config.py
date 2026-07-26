"""Fail-closed startup checks for the miniapp service.

IAP is optional and may be configured later through Dashboard. Startup only
requires credentials used by the active Android authentication flow.
"""

from __future__ import annotations

from common_db.runtime_config import (
    MIN_ANDROID_JWT_SECRET_BYTES,
    android_jwt_secret_error,
)

from .config import get_android_jwt_secret


def validate_security_config() -> None:
    secret = get_android_jwt_secret()
    validation_error = android_jwt_secret_error(secret)
    if validation_error:
        raise RuntimeError(
            f"{validation_error}; configure a strong random value "
            f"(>= {MIN_ANDROID_JWT_SECRET_BYTES} bytes, e.g. `openssl rand -hex 32`) "
            "in Dashboard or config.yml"
        )
