"""IAP may be configured later without blocking the Miniapp."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException


def test_incomplete_iap_config_does_not_block_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from miniapp.backend import security_config

    monkeypatch.setattr(
        security_config,
        "get_android_jwt_secret",
        lambda: "a" * 64,
    )

    security_config.validate_security_config()


class _UnreadRequest:
    async def json(self) -> dict:
        raise AssertionError("RTDN body must not be read before authentication")


def test_unconfigured_rtdn_endpoint_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from miniapp.backend.android import iap_router

    monkeypatch.setattr(iap_router, "get_google_play_rtdn_token", lambda: "")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            iap_router.real_time_developer_notification(
                _UnreadRequest(),
                token=None,
            )
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "iap_not_configured"


def test_configured_rtdn_endpoint_rejects_wrong_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from miniapp.backend.android import iap_router

    monkeypatch.setattr(
        iap_router,
        "get_google_play_rtdn_token",
        lambda: "configured-secret",
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            iap_router.real_time_developer_notification(
                _UnreadRequest(),
                token="wrong-secret",
            )
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "bad_rtdn_token"
