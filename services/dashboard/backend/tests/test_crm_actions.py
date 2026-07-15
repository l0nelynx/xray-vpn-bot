"""Tests for CRM actions pipeline."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, unquote, urlparse

from common_db.models import User


def _run(coro):
    return asyncio.run(coro)


def test_normalize_actions_rw_before_telegram() -> None:
    from dashboard.backend.crm_model_adapter import normalize_actions

    actions = [
        {"type": "send_message", "enabled": True, "text": "hi"},
        {"type": "rw_bonus_days", "enabled": True, "days": 3},
    ]
    ordered = normalize_actions(actions)
    assert ordered[0]["type"] == "rw_bonus_days"
    assert ordered[1]["type"] == "send_message"


def test_execute_user_actions_message_only() -> None:
    from dashboard.backend.crm_actions import execute_user_actions

    async def go() -> None:
        user = User(id=1, tg_id=101, username="alice", vless_uuid=None)
        actions = [{"type": "send_message", "enabled": True, "order": 100, "text": "Hello {{username}}"}]

        with patch("dashboard.backend.crm_actions.tg_send", new_callable=AsyncMock) as send:
            send.return_value = True
            result = await execute_user_actions(
                MagicMock(),
                user,
                None,
                actions,
                bot_username="mybot",
            )
            assert result.message_sent is True
            assert result.perks_applied is False
            send.assert_awaited_once()

    _run(go())


def test_execute_user_actions_rw_only() -> None:
    from dashboard.backend.crm_actions import execute_user_actions

    async def go() -> None:
        user = User(id=1, tg_id=101, username="alice", vless_uuid="uuid-1")
        crm_user = {"uuid": "uuid-1", "status": "active"}
        actions = [{"type": "rw_reset_traffic", "enabled": True, "order": 12}]

        rw = MagicMock()
        rw.reset_user_traffic = AsyncMock(return_value=True)

        with patch("dashboard.backend.crm_actions.tg_send", new_callable=AsyncMock) as send:
            result = await execute_user_actions(rw, user, crm_user, actions)
            assert result.perks_applied is True
            assert result.message_skipped is True
            send.assert_not_awaited()
            rw.reset_user_traffic.assert_awaited_once_with("uuid-1")

    _run(go())


def test_execute_user_actions_open_bot_button() -> None:
    from dashboard.backend.crm_actions import execute_user_actions

    async def go() -> None:
        user = User(id=1, tg_id=101, username="alice", vless_uuid=None)
        actions = [
            {"type": "send_message", "enabled": True, "order": 100, "text": "Hi"},
            {"type": "attach_button", "enabled": True, "order": 101, "button_type": "open_bot"},
        ]

        with patch("dashboard.backend.crm_actions.tg_send", new_callable=AsyncMock) as send:
            send.return_value = True
            result = await execute_user_actions(
                MagicMock(),
                user,
                None,
                actions,
                bot_username="CheezyXrayBot",
            )
            assert result.message_sent is True
            markup = send.await_args.args[2]
            assert markup["inline_keyboard"][0][0]["text"] == "Открыть бота"
            assert markup["inline_keyboard"][0][0]["url"] == (
                "https://t.me/CheezyXrayBot?start="
            )

    _run(go())


def test_execute_user_actions_invite_friends_button() -> None:
    from dashboard.backend.crm_actions import execute_user_actions

    async def go() -> None:
        user = User(id=1, tg_id=101, username="alice", vless_uuid=None)
        actions = [
            {"type": "send_message", "enabled": True, "order": 100, "text": "Share me"},
            {
                "type": "attach_button",
                "enabled": True,
                "order": 101,
                "button_type": "invite_friends",
            },
        ]
        session = MagicMock()

        with (
            patch("dashboard.backend.crm_actions.tg_send", new_callable=AsyncMock) as send,
            patch(
                "dashboard.backend.crm_actions._repo_promos.get_or_create_referral_code",
                new_callable=AsyncMock,
                return_value="ABCD1234",
            ) as get_code,
            patch(
                "dashboard.backend.crm_actions._repo_system.get_default_credit_grant",
                new_callable=AsyncMock,
                return_value=3,
            ),
        ):
            send.return_value = True
            result = await execute_user_actions(
                MagicMock(),
                user,
                None,
                actions,
                bot_username="CheezyXrayBot",
                session=session,
            )
            assert result.message_sent is True
            get_code.assert_awaited_once_with(session, 101)
            markup = send.await_args.args[2]
            btn = markup["inline_keyboard"][0][0]
            assert btn["text"] == "Пригласить друзей"
            share = urlparse(btn["url"])
            assert share.netloc == "t.me"
            assert share.path == "/share/url"
            qs = parse_qs(share.query)
            deeplink = unquote(qs["url"][0])
            text = unquote(qs["text"][0])
            assert deeplink == "https://t.me/CheezyXrayBot?start=ABCD1234"
            assert "3 🪙" in text
            assert "по моему коду" in text

    _run(go())


def test_validate_actions_requires_enabled() -> None:
    from dashboard.backend.crm_model_adapter import validate_actions
    import pytest

    with pytest.raises(ValueError, match="at least one enabled"):
        validate_actions([{"type": "send_message", "enabled": False, "text": "x"}])
