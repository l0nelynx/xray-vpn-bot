"""Inventory of config.yml keys for the dual-source migration.

BOOTSTRAP_KEYS stay file-only (infra / process identity).
RUNTIME_KEYS may be overridden by ``app_runtime_settings`` when present in DB.
PAYMENT_PROVIDERS / INTEGRATION_PROVIDERS map registry names → credential fields.
"""
from __future__ import annotations

from typing import Any

# Still read only from config.yml / env (not moved in this release).
BOOTSTRAP_KEYS: frozenset[str] = frozenset({
    "token",
    "admin_bot_token",
    "admin_id",
    "bot_url",
    "miniapp_url",
    "miniapp_tg_url",
    "remnawave_url",
    "remnawave_token",
    "remnawave_webhook_secret",
    "dashboard_login",
    "dashboard_password",
    "dashboard_secret",
    "payments_secrets_key",
    "uvicorn_host",
    "uvicorn_port",
    "expose_api_docs",
    "log_level",
    # SA file paths remain bootstrap fallback until JSON is saved in Dashboard.
    "google_play_service_account_path",
    "fcm_service_account_path",
    "support_token",
    "support_uploads_dir",
    "connect_app_config_path",
})

# Preferred: Dashboard Runtime Settings. YAML remains fallback until set in DB.
RUNTIME_KEYS: frozenset[str] = frozenset({
    "branding_name",
    "news_id",
    "news_url",
    "support_bot_id",
    "agreement_url",
    "policy_url",
    "logs_id",
    "web_id",
    "admin_logs_length",
    "free_days",
    "free_traffic",
    # Android (non-secret)
    "android_access_ttl",
    "android_refresh_ttl",
    "android_jwt_issuer",
    # SMTP / email codes (non-secret)
    "smtp_host",
    "smtp_port",
    "smtp_user",
    "smtp_from",
    "smtp_use_tls",
    "email_code_ttl",
    "email_code_max_attempts",
    # Telemt connection URL
    "telemt_server",
    # Store / FCM / Google Play scalars
    "store_url",
    "fcm_project_id",
    "google_play_package_name",
    # Web portal
    "web_allowed_origins",
    # Remnawave product IDs
    "rw_free_id",
    "rw_pro_id",
    "rw_ext_free_id",
    "rw_ext_pro_id",
    "subscription_url",
    "api_health_alerts",
})

DEFAULT_MAINTENANCE: dict[str, Any] = {
    "enabled": False,
    "title": "Технические работы",
    "text": "Сервис временно недоступен. Попробуйте позже.",
}

DEFAULT_RUNTIME_CONFIG: dict[str, Any] = {
    "maintenance": dict(DEFAULT_MAINTENANCE),
    "android_access_ttl": 900,
    "android_refresh_ttl": 5184000,
    "android_jwt_issuer": "xray-vpn-bot",
    "smtp_port": 587,
    "smtp_use_tls": False,
    "email_code_ttl": 900,
    "email_code_max_attempts": 5,
    "api_health_alerts": {
        "enabled": True,
        "server_error_threshold": 20,
        "latency_p95_ms": 2000,
        "latency_min_requests": 20,
        "health_failures": 3,
        "cooldown_minutes": 30,
    },
}

# provider -> list of PaymentsConfig / YAML field names
PAYMENT_PROVIDER_FIELDS: dict[str, tuple[str, ...]] = {
    "crypto": ("crypto_bot_token",),
    "crystal": ("crystal_login", "crystal_secret", "crystal_salt", "crystal_webhook"),
    "apay": ("apay_id", "apay_secret", "apay_api_url"),
    "platega": (
        "platega_merchant_id",
        "platega_api_key",
        "platega_url",
        "platega_payment_method",
    ),
    "paritypay": (
        "paritypay_shop_id",
        "paritypay_secret_1",
        "paritypay_secret_2",
        "paritypay_url",
        "paritypay_webhook",
        "paritypay_service",
    ),
}

# Fields that should be masked in API responses (not echoed back).
PAYMENT_SECRET_FIELDS: frozenset[str] = frozenset({
    "crypto_bot_token",
    "crystal_secret",
    "crystal_salt",
    "apay_secret",
    "platega_api_key",
    "paritypay_secret_1",
    "paritypay_secret_2",
})

# Encrypted service integrations (SMTP password, Android JWT, Telemt header, …).
# Non-secret siblings live in RUNTIME_KEYS; secrets are stored here.
INTEGRATION_PROVIDER_FIELDS: dict[str, tuple[str, ...]] = {
    "smtp": ("smtp_password",),
    "android": ("android_jwt_secret",),
    "telemt": ("telemt_header",),
    "store": ("store_api_token",),
    "fcm": ("fcm_sa_json",),
    "google_play": ("google_play_rtdn_token", "google_play_sa_json"),
    "web": ("tg_client_secret",),
}

INTEGRATION_SECRET_FIELDS: frozenset[str] = frozenset({
    "smtp_password",
    "android_jwt_secret",
    "telemt_header",
    "store_api_token",
    "fcm_sa_json",
    "google_play_rtdn_token",
    "google_play_sa_json",
    "tg_client_secret",
})

# Empty string when clearing a disabled integration field.
INTEGRATION_EMPTY_DEFAULTS: dict[str, Any] = {
    "smtp_password": "",
    "android_jwt_secret": "",
    "telemt_header": "",
    "store_api_token": "",
    "fcm_sa_json": "",
    "google_play_rtdn_token": "",
    "google_play_sa_json": "",
    "tg_client_secret": "",
}
