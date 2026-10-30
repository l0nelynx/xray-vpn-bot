"""Bot settings must import on a clean checkout with only an explicit config."""
import json
import os
from pathlib import Path
import subprocess
import sys

import yaml


def test_bot_import_reads_config_path_instead_of_private_config(tmp_path):
    settings = tmp_path / "ci.yml"
    settings.write_text(yaml.safe_dump({
        "token": "123456789:AAFakeTelegramTokenForTestsOnly0123456789",
        "admin_bot_token": "",
        "branding_name": "Изолированный CI config",
    }), encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ, CONFIG_PATH=str(settings))
    environment["PYTHONPATH"] = os.pathsep.join(filter(None, [
        str(root / "services" / "bot"), environment.get("PYTHONPATH", ""),
    ]))
    output = subprocess.check_output([
        sys.executable, "-c",
        "import json; from app.settings import secrets; "
        "print(json.dumps(secrets.get('branding_name')))"
    ], cwd=tmp_path, env=environment, text=True, encoding="utf-8")
    assert json.loads(output) == "Изолированный CI config"


def test_bot_default_config_remains_relative_to_service(monkeypatch, tmp_path):
    from app import settings

    monkeypatch.setattr(settings, "__file__", str(tmp_path / "app" / "settings.py"))
    monkeypatch.delenv("CONFIG_PATH")
    (tmp_path / "config.yml").write_text("branding_name: legacy\n", encoding="utf-8")
    assert settings.load_config()["branding_name"] == "legacy"


def test_bot_explicit_filename_takes_priority_over_environment(monkeypatch, tmp_path):
    from app import settings

    monkeypatch.setattr(settings, "__file__", str(tmp_path / "app" / "settings.py"))
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "missing.yml"))
    (tmp_path / "explicit.yml").write_text("branding_name: explicit\n", encoding="utf-8")
    assert settings.load_config("explicit.yml")["branding_name"] == "explicit"
