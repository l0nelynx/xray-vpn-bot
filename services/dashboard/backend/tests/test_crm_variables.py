"""Tests for CRM message variable rendering."""
from __future__ import annotations

import pytest


def test_render_known_variables() -> None:
    from dashboard.backend.crm_variables import render_crm_message

    template = "Hi {{username}}, days: {{days_left}}, traffic: {{traffic_left}}"
    ctx = {
        "username": "@alice",
        "days_left": "3",
        "traffic_left": "2 ГБ",
    }
    assert render_crm_message(template, ctx) == "Hi @alice, days: 3, traffic: 2 ГБ"


def test_render_unknown_variable_becomes_empty() -> None:
    from dashboard.backend.crm_variables import render_crm_message

    assert render_crm_message("{{unknown}}", {}) == ""


def test_render_whitespace_in_braces() -> None:
    from dashboard.backend.crm_variables import render_crm_message

    assert render_crm_message("{{ username }}", {"username": "@bob"}) == "@bob"


def test_build_message_context_escapes_username() -> None:
    from dashboard.backend.crm_variables import build_message_context

    ctx = build_message_context(
        username="<script>",
        crm_user={
            "days_left": 5,
            "device_count": 2,
            "status": "active",
            "traffic_limit_bytes": 10 * 1024 ** 3,
            "used_traffic_bytes": 2 * 1024 ** 3,
            "traffic_ratio": 0.2,
        },
    )
    assert "&lt;script&gt;" in ctx["username"]
    assert ctx["days_left"] == "5"
    assert ctx["hwid_devices"] == "2"


def test_build_message_context_unlimited_traffic() -> None:
    from dashboard.backend.crm_variables import build_message_context

    ctx = build_message_context(
        username="alice",
        crm_user={"traffic_limit_bytes": 0, "used_traffic_bytes": 0},
    )
    assert ctx["traffic_left"] == "—"
