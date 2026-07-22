"""Inventory of config.yml keys for the dual-source migration.

BOOTSTRAP_KEYS stay file-only (infra / process identity).
RUNTIME_KEYS may be overridden by ``app_runtime_settings`` when present in DB.
PAYMENT_PROVIDERS map registry names → YAML credential fields.
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
    "rw_free_id",
    "rw_pro_id",
    "rw_ext_free_id",
    "rw_ext_pro_id",
    "subscription_url",
    "dashboard_login",
    "dashboard_password",
    "dashboard_secret",
    "payments_secrets_key",
    "android_jwt_secret",
    "android_access_ttl",
    "android_refresh_ttl",
    "android_jwt_issuer",
    "uvicorn_host",
    "uvicorn_port",
    "expose_api_docs",
    "log_level",
    "smtp_host",
    "smtp_port",
    "smtp_user",
    "smtp_password",
    "smtp_from",
    "smtp_use_tls",
    "email_code_ttl",
    "email_code_max_attempts",
    "telemt_server",
    "telemt_header",
    "store_url",
    "store_api_token",
    "google_play_package_name",
    "google_play_service_account_path",
    "google_play_rtdn_token",
    "fcm_project_id",
    "fcm_service_account_path",
    "web_allowed_origins",
    "tg_client_secret",
    "support_token",
    "support_uploads_dir",
    "connect_app_config_path",
    "stars_price",
    "crypto_price",
    "sbp_price",
    "discount",
    "star_rub_rate",
    "usd_rub_rate",
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
})

DEFAULT_MAINTENANCE: dict[str, Any] = {
    "enabled": False,
    "title": "Технические работы",
    "text": "Сервис временно недоступен. Попробуйте позже.",
}

DEFAULT_RUNTIME_CONFIG: dict[str, Any] = {
    "maintenance": dict(DEFAULT_MAINTENANCE),
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
