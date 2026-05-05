import os
import yaml

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/app/config.yml")

_config = None


def get_config() -> dict:
    global _config
    if _config is None:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            _config = yaml.safe_load(f) or {}
    return _config


def get_bot_token() -> str:
    return get_config().get("token", "")


def get_admin_bot_token() -> str:
    return get_config().get("admin_bot_token", "")


def get_admin_id() -> int | None:
    value = get_config().get("admin_id")
    return int(value) if value is not None else None


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


def get_google_play_rtdn_token() -> str:
    """Shared secret appended as a query string `?token=...` on the Pub/Sub
    push subscription, so the RTDN endpoint can refuse unauthenticated
    notifications. Optional but strongly recommended."""
    return (
        get_config().get("google_play_rtdn_token")
        or os.environ.get("GOOGLE_PLAY_RTDN_TOKEN")
        or ""
    )
