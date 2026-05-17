"""Step 3 drift guard: dashboard shims must re-export the *same* objects.

dashboard/backend/database/models.py and url.py are backwards-compat shims
that re-export from common_db. If someone reintroduces a local ORM class
under the same name, `is` identity breaks and these tests fail — that's the
whole point. The check is `is`, not `==`, because SQLAlchemy mapped classes
compare equal trivially but two separate Base hierarchies would silently
register two tables with the same name.

Skipped if the dashboard package is not importable from the current sys.path
(e.g. running the package test suite in isolation without the repo root).
"""
from __future__ import annotations

import importlib

import pytest

import common_db
from common_db import models as cdb_models

dashboard_models = pytest.importorskip("dashboard.backend.database.models")
dashboard_url = pytest.importorskip("dashboard.backend.database.url")


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
def test_dashboard_model_is_common_db_model(name: str) -> None:
    shimmed = getattr(dashboard_models, name)
    canonical = getattr(cdb_models, name)
    assert shimmed is canonical, (
        f"dashboard.backend.database.models.{name} drifted from common_db.models.{name}: "
        f"{shimmed!r} is not {canonical!r}"
    )


def test_dashboard_base_is_common_db_base() -> None:
    assert dashboard_models.Base is common_db.Base


def test_dashboard_url_helpers_are_common_db_helpers() -> None:
    assert dashboard_url.async_db_url is common_db.async_db_url
    assert dashboard_url.sync_db_url is common_db.sync_db_url


def test_dashboard_shim_exports_all_expected_names() -> None:
    missing = [n for n in SHIMMED_MODEL_NAMES if not hasattr(dashboard_models, n)]
    assert not missing, f"dashboard shim missing exports: {missing}"
