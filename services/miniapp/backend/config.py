import logging
import os
import yaml

from common_db.runtime_config import DualSourceConfig, set_crypto_secret

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/app/config.yml")

_LOG_LEVEL_ALIASES = {
    "normal": logging.INFO,
    "info": logging.INFO,
    "debug": logging.DEBUG,
    "warning": logging.WARNING,
    "warn": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

_yaml_config = None
_config: DualSourceConfig | None = None


def _load_yaml() -> dict:
    # Tests and local launchers may set CONFIG_PATH after this module was first
    # imported by a router. Resolve the environment at load time rather than
    # freezing `/app/config.yml` at import time.
    path = os.environ.get("CONFIG_PATH", CONFIG_PATH)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_config() -> DualSourceConfig:
    global _yaml_config, _config
    if _config is None:
        _yaml_config = _load_yaml()
        set_crypto_secret(
            str(
                _yaml_config.get("payments_secrets_key")
                or _yaml_config.get("dashboard_secret")
                or ""
            )
        )
        _config = DualSourceConfig(_yaml_config)
    return _config


def get_yaml_config() -> dict:
    """Raw YAML dict (no DB overlay) — used for Dashboard import / source display."""
    get_config()
    assert _yaml_config is not None
    return _yaml_config


def get_log_level() -> int:
    """Resolve logging level from config.yml ``log_level`` (default: ``normal``).

    Accepted values: normal, info, debug, warning, error, critical.
    Env ``LOG_LEVEL`` is a fallback for backwards compatibility.
    """
    raw = get_config().get("log_level") or os.environ.get("LOG_LEVEL") or "normal"
    key = str(raw).strip().lower()
    if key in _LOG_LEVEL_ALIASES:
        return _LOG_LEVEL_ALIASES[key]
    # Allow standard logging level names (e.g. INFO) as a last resort.
    level = getattr(logging, key.upper(), None)
    if isinstance(level, int):
        return level
    return logging.INFO


def get_bot_token() -> str:
    return get_config().get("token", "")


def get_admin_bot_token() -> str:
    return get_config().get("admin_bot_token", "")


def get_admin_id() -> int | None:
    value = get_config().get("admin_id")
    return int(value) if value is not None else None


def get_logs_id() -> int | None:
    """Chat ID for event log notifications (Android API events, invoices,
    deliveries, etc.). When unset → notifications are silently skipped."""
    value = get_config().get("logs_id")
    try:
        return int(value) if value is not None and str(value).strip() != "" else None
    except (TypeError, ValueError):
        return None


def get_bot_url() -> str:
    return get_config().get("bot_url", "")


def get_policy_url() -> str:
    return get_config().get("policy_url", "")


def get_agreement_url() -> str:
    return get_config().get("agreement_url", "")


def get_branding_name() -> str:
    return get_config().get("branding_name", "") or ""


def get_support_bot_link() -> str:
    cfg = get_config()
    link = cfg.get("support_bot_link") or ""
    if link:
        return link
    bot_id = (cfg.get("support_bot_id") or "").lstrip("@").strip()
    return f"https://t.me/{bot_id}" if bot_id else ""


def get_remnawave_url() -> str:
    return get_config().get("remnawave_url", "")


def get_subscription_host() -> str:
    """Host portion of the Remnawave subscription URL (no scheme, no path).

    Read from config.yml `subscription_url`. Used by android-link `by_url` to
    validate that incoming URLs point at our own subscription host.
    """
    return (get_config().get("subscription_url") or "").strip()


def get_remnawave_token() -> str:
    return get_config().get("remnawave_token", "")


def get_rw_pro_id() -> str:
    return get_config().get("rw_pro_id", "")


def get_rw_free_id() -> str:
    return get_config().get("rw_free_id", "")


def get_apay_id() -> int | None:
    value = get_config().get("apay_id")
    return int(value) if value is not None else None


def get_apay_secret() -> str:
    return get_config().get("apay_secret", "")


# Wire the shared Remnawave client to the miniapp's config. The module-level
# helpers in `remnawave_client.api` lazily configure the default client from
# this provider on first use (replaces the old miniapp.backend.remnawave_client
# shim).
import remnawave_client as _remna

_remna.set_config_provider(lambda: {
    "base_url": get_remnawave_url(),
    "token": get_remnawave_token(),
    "free_squad_id": get_rw_free_id(),
})

# Wire the shared payments package to the miniapp's config (replaces the local
# miniapp.backend.payments package).
import payments as _payments
from common_db.runtime_config import payments_config_kwargs

_payments.set_config_provider(lambda: _payments.PaymentsConfig(**payments_config_kwargs(get_config())))


def get_apay_api_url() -> str:
    return get_config().get("apay_api_url", "")


def get_platega_merchant_id() -> str:
    return get_config().get("platega_merchant_id", "") or ""


def get_platega_api_key() -> str:
    return get_config().get("platega_api_key", "") or ""


def get_platega_url() -> str:
    return (get_config().get("platega_url") or "https://app.platega.io").rstrip("/")


def get_platega_payment_method() -> int:
    value = get_config().get("platega_payment_method", 2)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 2


def get_paritypay_shop_id() -> str:
    return get_config().get("paritypay_shop_id", "") or ""


def get_paritypay_secret_1() -> str:
    return get_config().get("paritypay_secret_1", "") or ""


def get_paritypay_secret_2() -> str:
    return get_config().get("paritypay_secret_2", "") or ""


def get_paritypay_url() -> str:
    return (get_config().get("paritypay_url") or "https://api.paritypay.ru").rstrip("/")


def get_paritypay_webhook() -> str:
    return get_config().get("paritypay_webhook", "") or ""


def get_paritypay_service() -> str:
    return get_config().get("paritypay_service", "sbp") or "sbp"


def get_crystal_login() -> str:
    return get_config().get("crystal_login", "")


def get_crystal_secret() -> str:
    return get_config().get("crystal_secret", "")


def get_crystal_salt() -> str:
    return get_config().get("crystal_salt", "")


def get_crystal_webhook() -> str:
    return get_config().get("crystal_webhook", "")


def get_crypto_bot_token() -> str:
    return get_config().get("crypto_bot_token", "")


def get_news_url() -> str:
    return get_config().get("news_url", "")


def get_news_id() -> int | None:
    value = get_config().get("news_id")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def get_free_days() -> int:
    return int(get_config().get("free_days", 30) or 30)


def get_free_traffic() -> int:
    return int(get_config().get("free_traffic", 10) or 10)


def get_rw_ext_free_id() -> str:
    return get_config().get("rw_ext_free_id", "")


def get_telemt_server() -> str:
    return (get_config().get("telemt_server") or "").rstrip("/")


def get_telemt_header() -> str:
    return get_config().get("telemt_header", "") or ""


# --- Android API ---

def get_android_jwt_secret() -> str:
    """HS256 signing key for Android-API JWTs.

    Read from config.yml `android_jwt_secret` or env `ANDROID_JWT_SECRET`.
    The service refuses to issue tokens if neither is set.
    """
    return (
        get_config().get("android_jwt_secret")
        or os.environ.get("ANDROID_JWT_SECRET")
        or ""
    )


def get_android_access_ttl_seconds() -> int:
    return int(get_config().get("android_access_ttl", 15 * 60) or 15 * 60)


def get_android_refresh_ttl_seconds() -> int:
    return int(get_config().get("android_refresh_ttl", 60 * 24 * 3600) or 60 * 24 * 3600)


def get_android_jwt_issuer() -> str:
    return get_config().get("android_jwt_issuer", "xray-vpn-bot") or "xray-vpn-bot"


# --- SMTP (Android API email codes) ---

def get_smtp_host() -> str:
    return get_config().get("smtp_host", "") or ""


def get_smtp_port() -> int:
    return int(get_config().get("smtp_port", 587) or 587)


def get_smtp_user() -> str:
    return get_config().get("smtp_user", "") or ""


def get_smtp_password() -> str:
    return get_config().get("smtp_password", "") or ""


def get_smtp_from() -> str:
    """Sender address. Falls back to smtp_user."""
    return get_config().get("smtp_from") or get_smtp_user()


def get_smtp_use_tls() -> bool:
    """Implicit TLS (port 465). STARTTLS is auto-detected on 587/25."""
    value = get_config().get("smtp_use_tls")
    if value is None:
        return get_smtp_port() == 465
    return bool(value)


def get_email_code_ttl_seconds() -> int:
    return int(get_config().get("email_code_ttl", 15 * 60) or 15 * 60)


def get_email_code_max_attempts() -> int:
    return int(get_config().get("email_code_max_attempts", 5) or 5)


def get_email_denied_domains() -> list[str]:
    """Extra email domains rejected at registration (merged with built-in list).

    Config key: ``email_denied_domains`` — YAML list or comma-separated string.
    """
    raw = get_config().get("email_denied_domains") or []
    if isinstance(raw, str):
        return [d.strip().lower() for d in raw.split(",") if d.strip()]
    return [str(d).strip().lower() for d in raw if d]


# --- Web portal ------------------------------------------------------------

def get_tg_client_secret() -> str:
    """Client Secret issued by BotFather for Telegram OpenID Connect (Login 2.0).

    Config key: tg_client_secret.  Required for the web portal "Sign in with
    Telegram" button; leave empty to disable the feature.
    """
    return get_config().get("tg_client_secret", "") or ""


def get_web_allowed_origins() -> list[str]:
    """CORS allowed origins for the external web portal frontend.

    Config key: web_allowed_origins — a YAML list or comma-separated string.
    Example:
      web_allowed_origins:
        - https://web.yourdomain.com
        - https://yourrepo.vercel.app
    """
    raw = get_config().get("web_allowed_origins") or []
    if isinstance(raw, str):
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [str(o).strip() for o in raw if o]


def get_subscription_page_oauth_redirect_uris() -> list[str]:
    """Exact OAuth callback allowlist for the subscription-page BFF."""
    raw = (
        get_config().get("subscription_page_oauth_redirect_uris")
        or os.environ.get("SUBSCRIPTION_PAGE_OAUTH_REDIRECT_URIS")
        or []
    )
    if isinstance(raw, str):
        return [value.strip() for value in raw.split(",") if value.strip()]
    return [str(value).strip() for value in raw if value]


def get_web_portal_url() -> str:
    return (
        get_config().get("web_portal_url")
        or os.environ.get("WEB_PORTAL_URL")
        or ""
    ).rstrip("/")


def get_web_id() -> int | None:
    """Chat ID for web-portal notifications (partnership inquiries submitted
    from the public landing page). When unset → notifications are silently
    skipped. Mirrors `logs_id` but targets a separate chat."""
    value = get_config().get("web_id")
    try:
        return int(value) if value is not None and str(value).strip() != "" else None
    except (TypeError, ValueError):
        return None


def get_expose_api_docs() -> bool:
    """Whether to serve the interactive Swagger UI and openapi.json.

    Off by default: in production the schema exposes the full API surface
    (including admin/IAP endpoints) to anyone. Enable temporarily for debugging
    via config `expose_api_docs: true` or env `EXPOSE_API_DOCS=1`.
    """
    env = os.environ.get("EXPOSE_API_DOCS")
    if env is not None:
        return env.strip().lower() in ("1", "true", "yes", "on")
    return bool(get_config().get("expose_api_docs", False))


def get_connect_app_config_path() -> str:
    """Path to an operator override for the /connect-page app catalog.

    If the file exists it is served by `GET /api/connect/app-config` instead of
    the bundled default; mount it like `config.yml` (see docs/connect-page.md).
    Default `/app/app-config.json`; env `CONNECT_APP_CONFIG_PATH` overrides.
    """
    return (
        os.environ.get("CONNECT_APP_CONFIG_PATH")
        or get_config().get("connect_app_config_path")
        or "/app/app-config.json"
    )


def get_support_uploads_dir() -> str:
    """Filesystem directory for support-ticket image attachments.

    Shared, read-write bind mount with the `dashboard` container (see
    docker-compose.yml) — the admin needs to read images the user uploaded
    here, and this service needs to read images the admin uploaded there.
    Default matches the mount path in compose.
    """
    return get_config().get("support_uploads_dir") or "/app/support_uploads"


# --- Google Play IAP -------------------------------------------------------

def get_google_play_package_name() -> str:
    """Application ID, e.g. `com.example.xrayvpn`. Required for the
    Google Play Developer API path. Empty string disables IAP entirely."""
    return get_config().get("google_play_package_name", "") or ""


def get_google_play_service_account_path() -> str:
    """Filesystem path to the service-account JSON granted access to the
    Play Developer API for our package. Mounted into the container."""
    return (
        get_config().get("google_play_service_account_path")
        or os.environ.get("GOOGLE_PLAY_SERVICE_ACCOUNT_PATH")
        or ""
    )


def get_google_play_sa_json() -> str:
    """Service-account JSON content from Dashboard integrations (preferred)."""
    return (get_config().get("google_play_sa_json") or "").strip()


def get_google_play_rtdn_token() -> str:
    """Shared secret appended as a query string `?token=...` on the Pub/Sub
    push subscription, so the RTDN endpoint can refuse unauthenticated
    notifications. Optional but strongly recommended."""
    return (
        get_config().get("google_play_rtdn_token")
        or os.environ.get("GOOGLE_PLAY_RTDN_TOKEN")
        or ""
    )
