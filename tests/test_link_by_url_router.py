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


@pytest.fixture(autouse=True)
def _stub_subscription_host(monkeypatch):
    """Pin the parser's subscription host to ``sub.domain.com`` so
    tests don't require a real config.yml. The router reads the host via
    ``get_subscription_host`` (imported at module load); replace it with a
    constant function for the duration of every test in this file.
    """
    import miniapp.backend.android.link_router as lr
    monkeypatch.setattr(lr, "get_subscription_host",
                        lambda: "sub.domain.com")


class TestParseShortUuid:
    """Pure URL → short_uuid parser, no FastAPI involvement."""

    GOOD_URL = "https://sub.domain.com/sN_RHMk6BGv-RJ8g"
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
                "https://sub.domain.com/api/sN_xxxxxxxxxxxx"
            )
        assert exc.value.status_code == 422

    def test_empty_path_rejected(self):
        with pytest.raises(HTTPException):
            _parse_short_uuid("https://sub.domain.com/")

    def test_too_short_path_rejected(self):
        # Less than 8 chars fails the regex.
        with pytest.raises(HTTPException):
            _parse_short_uuid("https://sub.domain.com/short")

    def test_invalid_characters_rejected(self):
        with pytest.raises(HTTPException):
            _parse_short_uuid(
                "https://sub.domain.com/has spaces here!"
            )

    def test_malformed_url_rejected(self):
        with pytest.raises(HTTPException):
            _parse_short_uuid("not-a-url-at-all")


from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient

from common_db.models import User


@dataclass
class _FakeUser:
    # link_by_url only reads `id` and `email` off the dependency-injected
    # user; the rest of the User row is read from the DB by
    # import_subscription_by_uuid via session.get(User, id).
    id: int = 100
    email: str | None = "a@x.io"


@pytest.fixture
def link_by_url_app(with_app_db, fake_remnawave, monkeypatch):
    """Minimal FastAPI app exposing only the link_router.

    Overrides require_verified_email to return a fake user with id=100.
    Captures notify_log calls in app.state.notify_calls.
    The with_app_db fixture redirects async_session for both the
    app/handlers/android_link.py module and app/database/models. We
    additionally redirect miniapp.backend.database.session.async_session
    since the router opens its own session via that import.
    """
    import miniapp.backend.android.link_router as lr
    import miniapp.backend.android.deps as deps
    import miniapp.backend.notify_log as nl
    import miniapp.backend.database.session as mdb

    monkeypatch.setattr(mdb, "async_session", with_app_db)
    monkeypatch.setattr(lr, "async_session", with_app_db)
    # The router imported update_user by name at module load; the
    # fake_remnawave fixture patches the source module but the bound
    # name in lr still points at the real client. Redirect it.
    monkeypatch.setattr(lr, "update_user", fake_remnawave.update_user)

    notify_calls: list[str] = []

    async def fake_notify(text, *, parse_mode="HTML"):
        notify_calls.append(text)

    monkeypatch.setattr(nl, "notify_log", fake_notify)
    monkeypatch.setattr(lr, "notify_log", fake_notify)

    app = FastAPI()
    app.include_router(lr.router)
    app.state.notify_calls = notify_calls
    app.state.fake_user = _FakeUser()

    async def override_require_verified_email():
        return app.state.fake_user

    app.dependency_overrides[deps.require_verified_email] = (
        override_require_verified_email
    )
    # Slowapi requires app.state.limiter; reuse the router's limiter.
    app.state.limiter = lr.limiter
    # Slowapi keeps per-IP counters on the module-level Limiter — reset
    # between tests so the 3/minute cap doesn't bleed across cases.
    lr.limiter.reset()
    return app


@pytest.fixture
def link_by_url_client(link_by_url_app):
    return TestClient(link_by_url_app)


SHORT = "sN_RHMk6BGv-RJ8g"
URL = f"https://sub.domain.com/{SHORT}"


