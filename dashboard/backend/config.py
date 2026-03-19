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
