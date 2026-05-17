"""Step 5 drift guard: app.database.models shim must re-export common_db.

Unlike dashboard/miniapp, app.database.models is a *partial* shim — it
still owns the runtime engine/async_session and the startup orchestrator
async_main(). These tests cover the model-identity surface only; the
runtime side is exercised by the import smoke test in the conversation.

Skipped if the seller-bot app package is not importable from the current
sys.path (e.g. running the package test suite in isolation without the
repo root).
"""
from __future__ import annotations

import pytest

import common_db
from common_db import models as cdb_models

app_models = pytest.importorskip("app.database.models")
app_url = pytest.importorskip("app.database.url")


SHIMMED_MODEL_NAMES = [
    "CacheVersion",
    "DisabledUser",
    "EmailVerification",
    "GooglePlayPurchase",
    "GooglePlaySku",
    "MenuButton",
    "MenuScreen",
    "Promo",
    "PromoSettings",
    "RefreshToken",
    "SquadProfile",
    "SupportMessage",
    "SupportTicket",
    "TariffPlan",
    "TariffPrice",
    "TelegramLinkCode",
    "TelmtFreeParams",
    "Transaction",
    "User",
    "WebAppMenuNode",
]


@pytest.mark.parametrize("name", SHIMMED_MODEL_NAMES)
def test_app_model_is_common_db_model(name: str) -> None:
    shimmed = getattr(app_models, name)
    canonical = getattr(cdb_models, name)
    assert shimmed is canonical, (
        f"app.database.models.{name} drifted from common_db.models.{name}: "
        f"{shimmed!r} is not {canonical!r}"
    )


def test_app_base_is_common_db_base() -> None:
    assert app_models.Base is common_db.Base


def test_app_url_helpers_are_common_db_helpers() -> None:
    assert app_url.async_db_url is common_db.async_db_url
    assert app_url.sync_db_url is common_db.sync_db_url


def test_app_shim_exports_all_expected_names() -> None:
    missing = [n for n in SHIMMED_MODEL_NAMES if not hasattr(app_models, n)]
    assert not missing, f"app shim missing exports: {missing}"


def test_app_keeps_runtime_attributes() -> None:
    """app.database.models is a *partial* shim — it still owns the
    runtime engine + async_session + startup orchestrator. If any of
    these go missing the seller bot won't start; this test catches it."""
    for attr in ("Base", "DB_URL", "engine", "async_session", "async_main"):
        assert hasattr(app_models, attr), f"app.database.models lost runtime attr: {attr}"


def test_app_metadata_is_common_db_metadata() -> None:
    """Critical for alembic: env.py reads app.database.models.Base.metadata
    as autogenerate's target. After the shim, that metadata IS
    common_db.Base.metadata — the single source of truth across all three
    services. If this ever fails, autogenerate would diff against a
    partial schema and silently drop tables."""
    assert app_models.Base.metadata is common_db.Base.metadata


def test_all_three_shims_share_identity() -> None:
    """Cross-check: app, dashboard, and miniapp shims must all point at
    the same common_db objects. The unified Base only works if there's
    exactly one mapped class per table across the whole repo."""
    dash = pytest.importorskip("dashboard.backend.database.models")
    mini = pytest.importorskip("miniapp.backend.database.models")
    for name in SHIMMED_MODEL_NAMES:
        a = getattr(app_models, name)
        d = getattr(dash, name)
        m = getattr(mini, name)
        assert a is d is m, (
            f"{name}: shims disagree — app={a!r} dashboard={d!r} miniapp={m!r}"
        )
