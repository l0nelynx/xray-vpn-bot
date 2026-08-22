import os
import yaml

from common_db.runtime_config import DualSourceConfig, set_crypto_secret

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/app/config.yml")

_yaml_config = None
_config: DualSourceConfig | None = None


def _load_yaml() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
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
    get_config()
    assert _yaml_config is not None
    return _yaml_config


# Legacy built-in default — now rejected at startup. Kept as a constant so the
# validator can detect and refuse a config that still ships it.
INSECURE_DASHBOARD_SECRET = "xray-vpn-dashboard-jwt-secret-key"


def get_dashboard_login() -> str:
    return get_config().get("dashboard_login", "admin")


def get_dashboard_password() -> str:
    # No insecure default — an unset password must fail closed at startup,
    # never silently fall back to a guessable value.
    return get_config().get("dashboard_password", "") or ""


def get_secret_key() -> str:
    # No insecure default — an unset/weak secret would let anyone forge admin
    # JWTs. validate_security_config() refuses to boot in that case.
    return get_config().get("dashboard_secret", "") or ""


def get_payments_secrets_key() -> str:
    """Key used to encrypt payment_integrations blobs.

    Prefer dedicated ``payments_secrets_key``; fall back to dashboard_secret
    during the dual-source period so existing installs work without a new key.
    """
    return (
        get_config().get("payments_secrets_key")
        or get_secret_key()
        or ""
    )


def get_expose_api_docs() -> bool:
    """Whether to serve Swagger UI + openapi.json. Off by default so the admin
    API surface isn't publicly enumerable. Enable via config `expose_api_docs:
    true` or env `EXPOSE_API_DOCS=1` for debugging."""
    env = os.environ.get("EXPOSE_API_DOCS")
    if env is not None:
        return env.strip().lower() in ("1", "true", "yes", "on")
    return bool(get_config().get("expose_api_docs", False))


def get_support_uploads_dir() -> str:
    """Filesystem directory for support-ticket image attachments.

    Shared, read-write bind mount with the `miniapp` container (see
    docker-compose.yml) — this service needs to read images the user
    uploaded via miniapp, and miniapp needs to read images the admin
    uploads here. Default matches the mount path in compose.
    """
    return get_config().get("support_uploads_dir") or "/app/support_uploads"


def get_telemt_server() -> str:
    return get_config().get("telemt_server", "")


def get_telemt_header() -> str:
    return get_config().get("telemt_header", "")


def get_store_url() -> str:
    return get_config().get("store_url", "")


def get_store_api_token() -> str:
    return get_config().get("store_api_token", "")


def get_bot_token() -> str:
    return get_config().get("token", "")


def get_news_id():
    return get_config().get("news_id")


def get_news_url() -> str:
    return get_config().get("news_url", "")


def get_remnawave_url() -> str:
    return get_config().get("remnawave_url", "")


def get_remnawave_token() -> str:
    return get_config().get("remnawave_token", "")


def get_rw_pro_id() -> str:
    return get_config().get("rw_pro_id", "")


def get_rw_free_id() -> str:
    return get_config().get("rw_free_id", "")


def get_redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://redis:6379/0")


def get_fcm_project_id() -> str:
    return (get_config().get("fcm_project_id") or "").strip()


def get_fcm_service_account_path() -> str:
    return (get_config().get("fcm_service_account_path") or "").strip()


def get_fcm_sa_json() -> str:
    """Service-account JSON content from Dashboard integrations (preferred)."""
    return (get_config().get("fcm_sa_json") or "").strip()
