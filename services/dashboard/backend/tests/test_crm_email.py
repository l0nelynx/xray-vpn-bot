"""Email-only recipients through scans, events, webhooks, and SMTP delivery."""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_db import Base
from common_db.models import User, CrmCampaign, CrmCampaignDelivery, CrmEventDelivery, CrmWebhookDelivery
from common_db.repo import crm_events, crm_webhooks
from dashboard.backend.crm_actions import execute_user_actions
from dashboard.backend.crm_conditions import evaluate_audience_user_ids
from dashboard.backend.crm_email import render_email
from dashboard.backend.crm_model_adapter import validate_actions

EMAIL = {"type": "send_email", "enabled": True, "subject": "Осталось {{days_left}} дня", "text": "Привет, {{username}}!\n\nПродлите подписку."}
CONDITIONS = [{"type": "segment", "segment_id": "all_users"}]


async def _with_db(check):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await check(async_sessionmaker(engine, expire_on_commit=False))
    finally:
        await engine.dispose()


def _user(**kwargs):
    return User(id=1, tg_id=None, email="alice@example.com", email_verified_at="2026-10-31", **kwargs)


def test_email_rendering_escapes_fields_and_preserves_plain_text():
    subject, plain, document = render_email(
        subject="Hello {{username}}", text='Line one\nLine two\n\n<script>alert(1)</script> & {{username}}',
        brand_name='A&B', logo_src='cid:logo',
        context={"username": "A&amp;B\r\nInjected: value"},
    )
    assert subject == "Hello A&B Injected: value"
    assert '<script>' not in document and '&lt;script&gt;' in document
    assert 'Line one<br>Line two' in document
    assert 'A&amp;B' in document and 'javascript:' not in document
    assert 'A&B' in plain and 'команда A&B' in plain


@pytest.mark.parametrize("patch_fields", [
    {"subject": ""}, {"subject": "x\r\nBcc: bad@example.com"},
    {"text": " "}, {"text": 10}, {"recipients": "unknown"},
])
def test_email_action_validation(patch_fields):
    with pytest.raises(ValueError):
        validate_actions([{**EMAIL, **patch_fields}])


@pytest.mark.parametrize("tg_id,verified,recipients,expected", [
    (None, True, "without_telegram", True),
    (101, True, "without_telegram", False),
    (101, True, "all", True),
    (None, False, "all", False),
])
def test_email_delivery_eligibility(tg_id, verified, recipients, expected):
    async def check():
        user = _user()
        user.tg_id = tg_id
        user.email_verified_at = "2026-10-31" if verified else None
        with patch("dashboard.backend.crm_actions.send_crm_email", new_callable=AsyncMock) as send, patch("dashboard.backend.crm_actions.tg_send", new_callable=AsyncMock) as telegram:
            result = await execute_user_actions(MagicMock(), user, None, [{**EMAIL, "recipients": recipients}], session=MagicMock())
            assert result.message_sent == expected
            assert result.message_skipped != expected
            assert send.await_count == int(expected)
            telegram.assert_not_awaited()
    asyncio.run(check())


def test_email_failure_is_counted_and_does_not_record_success():
    async def check():
        callback = AsyncMock()
        with patch("dashboard.backend.crm_actions.send_crm_email", new_callable=AsyncMock, side_effect=OSError("unavailable")):
            result = await execute_user_actions(MagicMock(), _user(), None, [EMAIL], session=MagicMock(), on_message_sent=callback)
            assert result.message_failed and not result.message_sent and not result.message_skipped
            assert result.errors == ["email send failed"]
            callback.assert_not_awaited()
    asyncio.run(check())


def test_mixed_channels_skip_telegram_for_email_only_user_and_record_once():
    async def check():
        callback = AsyncMock()
        with patch("dashboard.backend.crm_actions.send_crm_email", new_callable=AsyncMock) as send, patch("dashboard.backend.crm_actions.tg_send", new_callable=AsyncMock) as telegram:
            result = await execute_user_actions(MagicMock(), _user(), None, [EMAIL, {"type": "send_message", "text": "Hi"}], session=MagicMock(), on_message_sent=callback)
            assert result.message_sent and not result.message_failed
            send.assert_awaited_once()
            telegram.assert_not_awaited()
            callback.assert_awaited_once()
    asyncio.run(check())


