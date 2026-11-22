"""Exercise the actual Telegram dispatcher, Dashboard API and shared attachment store."""
import asyncio
import os
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import SimpleEventIsolation
from aiogram.types import Update
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlalchemy import func, select

from common_db import Base
from common_db.models import SupportTicket, User
from tests.test_support_workflow_api import support_api


@pytest.fixture
def support(monkeypatch, tmp_path):
    from app.database import requests
    from app.support import router, tickets
    from dashboard.backend.routers import support as dashboard

    url = os.environ.get("SUPPORT_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Set SUPPORT_TEST_POSTGRES_URL to run Telegram support integration tests")
    schema = "support_test_" + uuid4().hex
    engine = create_async_engine(url, poolclass=NullPool, connect_args={"server_settings": {"search_path": schema}})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async def seed():
        async with engine.begin() as conn:
            await conn.execute(CreateSchema(schema))
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(User.__table__.insert(), [{"tg_id": 101, "username": "alice"}, {"tg_id": 202, "username": "bob"}])

    async def cleanup():
        async with engine.begin() as conn:
            await conn.execute(DropSchema(schema, cascade=True))
        await engine.dispose()

    app, _ = support_api(factory, tmp_path, monkeypatch)
    for module in (requests, tickets, router):
        monkeypatch.setattr(module, "async_session", factory)
    monkeypatch.setattr(tickets, "uploads_dir", lambda: str(tmp_path))
    config = {"support_token": "111:Support", "token": "222:Seller", "admin_id": 777,
              "miniapp_url": "https://test.invalid/bot/miniapp"}
    monkeypatch.setattr(router, "secrets", config)
    monkeypatch.setattr(dashboard, "get_config", lambda: config)
    monkeypatch.setattr(dashboard, "get_bot_token", lambda: config["token"])
    operator, customer = AsyncMock(), AsyncMock()
    monkeypatch.setattr(router, "send_notification", operator)
    monkeypatch.setattr(dashboard, "send_notification", customer)
    asyncio.run(seed())
    try:
        with TestClient(app) as http:
            yield http, factory, operator, customer
    finally:
        asyncio.run(cleanup())


def png():
    buf = BytesIO()
    Image.new("RGB", (2, 2)).save(buf, format="PNG")
    return buf.getvalue()


def test_both_bots_register_one_account(support):
    from app.database.requests import set_user
    _, factory, _, _ = support

    async def run():
        ids = await asyncio.gather(set_user(333), set_user(333, initial_language="en"), set_user(333))
        assert len(set(ids)) == 1
        async with factory() as session:
            assert await session.scalar(select(func.count()).select_from(User).where(User.tg_id == 333)) == 1
            user = await session.get(User, ids[0])
            assert user.username is None
    asyncio.run(run())


@pytest.mark.parametrize("token", ["", "yoursupportbottoken", "123456789:AnotherSecret", "999:ValidButLocalDatabase"])
def test_optional_support_identity(monkeypatch, token):
    from bot import main
    monkeypatch.setattr(main, "secrets", {"support_token": token})
    assert main.configured_support_bot() is None


def test_draft_and_active_ticket_limits(support):
    from app.support import tickets
    from fastapi import UploadFile
    from support_attachments import AttachmentValidationError

    async def run():
        async def submit(text="Problem", files=(), ticket_id=None):
            return await tickets.submit(1, ticket_id=ticket_id, category="other", text=text, files=files, lang="ru")
        with pytest.raises(tickets.TicketError, match="need_text"):
            await submit(text="")
        with pytest.raises(tickets.TicketError, match="text_limit"):
            await submit(text="x" * 4001)
        with pytest.raises(AttachmentValidationError):
            await submit(files=[UploadFile(BytesIO(png())) for _ in range(4)])
        with pytest.raises(AttachmentValidationError):
            await submit(files=[UploadFile(BytesIO(b"x" * (5 * 1024 * 1024 + 1)))])
        ticket_id = await submit()
        await tickets.change_status(1, ticket_id, reopen=False)
        with pytest.raises(tickets.TicketError, match="closed"):
            await submit(ticket_id=ticket_id)
        for _ in range(5):
            await submit()
        with pytest.raises(tickets.TicketError, match="limit"):
            await submit()
        with pytest.raises(tickets.TicketError, match="limit"):
            await tickets.change_status(1, ticket_id, reopen=True)
    asyncio.run(run())


