import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from miniapp.backend.web import registration_guard as guard, web_router


def test_sliding_windows_and_pair_retries(monkeypatch):
    window = guard.RegistrationWindow()
    now = 0
    monkeypatch.setattr(guard.time, "monotonic", lambda: now)
    for _ in range(6):
        assert window.check("nat", "alice") == 0
    with pytest.raises(HTTPException) as limited:
        window.check("nat", "alice")
    assert limited.value.headers == {"Retry-After": "600"}
    assert window.check("nat", "bob") == window.check("nat", "carol") == 0
    assert window.check("nat", "dave") == 3600
    assert window.check("other", "dave") == 0
    now = 600
    assert window.check("nat", "alice") == 0
    assert window.check("nat", "dave") == 3000
    now = 3600
    assert window.check("nat", "dave") == 0
    assert set(window.emails["nat"]) == {"alice", "dave"}
    assert "other" not in window.emails


def test_concurrent_reservations_share_three_slots():
    window = guard.RegistrationWindow()
    with ThreadPoolExecutor() as threads:
        waits = list(threads.map(lambda email: window.check("nat", email), map(str, range(15))))
    assert waits.count(0) == 3


def test_register_challenge_and_retry(monkeypatch):
    monkeypatch.setenv("TURNSTILE_SITE_KEY", "public")
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "secret")
    monkeypatch.setattr(guard, "window", guard.RegistrationWindow())
    monkeypatch.setattr(guard, "get_web_allowed_origins", lambda: ["https://portal.test"])
    monkeypatch.setattr(guard, "get_web_portal_url", lambda: "")
    # A conflict after hashing exercises retries without creating real accounts.
    hashing = AsyncMock(return_value="hash")
    monkeypatch.setattr(web_router.android_security, "hash_password", hashing)
    monkeypatch.setattr(web_router.android_repo, "create_user_with_password", AsyncMock(
        side_effect=IntegrityError(None, None, Exception())
    ))
    app = FastAPI()
    app.include_router(web_router.router)
    client = TestClient(app)
    def register(email, **extra):
        return client.post("/api/web/register", headers={"X-Real-IP": "192.0.2.20"},
                           json={"email": email, "password": "example-password", **extra})

    for address in ["FIRST", "first", "second", "third"]:
        assert register(f"{address}@gmail.com").status_code == 409
    fourth = "fourth@gmail.com"
    detail = register(fourth).json()["detail"]
    assert detail["code"] == "challenge_required" and detail["site_key"] == "public"
    assert hashing.await_count == 4
    assert register("first@gmail.com").status_code == 409
    assert register(fourth).status_code == 403
    result = {"success": True, "action": "web_register", "hostname": "portal.test",
              "cdata": detail["cdata"]}
    verify = AsyncMock(return_value=httpx.Response(
        200, json=result, request=httpx.Request("POST", guard.VERIFY_URL)
    ))
    monkeypatch.setattr(httpx.AsyncClient, "post", verify)
    assert register("different@gmail.com", captcha_token="proof").status_code == 403
    assert register(fourth, captcha_token="proof").status_code == 409
    assert register(fourth, captcha_token="proof").status_code == 403
    assert hashing.await_count == 6
    verify.side_effect = httpx.ReadTimeout("timeout")
    assert register(fourth, captcha_token="another-proof").status_code == 503
    assert hashing.await_count == 6


def test_without_keys_new_addresses_can_retry_when_slot_opens(monkeypatch):
    monkeypatch.delenv("TURNSTILE_SECRET_KEY", raising=False)
    window = guard.RegistrationWindow()
    monkeypatch.setattr(guard, "window", window)
    for email in ("a", "b", "c"):
        window.check("nat", email)
    with pytest.raises(HTTPException) as error:
        asyncio.run(guard.enforce("nat", "d", "arbitrary"))
    assert error.value.status_code == 429
    assert 0 < int(error.value.headers["Retry-After"]) <= 3600