def test_email_scan_filters_contacts_and_supports_stable_allowlist():
    async def check(factory):
        async with factory() as session:
            session.add_all([
                _user(),
                User(id=2, tg_id=102, email="linked@example.com", email_verified_at="2026-10-31"),
                User(id=3, email="unverified@example.com"),
                User(id=4, email="banned@example.com", email_verified_at="2026-10-31", is_banned=True),
                User(id=5, tg_id=105),
            ])
            await session.flush()
            ids, _ = await evaluate_audience_user_ids(session, None, CONDITIONS, [EMAIL])
            assert ids == [1]
            ids, _ = await evaluate_audience_user_ids(session, None, CONDITIONS, [{**EMAIL, "recipients": "all"}])
            assert set(ids) == {1, 2}
            ids, _ = await evaluate_audience_user_ids(session, None, CONDITIONS, [EMAIL, {"type": "send_message"}])
            assert set(ids) == {1, 2, 5}
            ids, _ = await evaluate_audience_user_ids(session, None, [*CONDITIONS, {"type": "user_allowlist", "user_ids": [1]}], [EMAIL])
            assert ids == [1]
    asyncio.run(_with_db(check))


@pytest.mark.parametrize("repeat_policy", ["once", "cooldown"])
def test_event_email_audience_survives_queue_and_repeat_policy(repeat_policy):
    from dashboard.backend import crm_event_runner, crm_runner

    async def check(factory):
        async with factory() as session:
            session.add(_user())
            event = await crm_events.create_event(
                session, name="email event", conditions=CONDITIONS, actions=[{**EMAIL, "recipients": "all"}],
                segment_type="all_users", segment_params={}, message_text="", attach_button=False,
                bonus_days=None, bonus_traffic_gb=None, run_at_time="12:00", frequency="daily",
                weekday=None, repeat_policy=repeat_policy, repeat_cooldown_days=7, created_by="test",
            )
            await session.commit()
            event_id = event.id
        rw = MagicMock(get_all_users_for_crm=AsyncMock(return_value=[]))
        with patch.object(crm_event_runner, "async_session", factory), patch.object(crm_event_runner, "_rw_client", return_value=rw):
            response = await crm_event_runner.run_crm_event(event_id)
            assert response["total"] == 1
            campaign_id = response["campaign_id"]
        with patch.object(crm_runner, "async_session", factory), patch.object(crm_runner, "_rw_client", return_value=rw), patch.object(crm_runner, "tg_bot_username", new_callable=AsyncMock, return_value=None), patch("dashboard.backend.crm_actions.send_crm_email", new_callable=AsyncMock):
            await crm_runner.execute_crm_campaign(campaign_id)
        async with factory() as session:
            campaign = await session.get(CrmCampaign, campaign_id)
            assert campaign.messages_sent == 1 and campaign.messages_failed == 0
            row = await session.scalar(select(CrmCampaignDelivery))
            assert row.user_id == 1 and row.tg_id is None and row.message_status == "sent"
            assert await crm_events.get_sent_user_ids(session, event_id) == {1}
            # Linking Telegram later must not reset the once policy.
            user = await session.get(User, 1)
            user.tg_id = 101
            user.email = "changed@example.com"
            await session.commit()
        with patch.object(crm_event_runner, "async_session", factory), patch.object(crm_event_runner, "_rw_client", return_value=rw):
            response = await crm_event_runner.run_crm_event(event_id)
            assert response["status"] == "empty"
    asyncio.run(_with_db(check))


def test_webhook_email_only_recipient_and_cooldown():
    from dashboard.backend import crm_webhook_runner

    async def check(factory):
        async with factory() as session:
            session.add(_user(rw_id=123))
            rule = await crm_webhooks.create_rule(session, name="Email", scope="user", event="user.expired", actions=[EMAIL], created_by="test", cooldown_hours=24)
            await session.commit()
            rule_id = rule.id
        payload = {"scope": "user", "event": "user.expired", "timestamp": "2026-10-31T12:00:00Z", "data": {"id": 123}}
        with patch.object(crm_webhook_runner, "async_session", factory), patch.object(crm_webhook_runner, "_rw_client", return_value=MagicMock()), patch.object(crm_webhook_runner, "_fetch_crm_user", new_callable=AsyncMock, return_value=None), patch.object(crm_webhook_runner, "tg_bot_username", new_callable=AsyncMock, return_value=None), patch("dashboard.backend.crm_actions.send_crm_email", new_callable=AsyncMock) as send:
            await crm_webhook_runner.execute_crm_webhook(payload)
            await crm_webhook_runner.execute_crm_webhook(payload)
            send.assert_awaited_once()
        async with factory() as session:
            rule = await crm_webhooks.get_rule(session, rule_id)
            assert rule.webhooks_received == 2 and rule.messages_sent == 1
            row = await session.scalar(select(CrmWebhookDelivery))
            assert row.user_id == 1 and row.tg_id is None
    asyncio.run(_with_db(check))


