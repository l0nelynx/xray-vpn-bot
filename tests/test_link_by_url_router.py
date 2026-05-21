"""Router-level tests for POST /api/android/link/by_url.

Uses FastAPI TestClient. Builds a minimal app importing only the
link_router, overrides deps.require_verified_email, monkeypatches
notify_log and Remnawave shims, and redirects async_session via the
existing with_app_db fixture.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from miniapp.backend.android.link_router import _parse_short_uuid


class TestParseShortUuid:
    """Pure URL → short_uuid parser, no FastAPI involvement."""

    GOOD_URL = "https://user.spicycheeze.xyz/sN_RHMk6BGv-RJ8g"
    GOOD_SHORT = "sN_RHMk6BGv-RJ8g"

    def test_valid_https_returns_short_uuid(self):
        assert _parse_short_uuid(self.GOOD_URL) == self.GOOD_SHORT

    def test_query_string_is_ignored(self):
        assert _parse_short_uuid(self.GOOD_URL + "?ref=foo") == self.GOOD_SHORT

    def test_fragment_is_ignored(self):
        assert _parse_short_uuid(self.GOOD_URL + "#anchor") == self.GOOD_SHORT

    def test_trailing_slash_is_accepted(self):
        assert _parse_short_uuid(self.GOOD_URL + "/") == self.GOOD_SHORT

    def test_http_scheme_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _parse_short_uuid(self.GOOD_URL.replace("https://", "http://"))
        assert exc.value.status_code == 422
        assert exc.value.detail == {"code": "invalid_url"}

    def test_wrong_host_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _parse_short_uuid("https://attacker.example.com/sN_xxxxxxxxxxxx")
        assert exc.value.status_code == 422

    def test_multi_segment_path_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _parse_short_uuid(
                "https://user.spicycheeze.xyz/api/sN_xxxxxxxxxxxx"
            )
        assert exc.value.status_code == 422

    def test_empty_path_rejected(self):
        with pytest.raises(HTTPException):
            _parse_short_uuid("https://user.spicycheeze.xyz/")

    def test_too_short_path_rejected(self):
        # Less than 8 chars fails the regex.
        with pytest.raises(HTTPException):
            _parse_short_uuid("https://user.spicycheeze.xyz/short")

    def test_invalid_characters_rejected(self):
        with pytest.raises(HTTPException):
            _parse_short_uuid(
                "https://user.spicycheeze.xyz/has spaces here!"
            )

    def test_malformed_url_rejected(self):
        with pytest.raises(HTTPException):
            _parse_short_uuid("not-a-url-at-all")
