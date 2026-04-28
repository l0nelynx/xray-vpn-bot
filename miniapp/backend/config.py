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
