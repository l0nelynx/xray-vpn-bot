"""Bootstrap safe test settings before collection imports application modules.

An autouse fixture is too late: some integration tests import bot handlers at
module scope. Never depend on an operator's ignored config.yml or database.
"""
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    directory = TemporaryDirectory(prefix="xray-vpn-tests-")
    config.add_cleanup(directory.cleanup)
    environment = pytest.MonkeyPatch()
    config.add_cleanup(environment.undo)

    settings = yaml.safe_load(
        (Path(__file__).parent / "config-example.yml").read_text(encoding="utf-8")
    )
    settings.update(
        token="123456789:AAFakeTelegramTokenForTestsOnly0123456789",
        admin_bot_token="",
        crypto_bot_token="",
        logs_id=None,
        dashboard_login="ci-admin",
        dashboard_password="ci-only-admin-password",
        dashboard_secret="ci-only-dashboard-signing-secret-0123456789",
        android_jwt_secret="ci-only-android-signing-secret-0123456789",
        payments_secrets_key="ci-only-payments-encryption-secret-0123456789",
        remnawave_url="https://panel.invalid",
        remnawave_token="ci-only-panel-token",
        smtp_host="",
        smtp_password="",
        fcm_service_account_path="",
    )
    test_config = Path(directory.name) / "config.yml"
    test_config.write_text(yaml.safe_dump(settings, allow_unicode=True), encoding="utf-8")
    environment.setenv("CONFIG_PATH", str(test_config))
    environment.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    environment.setenv("DB_PATH", str(Path(directory.name) / "fallback.sqlite3"))
    # A valid, deliberately unreachable local DSN lets imports validate ARQ
    # settings without contacting an operator's Redis. Tests mock actual I/O.
    environment.setenv("REDIS_URL", "redis://127.0.0.1:1/15")
    environment.setenv("API_HEALTH_ENABLED", "1")
