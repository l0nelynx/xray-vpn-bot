from __future__ import annotations

import pytest
from fastapi import HTTPException

from dashboard.backend.routers.telemt import (
    _assert_editable_patch,
    _filter_editable_config,
)


def test_filter_editable_config_exposes_only_server_listeners() -> None:
    payload = {
        "general": {"links": {"show": True}},
        "server": {
            "listeners": [{"ip": "0.0.0.0", "port": 8443}],
            "port": 443,
            "api": {"auth_header": "SECRET"},
            "admin_api": {"auth_header": "ALSO_SECRET"},
        },
        "network": {"ipv4": "192.0.2.1"},
        "access": {"users": [{"secret": "SECRET"}]},
    }

    assert _filter_editable_config(payload) == {
        "general": {"links": {"show": True}},
        "server": {"listeners": [{"ip": "0.0.0.0", "port": 8443}]},
    }


def test_filter_editable_config_omits_server_without_listeners() -> None:
    assert _filter_editable_config({"server": {"port": 443}}) == {}


def test_server_listeners_patch_is_accepted() -> None:
    _assert_editable_patch(
        {"server": {"listeners": [{"ip": "0.0.0.0", "port": 8443}]}}
    )
    # An empty list intentionally removes every listener and is still a valid
    # wholesale array replacement; Telemt performs final config validation.
    _assert_editable_patch({"server": {"listeners": []}})


@pytest.mark.parametrize(
    ("server", "message"),
    [
        ({"port": 8443}, "server.port"),
        ({"api": {"auth_header": "SECRET"}}, "server.api"),
        ({"admin_api": {}}, "server.admin_api"),
        ({}, "empty server patch"),
        ([], "server patch must be a JSON object"),
        ({"listeners": {}}, "server.listeners must be an array"),
        ({"listeners": ["0.0.0.0:443"]}, "each server.listeners item"),
    ],
)
def test_server_patch_rejects_non_allowlisted_or_malformed_fields(
    server: object,
    message: str,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        _assert_editable_patch({"server": server})

    assert exc_info.value.status_code == 400
    assert message in str(exc_info.value.detail)
