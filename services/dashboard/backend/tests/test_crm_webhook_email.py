"""Delivery to webhook-provided contacts independently of local accounts."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
from common_db.mailer import MailerError
from common_db.models import User, CrmWebhookDelivery
from common_db.repo import crm_webhooks
from dashboard.backend import crm_webhook_runner as runner
from dashboard.backend.crm_actions import UserActionResult
from dashboard.backend.crm_model_adapter import validate_actions

EMAIL = {
    "type": "send_email", "enabled": True, "subject": "Account notice",
    "text": "Hello {{username}}. {{ip}} {{blockMinutes}}", "recipients": "without_telegram",
    "send_to_email_from_webhook": True,
}


def _payload(email="hook@example.com", scope="torrent_blocker"):
    user = {"id": 123, "username": "remote", "email": email, "status": "EXPIRED"}
    data = user if scope == "user" else {"user": user}
    if scope == "torrent_blocker":
        data["report"] = {
            "actionReport": {"userId": "123", "ip": "203.0.113.42", "blockDuration": 1800},
            "xrayReport": {"email": "123"},
        }
    return {
        "scope": scope,
        "event": {"user": "user.expired", "torrent_blocker": "torrent_blocker.report", "user_hwid_devices": "user_hwid_devices.added"}[scope],
        "timestamp": "2026-10-31T12:00:00Z", "data": data,
    }


@asynccontextmanager
async def _database(mode="missing", actions=None, scope="torrent_blocker"):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            if mode != "missing":
                session.add(User(id=1, rw_id=123, tg_id=101, username="local", email="database@example.com", is_banned=mode == "banned"))
            rule = await crm_webhooks.create_rule(
                session, name="Webhook email", scope=scope, event=_payload(scope=scope)["event"],
                actions=actions or [EMAIL], created_by="test", cooldown_hours=24,
            )
            await session.commit()
            rule_id = rule.id
        yield factory, rule_id
    finally:
        await engine.dispose()


@contextmanager
def _io(factory):
    with (
        patch.object(runner, "async_session", factory),
        patch.object(runner, "_rw_client", return_value=MagicMock()),
        patch.object(runner, "_fetch_crm_user", new_callable=AsyncMock, return_value=None) as fetch,
        patch.object(runner, "tg_bot_username", new_callable=AsyncMock) as bot,
        patch.object(runner, "send_crm_email", new_callable=AsyncMock) as send,
        patch.object(runner, "execute_user_actions", new_callable=AsyncMock, return_value=UserActionResult(message_sent=True, message_skipped=False)) as local,
    ):
        yield send, local, fetch, bot


@pytest.mark.parametrize("mode", ["missing", "existing", "banned"])
@pytest.mark.parametrize("scope", ["torrent_blocker", "user", "user_hwid_devices"])
def test_webhook_email_does_not_depend_on_local_account_or_telegram(mode, scope):
    async def check():
        async with _database(mode, scope=scope) as (factory, rule_id):
            with _io(factory) as (send, local, fetch, bot):
                await runner.execute_crm_webhook(_payload(scope=scope))
                send.assert_awaited_once()
                assert send.await_args.kwargs["to"] == "hook@example.com"
                assert send.await_args.kwargs["context"]["username"] == "@remote"
                if scope == "torrent_blocker":
                    assert send.await_args.kwargs["context"]["blockMinutes"] == "30"
                local.assert_not_awaited()
                fetch.assert_not_awaited()
                bot.assert_not_awaited()
            async with factory() as session:
                row = await session.scalar(select(CrmWebhookDelivery))
                assert row.recipient_email == "hook@example.com"
                assert row.user_id is None and row.tg_id is None
                assert await session.scalar(select(func.count(User.id))) == int(mode != "missing")
                rule = await crm_webhooks.get_rule(session, rule_id)
                assert rule.messages_sent == 1 and rule.messages_failed == 0
    asyncio.run(check())


@pytest.mark.parametrize("email", [None, "", "123", "user@localhost", "one@example.com,two@example.com", "one@example.com\r\nBcc: other@example.com", "Name <one@example.com>", 123])
def test_invalid_webhook_email_is_skipped_without_database_or_xray_fallback(email):
    async def check():
        async with _database("existing") as (factory, rule_id):
            with _io(factory) as (send, local, _, _):
                await runner.execute_crm_webhook(_payload(email))
                send.assert_not_awaited()
                local.assert_not_awaited()
            async with factory() as session:
                rule = await crm_webhooks.get_rule(session, rule_id)
                assert rule.webhooks_received == 1
                assert rule.messages_sent == rule.messages_failed == 0
                assert await session.scalar(select(func.count(CrmWebhookDelivery.id))) == 0
    asyncio.run(check())


def test_webhook_email_cooldown_is_per_normalized_address():
    async def check():
        async with _database() as (factory, rule_id):
            with _io(factory) as (send, _, _, _):
                await runner.execute_crm_webhook(_payload(" Hook@Example.COM "))
                await runner.execute_crm_webhook(_payload("hook@example.com"))
                await runner.execute_crm_webhook(_payload("other@example.com"))
                assert [call.kwargs["to"] for call in send.await_args_list] == ["hook@example.com", "other@example.com"]
            async with factory() as session:
                rule = await crm_webhooks.get_rule(session, rule_id)
                assert rule.messages_sent == 2 and rule.webhooks_received == 3
    asyncio.run(check())


def test_webhook_smtp_failure_counts_and_does_not_start_cooldown():
    async def check():
        async with _database() as (factory, rule_id):
            with _io(factory) as (send, _, _, _):
                send.side_effect = [MailerError("failed"), None]
                for _ in range(3):
                    await runner.execute_crm_webhook(_payload())
                assert send.await_count == 2
            async with factory() as session:
                rule = await crm_webhooks.get_rule(session, rule_id)
                assert rule.messages_sent == rule.messages_failed == 1
                assert await session.scalar(select(func.count(CrmWebhookDelivery.id))) == 1
    asyncio.run(check())


@pytest.mark.parametrize("blocked", ["local", "webhook"])
def test_webhook_email_and_local_actions_have_independent_cooldowns(blocked):
    async def check():
        async with _database("existing", actions=[EMAIL, {"type": "send_message", "text": "Hi"}]) as (factory, rule_id):
            async with factory() as session:
                await crm_webhooks.record_delivery(
                    session, rule_id=rule_id, tg_id=101 if blocked == "local" else None,
                    user_id=1 if blocked == "local" else None,
                    recipient_email="hook@example.com" if blocked == "webhook" else None,
                )
                await session.commit()
            with _io(factory) as (send, local, _, _):
                await runner.execute_crm_webhook(_payload())
                assert send.await_count == int(blocked == "local")
                assert local.await_count == int(blocked == "webhook")
                if local.await_count:
                    assert all(a["type"] != "send_email" for a in local.await_args.args[3])
    asyncio.run(check())


@pytest.mark.parametrize("flag", [False, True])
def test_webhook_option_off_or_action_disabled_keeps_unknown_users_skipped(flag):
    async def check():
        actions = [{**EMAIL, "send_to_email_from_webhook": flag, "enabled": not flag}]
        async with _database(actions=actions) as (factory, _):
            with _io(factory) as (send, local, _, _):
                await runner.execute_crm_webhook(_payload())
                send.assert_not_awaited()
                local.assert_not_awaited()
    asyncio.run(check())


def test_webhook_flag_is_validated_and_restricted_to_webhook_rules():
    validate_actions([EMAIL], allow_webhook_email=True)
    with pytest.raises(ValueError, match="only available for webhooks"):
        validate_actions([EMAIL])
    with pytest.raises(ValueError, match="must be a boolean"):
        validate_actions([{**EMAIL, "send_to_email_from_webhook": "false"}], allow_webhook_email=True)


def test_api_preserves_webhook_email_option_on_create_and_update():
    from dashboard.backend.routers import crm

    async def check():
        async with _database() as (factory, _):
            with patch.object(crm, "async_session", factory):
                created = await crm.create_webhook_rule(crm.CrmWebhookRuleCreate(scope="user", event="user.expired", actions=[EMAIL]), user="test")
                assert created.actions[0]["send_to_email_from_webhook"] is True
                updated = await crm.update_webhook_rule(created.id, crm.CrmWebhookRuleUpdate(actions=[{**EMAIL, "send_to_email_from_webhook": False}]), _="test")
                assert updated.actions[0]["send_to_email_from_webhook"] is False
    asyncio.run(check())
