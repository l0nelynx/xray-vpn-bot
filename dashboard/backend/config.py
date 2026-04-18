import os
import yaml

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/app/config.yml")

_config = None


def get_config() -> dict:
    global _config
    if _config is None:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            _config = yaml.safe_load(f)
    return _config


def get_dashboard_login() -> str:
    return get_config().get("dashboard_login", "admin")


def get_dashboard_password() -> str:
    return get_config().get("dashboard_password", "admin")


def get_secret_key() -> str:
    return get_config().get("dashboard_secret", "xray-vpn-dashboard-jwt-secret-key")


def get_telemt_server() -> str:
    return get_config().get("telemt_server", "")


def get_telemt_header() -> str:
    return get_config().get("telemt_header", "")


def get_store_url() -> str:
    return get_config().get("store_url", "")


def get_store_api_token() -> str:
    return get_config().get("store_api_token", "")