@pytest.mark.parametrize("port,use_tls,start_tls", [(465, True, False), (587, False, True)])
def test_shared_smtp_multipart_and_tls(port, use_tls, start_tls):
    from common_db.mailer import send_email

    async def check():
        with patch("common_db.mailer.aiosmtplib.send", new_callable=AsyncMock) as smtp:
            await send_email(config={"smtp_host": "smtp.example.com", "smtp_user": "sender@example.com", "smtp_port": port}, to="alice@example.com", subject="News", text="Plain", html='<img src="cid:logo">', inline_image=("logo", b"png-image"))
            message = smtp.await_args.args[0]
            assert smtp.await_args.kwargs["use_tls"] == use_tls
            assert smtp.await_args.kwargs["start_tls"] == start_tls
            assert message.get_body(preferencelist=("plain",)).get_content().strip() == "Plain"
            assert message.get_body(preferencelist=("html",)).get_content().strip() == '<img src="cid:logo">'
            image = next(part for part in message.walk() if part.get_content_type() == "image/png")
            assert image["Content-ID"] == "<logo>" and image.get_payload(decode=True) == b"png-image"
            assert message["Date"] and message["Message-ID"]
    asyncio.run(check())


def test_email_preview_uses_same_template_and_never_sends():
    from dashboard.backend.routers.crm import EmailPreviewRequest, preview_crm_email
    from dashboard.backend import crm_email

    async def check(factory):
        with patch("dashboard.backend.routers.crm.async_session", factory), patch.object(crm_email, "email_branding", new_callable=AsyncMock, return_value=("TestVPN", b"logo")), patch.object(crm_email, "send_email", new_callable=AsyncMock) as send:
            response = await preview_crm_email(EmailPreviewRequest(subject="Hello", text="Hi {{username}}"), _="test")
            assert 'data:image/png;base64,' in response["html"]
            assert "команда TestVPN" in response["html"]
            assert "{{username}}" not in response["html"]
            send.assert_not_awaited()
    asyncio.run(_with_db(check))


def test_crm_delivery_uses_shared_smtp_and_embeds_logo():
    from dashboard.backend import crm_email

    async def check():
        settings = {"smtp_host": "smtp.example.com", "smtp_user": "sender@example.com", "smtp_password": "test-only-password"}
        with patch.object(crm_email, "get_config", return_value=settings), patch.object(crm_email, "email_branding", new_callable=AsyncMock, return_value=("TestVPN", b"logo")), patch("common_db.mailer.aiosmtplib.send", new_callable=AsyncMock) as smtp:
            await crm_email.send_crm_email(MagicMock(), to="alice@example.com", action=EMAIL, context={"days_left": "3", "username": "Alice"})
            message = smtp.await_args.args[0]
            assert message["To"] == "alice@example.com"
            assert message["From"] == "sender@example.com"
            assert str(message["Subject"]) == "Осталось 3 дня"
            assert smtp.await_args.kwargs["password"] == settings["smtp_password"]
            assert "Привет, Alice!" in message.get_body(preferencelist=("plain",)).get_content()
            assert "cid:crm-brand-logo" in message.get_body(preferencelist=("html",)).get_content()
            logo = next(part for part in message.walk() if part.get_content_type() == "image/png")
            assert logo.get_payload(decode=True) == b"logo"
    asyncio.run(check())


def test_smtp_transport_failure_uses_shared_mailer_error():
    from common_db.mailer import MailerError, send_email
    from miniapp.backend.android.mailer import MailerError as VerificationMailerError

    assert MailerError is VerificationMailerError
    async def check():
        with patch("common_db.mailer.aiosmtplib.send", new_callable=AsyncMock, side_effect=TimeoutError()):
            with pytest.raises(MailerError, match="transport: TimeoutError"):
                await send_email(config={"smtp_host": "smtp.example.com", "smtp_user": "sender@example.com"}, to="alice@example.com", subject="Test", text="Body")
    asyncio.run(check())


def test_migration_backfills_legacy_delivery_ids(tmp_path):
    """Exercise actual SQLite batch DDL against an old schema, including duplicate tg_ids."""
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = Path(__file__).resolve().parents[4] / "alembic/versions/0047_crm_email_recipients.py"
    spec = importlib.util.spec_from_file_location("crm_email_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'migration.sqlite'}")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE users (id BIGINT PRIMARY KEY, tg_id BIGINT)"))
        conn.execute(sa.text("INSERT INTO users VALUES (1, 101), (2, 101)"))
        for table, owner in module.TABLES:
            conn.execute(sa.text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, {owner} BIGINT, tg_id BIGINT NOT NULL)"))
            conn.execute(sa.text(f"INSERT INTO {table} VALUES (1, 1, 101)"))
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
        for table, owner in module.TABLES:
            assert conn.scalar(sa.text(f"SELECT user_id FROM {table}")) == 1
            conn.execute(sa.text(f"INSERT INTO {table} (id, {owner}, tg_id, user_id) VALUES (2, 1, NULL, 3)"))
    engine.dispose()