class TestLinkByUrlEndpoint:
    def _seed_a(self, with_app_db, *, vless="a-uuid", email="a@x.io"):
        async def go():
            async with with_app_db() as s:
                s.add(User(id=100, email=email, vless_uuid=vless,
                           password_hash="ph",
                           email_verified_at="2026-05-19T00:00:00"))
                await s.commit()
        asyncio.run(go())

    def test_merged_pro_returns_200_and_disables_loser(
        self, link_by_url_client, link_by_url_app, with_app_db,
        fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=SHORT,
                                email="b@x.io",
                                status="active",
                                data_limit=10 * 1024 ** 3)
        self._seed_a(with_app_db)

        resp = link_by_url_client.post(
            "/api/android/link/by_url", json={"url": URL, "email": "b@x.io"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body == {
            "result": "merged_pro",
            "a_tier": "pro",
            "b_tier": "free",
        }
        assert "b-uuid" in fake_remnawave.disabled_calls
        # A.vless_uuid unchanged (PRO A kept its uuid).
        async def fetch():
            async with with_app_db() as s:
                return (await s.get(User, 100)).vless_uuid
        assert asyncio.run(fetch()) == "a-uuid"
        # notify_log was called with the result code.
        assert any(
            "merged_pro" in m
            for m in link_by_url_app.state.notify_calls
        )

    def test_invalid_url_returns_422(
        self, link_by_url_client,
    ):
        resp = link_by_url_client.post(
            "/api/android/link/by_url",
            json={"url": "https://attacker.example.com/sN_xxxxxxxxxxxx", "email": "b@x.io"},
        )
        assert resp.status_code == 422
        assert resp.json() == {"detail": {"code": "invalid_url"}}

    def test_multi_segment_path_returns_422(
        self, link_by_url_client,
    ):
        resp = link_by_url_client.post(
            "/api/android/link/by_url",
            json={"url": f"https://sub.domain.com/api/{SHORT}", "email": "b@x.io"},
        )
        assert resp.status_code == 422

    def test_http_scheme_returns_422(
        self, link_by_url_client,
    ):
        resp = link_by_url_client.post(
            "/api/android/link/by_url",
            json={"url": URL.replace("https://", "http://"), "email": "b@x.io"},
        )
        assert resp.status_code == 422

    def test_rw_lookup_miss_returns_404(
        self, link_by_url_client, fake_remnawave, with_app_db,
    ):
        # B short_uuid not registered → LookupNotFound.
        self._seed_a(with_app_db)
        resp = link_by_url_client.post(
            "/api/android/link/by_url", json={"url": URL, "email": "b@x.io"},
        )
        assert resp.status_code == 404
        assert resp.json() == {"detail": {"code": "rw_not_found"}}

    def test_both_pro_returns_200_with_support_code(
        self, link_by_url_client, link_by_url_app, with_app_db,
        fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=SHORT,
                                email="b@x.io",
                                status="active", data_limit=None)
        self._seed_a(with_app_db)

        resp = link_by_url_client.post(
            "/api/android/link/by_url", json={"url": URL, "email": "b@x.io"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"] == "both_pro_support_needed"
        assert body["a_tier"] == "pro"
        assert body["b_tier"] == "pro"
        # No DB change, no RW deactivate.
        assert fake_remnawave.disabled_calls == []
        async def fetch():
            async with with_app_db() as s:
                return (await s.get(User, 100)).vless_uuid
        assert asyncio.run(fetch()) == "a-uuid"
        assert any(
            "both_pro_support_needed" in m
            for m in link_by_url_app.state.notify_calls
        )

    def test_self_import_returns_already_owned(
        self, link_by_url_client, link_by_url_app, with_app_db,
        fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                short_uuid=SHORT,
                                status="active", data_limit=None)
        self._seed_a(with_app_db)

        resp = link_by_url_client.post(
            "/api/android/link/by_url", json={"url": URL, "email": "a@x.io"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"] == "already_owned"
        assert fake_remnawave.disabled_calls == []

    def test_email_not_verified_returns_403(
        self, link_by_url_client, link_by_url_app, with_app_db,
        fake_remnawave,
    ):
        # Toggle the fake user to unverified, then re-override.
        import miniapp.backend.android.deps as deps
        from fastapi import HTTPException, status as http_status

        async def reject():
            raise HTTPException(
                http_status.HTTP_403_FORBIDDEN, "email_not_verified",
            )

        link_by_url_app.dependency_overrides[
            deps.require_verified_email
        ] = reject

        resp = link_by_url_client.post(
            "/api/android/link/by_url", json={"url": URL, "email": "b@x.io"},
        )
        assert resp.status_code == 403

    def test_missing_auth_dependency_returns_401(
        self, link_by_url_client, link_by_url_app, with_app_db,
        fake_remnawave,
    ):
        import miniapp.backend.android.deps as deps
        from fastapi import HTTPException, status as http_status

        async def reject():
            raise HTTPException(
                http_status.HTTP_401_UNAUTHORIZED, "missing bearer token",
            )

        link_by_url_app.dependency_overrides[
            deps.require_verified_email
        ] = reject

        resp = link_by_url_client.post(
            "/api/android/link/by_url", json={"url": URL, "email": "b@x.io"},
        )
        assert resp.status_code == 401

    def test_rw_deactivate_failure_does_not_break_merge(
        self, link_by_url_client, link_by_url_app, with_app_db,
        fake_remnawave,
    ):
        fake_remnawave.add_user(uuid="a-uuid", email="a@x.io",
                                status="active", data_limit=None)
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=SHORT,
                                email="b@x.io",
                                status="active",
                                data_limit=10 * 1024 ** 3)
        fake_remnawave.update_should_raise = RuntimeError("rw down")
        self._seed_a(with_app_db)

        resp = link_by_url_client.post(
            "/api/android/link/by_url", json={"url": URL, "email": "b@x.io"},
        )
        assert resp.status_code == 200
        assert resp.json()["result"] == "merged_pro"
        assert any(
            "Failed to disable" in m
            for m in link_by_url_app.state.notify_calls
        )
        # Final result notify must reflect the failed disable as
        # disabled_uuid=— (not the still-live b-uuid).
        assert any(
            "merged_pro" in m and "disabled_uuid=<code>—</code>" in m
            for m in link_by_url_app.state.notify_calls
        )

    def test_missing_email_returns_422(
        self, link_by_url_client,
    ):
        """Pydantic rejects body without 'email' field."""
        resp = link_by_url_client.post(
            "/api/android/link/by_url", json={"url": URL},
        )
        assert resp.status_code == 422

    def test_malformed_email_returns_422(
        self, link_by_url_client,
    ):
        """Pydantic EmailStr rejects 'not-an-email'."""
        resp = link_by_url_client.post(
            "/api/android/link/by_url",
            json={"url": URL, "email": "not-an-email"},
        )
        assert resp.status_code == 422

    def test_email_mismatch_returns_404_rw_not_found(
        self, link_by_url_client, link_by_url_app, with_app_db,
        fake_remnawave,
    ):
        """RW has B with email=b@x.io; client claims other@x.io.
        Response is identical to test_rw_lookup_miss_returns_404 — by
        design (no oracle).
        """
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=SHORT,
                                email="b@x.io",
                                status="active",
                                data_limit=10 * 1024 ** 3)
        self._seed_a(with_app_db)

        resp = link_by_url_client.post(
            "/api/android/link/by_url",
            json={"url": URL, "email": "other@x.io"},
        )
        assert resp.status_code == 404
        assert resp.json() == {"detail": {"code": "rw_not_found"}}

    def test_email_mismatch_notify_carries_claimed_email(
        self, link_by_url_client, link_by_url_app, with_app_db,
        fake_remnawave,
    ):
        """Admin notify_log on rw_not_found carries the claimed_email so
        ops can grep for patterns. (logger.info inside the merge function
        carries the actual rw_email too, but we don't inspect logs here.)
        """
        fake_remnawave.add_user(uuid="b-uuid", short_uuid=SHORT,
                                email="b@x.io",
                                status="active",
                                data_limit=10 * 1024 ** 3)
        self._seed_a(with_app_db)

        link_by_url_client.post(
            "/api/android/link/by_url",
            json={"url": URL, "email": "other@x.io"},
        )
        assert any(
            "rw_not_found" in m and "other@x.io" in m
            for m in link_by_url_app.state.notify_calls
        )
