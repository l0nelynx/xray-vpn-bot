"""Unit tests for registration email denylist and IP/OTP cooldowns."""
from __future__ import annotations

import time

import pytest
from fastapi import HTTPException

from miniapp.backend.android import (
    email_policy,
    email_send_guard,
    register_ip_guard,
)


@pytest.fixture(autouse=True)
def _reset_guards(monkeypatch):
    register_ip_guard.reset()
    email_send_guard.reset()
    monkeypatch.setattr(email_policy, "get_email_denied_domains", lambda: [])
    yield
    register_ip_guard.reset()
    email_send_guard.reset()


# --- email denylist --------------------------------------------------------


@pytest.mark.parametrize(
    "email",
    [
        "probe64945@example.com",
        "user@example.org",
        "x@EXAMPLE.NET",
        "a@test.com",
        "b@qzz.io",
        "c@mail.qzz.io",
        "probe1@gmail.com",
        "test_x@doing1024.qzz.io",
        "test-foo@gmail.com",
    ],
)
def test_denied_emails(email: str):
    assert email_policy.is_email_denied(email)


@pytest.mark.parametrize(
    "email",
    [
        "real.user@gmail.com",
        "testing@gmail.com",
        "alice@company.io",
    ],
)
def test_allowed_emails(email: str):
    assert not email_policy.is_email_denied(email)
    assert email_policy.assert_email_allowed(email) == email.strip().lower()


def test_assert_email_allowed_rejects():
    with pytest.raises(HTTPException) as exc:
        email_policy.assert_email_allowed("probe1@example.com")
    assert exc.value.status_code == 403
    assert exc.value.detail == {"code": "email_rejected"}


def test_config_extra_denied_domain(monkeypatch):
    monkeypatch.setattr(
        email_policy, "get_email_denied_domains", lambda: ["spam.test"]
    )
    assert email_policy.is_email_denied("a@spam.test")
    assert not email_policy.is_email_denied("a@gmail.com")


# --- register IP guard -----------------------------------------------------


def test_register_ip_allows_three_per_hour():
    ip = "1.2.3.4"
    for _ in range(3):
        register_ip_guard.check(ip)
        register_ip_guard.record(ip)
    with pytest.raises(HTTPException) as exc:
        register_ip_guard.check(ip)
    assert exc.value.status_code == 429
    assert exc.value.detail["code"] == "rate_limited"
    assert exc.value.detail["retry_after"] >= 1


def test_register_ip_hour_window_slides(monkeypatch):
    ip = "5.6.7.8"
    now = time.time()
    # Three successes just over an hour ago — should not count.
    with register_ip_guard._lock:
        register_ip_guard._success_ts[ip] = [
            now - 3_601,
            now - 3_602,
            now - 3_603,
        ]
    register_ip_guard.check(ip)
    register_ip_guard.record(ip)


def test_register_ip_day_cap():
    ip = "9.9.9.9"
    now = time.time()
    with register_ip_guard._lock:
        # 10 events inside the day window but outside the hour window.
        register_ip_guard._success_ts[ip] = [
            now - 3_700 - i * 2_000 for i in range(10)
        ]
    with pytest.raises(HTTPException) as exc:
        register_ip_guard.check(ip)
    assert exc.value.status_code == 429
    assert exc.value.detail["retry_after"] >= 1


def test_register_ip_shared_bucket_android_web():
    ip = "10.0.0.1"
    for _ in range(3):
        register_ip_guard.check(ip)
        register_ip_guard.record(ip)
    with pytest.raises(HTTPException):
        register_ip_guard.check(ip)


# --- email send guard ------------------------------------------------------


def test_send_guard_three_then_five_minute_block():
    email = "user@gmail.com"
    ip = "8.8.8.8"
    for _ in range(3):
        email_send_guard.check(email=email, ip=ip)
        email_send_guard.record(email=email, ip=ip)
    with pytest.raises(HTTPException) as exc:
        email_send_guard.check(email=email, ip=ip)
    assert exc.value.status_code == 429
    assert 1 <= exc.value.detail["retry_after"] <= 5 * 60


def test_send_guard_email_and_ip_independent():
    email_send_guard.check(email="a@gmail.com", ip="1.1.1.1")
    email_send_guard.record(email="a@gmail.com", ip="1.1.1.1")
    # Different email, same IP — IP consecutive is 1; email is fresh.
    email_send_guard.check(email="b@gmail.com", ip="1.1.1.1")
    email_send_guard.record(email="b@gmail.com", ip="1.1.1.1")
    email_send_guard.check(email="c@gmail.com", ip="1.1.1.1")
    email_send_guard.record(email="c@gmail.com", ip="1.1.1.1")
    # Fourth send from same IP (across emails) should trip IP consecutive.
    with pytest.raises(HTTPException):
        email_send_guard.check(email="d@gmail.com", ip="1.1.1.1")


def test_send_guard_clear_consecutive_does_not_lift_active_block():
    email = "clear@gmail.com"
    for _ in range(3):
        email_send_guard.check(email=email, ip=None)
        email_send_guard.record(email=email, ip=None)
    email_send_guard.clear_consecutive(email=email)
    with pytest.raises(HTTPException):
        email_send_guard.check(email=email, ip=None)


def test_send_guard_day_limit_blocks_48h():
    email = "flood@gmail.com"
    now = time.time()
    key = email_send_guard._key_email(email)
    with email_send_guard._lock:
        bucket = email_send_guard._buckets[key]
        bucket.send_ts = [now - i * 60 for i in range(10)]
        bucket.consecutive = 0
        bucket.blocked_until = 0.0
    with pytest.raises(HTTPException) as exc:
        email_send_guard.check(email=email, ip=None)
    assert exc.value.status_code == 429
    # check() promotes day overflow into a 48h block.
    assert exc.value.detail["retry_after"] >= 47 * 3600
