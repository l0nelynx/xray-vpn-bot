"""Smoke imports for miniapp backend — catches broken relative imports before deploy.

Uvicorn loads ``miniapp.backend.main``, which pulls routers (incl. menu → bonus_points).
These tests mirror that import chain without starting a server.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_EXAMPLE = _REPO_ROOT / "config-example.yml"

# Same chain as main.py → routers (menu, payments, …) → bonus_points.
_MINIAPP_MODULES = (
    "miniapp.backend.bonus_points",
    "miniapp.backend.credits_delivery",
    "miniapp.backend.routers.menu",
    "miniapp.backend.routers.payments",
    "miniapp.backend.android.payments_router",
    "miniapp.backend.web.web_router",
)


@pytest.fixture(autouse=True)
def _miniapp_config(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _CONFIG_EXAMPLE.is_file():
        pytest.skip("config-example.yml missing")
    monkeypatch.setenv("CONFIG_PATH", str(_CONFIG_EXAMPLE))
    import miniapp.backend.config as cfg

    cfg._config = None


@pytest.mark.parametrize("module_name", _MINIAPP_MODULES)
def test_miniapp_module_imports(module_name: str) -> None:
    importlib.import_module(module_name)


def test_bonus_points_uses_backend_config() -> None:
    """bonus_points.py lives at backend/ root — must import .config, not ..config."""
    import miniapp.backend.bonus_points as bp
    import miniapp.backend.config as cfg

    assert bp.get_config is cfg.get_config


def test_miniapp_main_imports() -> None:
    """Full app module load (same entrypoint as ``uvicorn backend.main:app`` in container)."""
    sys.modules.pop("miniapp.backend.main", None)
    mod = importlib.import_module("miniapp.backend.main")
    assert mod.app is not None
    assert mod.BASE_PATH == "/bot/miniapp"