def test_support_chat_through_dashboard(support, monkeypatch, tmp_path):
    from app.support import router
    http, factory, operator, customer = support
    calls = []
    data = png()

    async def capture(bot, method, **kwargs):
        calls.append(method)
        return True

    async def download(bot, file_id, destination):
        destination.write(b"broken" if file_id == "broken" else data)
        destination.seek(0)
    monkeypatch.setattr(Bot, "__call__", capture)
    monkeypatch.setattr(Bot, "download", download)

    async def run():
        dp = Dispatcher(events_isolation=SimpleEventIsolation())
        dp.include_router(router.router)
        bot = Bot("111:Support")
        seq = 0

        async def feed(*, action=None, user=333, **fields):
            nonlocal seq
            seq += 1
            actor = {"id": user, "is_bot": False, "first_name": "A", "language_code": "en"}
            message = {"message_id": seq, "date": 1, "chat": {"id": user, "type": "private"}, "from": actor, **fields}
            if action:
                payload = {"callback_query": {"id": str(seq), "from": actor, "chat_instance": "test",
                                              "message": message, "data": action}}
            else:
                payload = {"message": message}
            await dp.feed_update(bot, Update.model_validate({"update_id": seq, **payload}))
            return calls[-1]

        def button(method, prefix):
            return next(b.callback_data for row in method.reply_markup.inline_keyboard for b in row
                        if b.callback_data.startswith("st:" + prefix))

        start = await feed(text="/start")
        assert "order number" in start.text and button(start, "list")
        await feed(action=button(start, "new"))
        prompt = await feed(action="st:category:payment")
        assert "subscription link" in prompt.text
        await feed(photo=[{"file_id": "photo", "file_unique_id": "1", "width": 2, "height": 2}],
                   caption="Payment issue", media_group_id="album")
        draft = await feed(document={"file_id": "doc", "file_unique_id": "2", "file_name": "screen.png"},
                           media_group_id="album")
        send = button(draft, "send:")
        sent = await feed(action=send)
        view = button(sent, "view:")
        ticket_id = int(view.split(":")[-1])
        assert "expired" in (await feed(action=send)).text
        operator.assert_awaited_once()
        notification = operator.await_args.args[2]
        assert "Payment issue" not in notification["text"]
        assert notification["reply_markup"]["inline_keyboard"][0][0]["url"].endswith(f"?ticket={ticket_id}")

        path = f"/admin/api/support/tickets/{ticket_id}"
        thread = http.get(path).json()
        first = thread["messages"][0]
        assert first["text"] == "Payment issue" and len(first["attachments"]) == 2
        att = first["attachments"][0]["id"]
        assert http.get(path + f"/attachments/{att}").content == data
        image = ("operator.png", data, "image/png")
        assert http.post(path + "/reply", data={"text": "Private", "internal": "true"}, files={"images": image}).is_success
        customer.assert_not_awaited()
        note_att = http.get(path).json()["messages"][-1]["attachments"][0]["id"]
        assert "unavailable" in (await feed(action=f"st:image:{ticket_id}:{note_att}")).text
        assert http.post(path + "/reply", data={"text": "Public reply"}, files={"images": image}).is_success
        _, url, body = customer.await_args.args
        assert url.endswith("111:Support/sendMessage") and "Public reply" in body["text"]
        assert body["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == view
        calls.clear()
        await feed(action=view)
        reply = next(m for m in calls if "Public reply" in (getattr(m, "text", "") or ""))
        assert all("Private" not in (getattr(m, "text", "") or "") for m in calls)
        image_action = button(reply, "image:")
        assert (await feed(action=image_action)).document.path.read_bytes() == data
        assert "недоступно" in (await feed(action=image_action, user=202)).text
        assert "недоступно" in (await feed(action=view, user=202)).text

        await feed(action=f"st:reply:{ticket_id}")
        before = set(tmp_path.rglob("*.png"))
        await feed(document={"file_id": "good", "file_unique_id": "good"})
        invalid = await feed(document={"file_id": "broken", "file_unique_id": "bad"})
        correction = await feed(action=button(invalid, "send:"))
        assert "Check your images" in correction.text and set(tmp_path.rglob("*.png")) == before
        await feed(action=button(correction, "reset:"))
        draft = await feed(document={"file_id": "good", "file_unique_id": "good"})
        await feed(action=button(draft, "send:"))
        assert http.get(path).json()["messages"][-1]["text"] == ""
        await feed(action=f"st:resolve:{ticket_id}")
        assert http.get(path).json()["status"] == "closed"
        await feed(action=f"st:reopen:{ticket_id}")
        assert http.get(path).json()["status"] == "open"
        await feed(action=f"st:resolve:{ticket_id}")
        async with factory.begin() as session:
            t = await session.get(SupportTicket, ticket_id)
            t.closed_at = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat(timespec="seconds")
            assert t.user_read_id == t.last_admin_message_id
        assert "expired" in (await feed(action=f"st:reopen:{ticket_id}")).text
        # An existing Mini App ticket is immediately available to its Telegram owner.
        legacy = http.post("/mini/api/support/tickets/create", data={"message": "From web"}).json()["id"]
        listing = await feed(action="st:list:0", user=101)
        assert button(listing, "view:") == f"st:view:{legacy}"
        old_path = f"/admin/api/support/tickets/{legacy}"
        assert http.post(old_path + "/reply", data={"text": "Original channel"}).is_success
        assert customer.await_args.args[1].endswith("222:Seller/sendMessage")
        await feed(action=f"st:reply:{legacy}", user=101)
        draft = await feed(text="Continue here", user=101)
        await feed(action=button(draft, "send:"), user=101)
        assert http.post(old_path + "/reply", data={"text": "Telegram channel"}).is_success
        assert customer.await_args.args[1].endswith("111:Support/sendMessage")
        await bot.session.close()

    asyncio.run(run())
