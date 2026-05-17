"""Step 4 drift guard: miniapp shims must re-export the *same* objects.

Mirrors test_dashboard_shim.py — see that file for the rationale.

Skipped if the miniapp package is not importable from the current sys.path
(e.g. running the package test suite in isolation without the repo root).
"""
from __future__ import annotations

import pytest

import common_db
from common_db import models as cdb_models

miniapp_models = pytest.importorskip("miniapp.backend.database.models")
miniapp_url = pytest.importorskip("miniapp.backend.database.url")


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
def test_miniapp_model_is_common_db_model(name: str) -> None:
    shimmed = getattr(miniapp_models, name)
    canonical = getattr(cdb_models, name)
    assert shimmed is canonical, (
        f"miniapp.backend.database.models.{name} drifted from common_db.models.{name}: "
        f"{shimmed!r} is not {canonical!r}"
    )


def test_miniapp_base_is_common_db_base() -> None:
    assert miniapp_models.Base is common_db.Base


def test_miniapp_url_helpers_are_common_db_helpers() -> None:
    assert miniapp_url.async_db_url is common_db.async_db_url
    assert miniapp_url.sync_db_url is common_db.sync_db_url


def test_miniapp_shim_exports_all_expected_names() -> None:
    missing = [n for n in SHIMMED_MODEL_NAMES if not hasattr(miniapp_models, n)]
    assert not missing, f"miniapp shim missing exports: {missing}"


def test_dashboard_and_miniapp_share_identity() -> None:
    """Cross-check: dashboard and miniapp shims must point at the *same*
    common_db objects (not just to equal-looking classes). If this ever
    fails, both shims drifted in different directions and Base.metadata
    is no longer single-source."""
    dash = pytest.importorskip("dashboard.backend.database.models")
    for name in SHIMMED_MODEL_NAMES:
        assert getattr(dash, name) is getattr(miniapp_models, name), (
            f"{name}: dashboard shim and miniapp shim disagree"
        )
