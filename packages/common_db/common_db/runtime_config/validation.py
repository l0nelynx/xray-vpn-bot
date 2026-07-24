"""Validation shared by runtime-config writers and consumers."""
from __future__ import annotations

MIN_ANDROID_JWT_SECRET_BYTES = 32

INSECURE_ANDROID_JWT_SECRETS = frozenset(
    {
        "",
        "change-me-android-jwt-secret",
    }
)


def android_jwt_secret_error(value: object) -> str | None:
    """Return a user-facing validation error for an Android JWT secret."""
    secret = value if isinstance(value, str) else ""
    if not secret or not secret.strip():
        return "android_jwt_secret is required when the Android integration is enabled"
    if secret in INSECURE_ANDROID_JWT_SECRETS:
        return "android_jwt_secret still uses the built-in insecure placeholder"
    if len(secret.encode("utf-8")) < MIN_ANDROID_JWT_SECRET_BYTES:
        return (
            "android_jwt_secret must be at least "
            f"{MIN_ANDROID_JWT_SECRET_BYTES} bytes (HS256)"
        )
    return None


def resolve_android_jwt_secret(
    *,
    submitted: object | None,
    existing: object | None,
    yaml_fallback: object | None,
) -> object | None:
    """Resolve a Dashboard save without hiding an explicit bad new value."""
    if submitted is not None:
        return submitted
    if android_jwt_secret_error(existing) is None:
        return existing
    return yaml_fallback
