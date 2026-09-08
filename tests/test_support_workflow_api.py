"""End-to-end ticket API contracts, using an isolated database and no Telegram."""
import asyncio
import io
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import Integer
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from common_db import Base
from common_db.models import User, SupportTicket, SupportMessage, SupportAttachment


@pytest.fixture
def client(tmp_path, monkeypatch):
    from miniapp.backend.routers import support as mini
    from dashboard.backend.routers import support as admin
    from miniapp.backend.android import support_router as android
    from miniapp.backend import support_actions, support_create
    for model in (SupportTicket, SupportMessage, SupportAttachment):
        monkeypatch.setattr(model.__table__.c.id, "type", Integer())
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'support.sqlite'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def seed():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with factory() as session:
            session.add_all([User(id=1, tg_id=101, username="alice"), User(id=2, tg_id=202, username="bob")])
            await session.commit()
    asyncio.run(seed())
    for module in (mini, admin, android, support_actions, support_create):
        monkeypatch.setattr(module, "async_session", factory)
        if hasattr(module, "get_support_uploads_dir"):
            monkeypatch.setattr(module, "get_support_uploads_dir", lambda: str(tmp_path))
        if hasattr(module, "get_config"):
            monkeypatch.setattr(module, "get_config", lambda: {})
    monkeypatch.setattr(mini, "get_admin_bot_token", lambda: "")
    monkeypatch.setattr(mini, "get_admin_id", lambda: None)
    monkeypatch.setattr(admin, "get_bot_token", lambda: "")
    monkeypatch.setattr(android, "get_admin_bot_token", lambda: "")
    monkeypatch.setattr(android, "get_admin_id", lambda: None)
    app = FastAPI()
    # Separate prefixes like the reverse proxy used in production.
    app.include_router(mini.router, prefix="/mini")
    app.include_router(admin.router, prefix="/admin")
    app.include_router(android.router)
    app.dependency_overrides[android.deps.get_current_user] = lambda: SimpleNamespace(id=1, email="alice@example.invalid")
    app.dependency_overrides[mini.get_tg_user] = lambda: SimpleNamespace(tg_id=101, username="alice")
    app.dependency_overrides[admin.get_current_user] = lambda: "admin"
    with TestClient(app) as c:
        yield c, app, mini
    asyncio.run(engine.dispose())


def create(c):
    r = c.post("/mini/api/support/tickets/create", data={"category": "connection", "platform": "Android", "message": "Cannot connect"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_reply_queue_read_and_resolution(client):
    c, _, _ = client
    ticket = create(c)
    a = f"/admin/api/support/tickets/{ticket}"
    u = f"/mini/api/support/tickets/{ticket}"
    assert c.get("/admin/api/support/tickets?queue=needs_reply").json()["total"] == 1
    assert c.post(a + "/reply", data={"text": "Try another network"}).status_code == 200
    detail = c.get(u).json()
    assert detail["status"] == "waiting_user" and detail["unread"]
    assert c.post(u + "/read", json={"message_id": detail["last_message_id"]}).status_code == 200
    assert not c.get(u).json()["unread"]
    # A stale read cursor cannot move the read watermark backwards.
    c.post(u + "/read", json={"message_id": 0})
    assert not c.get(u).json()["unread"]
    c.post(u + "/messages", data={"text": "Still broken"})
    assert c.get(a).json()["status"] == "open"
    c.post(a + "/reply", data={"text": "Fixed", "close": "true"})
    assert c.get(u).json()["can_reopen"]
    assert c.post(u + "/messages", data={"text": "Late"}).status_code == 409
    c.post(u + "/outcome", json={"action": "reopen"})
    assert c.get(a).json()["status"] == "open"
    c.post(u + "/outcome", json={"action": "resolved"})
    assert c.get(a).json()["status"] == "closed"


def test_notes_and_attachments_are_private(client):
    c, app, mini = client
    ticket = create(c)
    data = io.BytesIO()
    Image.new("RGB", (2, 2)).save(data, format="PNG")
    a = f"/admin/api/support/tickets/{ticket}"
    u = f"/mini/api/support/tickets/{ticket}"
    c.post(a + "/reply", data={"text": "Private investigation", "internal": "true"}, files={"images": ("note.png", data.getvalue(), "image/png")})
    detail = c.get(a).json()
    assert detail["status"] == "open"
    note = detail["messages"][-1]
    assert note["sender"] == "note"
    assert all(m["sender"] != "note" for m in c.get(u).json()["messages"])
    attachment = note["attachments"][0]["id"]
    assert c.get(u + f"/attachments/{attachment}").status_code == 404
    assert c.get(a + f"/attachments/{attachment}").status_code == 200
    app.dependency_overrides[mini.get_tg_user] = lambda: SimpleNamespace(tg_id=202, username="bob")
    assert c.get(u).status_code == 404
    assert c.post(u + "/read", json={"message_id": 1}).status_code == 404
    assert c.post(u + "/outcome", json={"action": "resolved"}).status_code == 404


def test_initial_photo_search_and_claim(client):
    c, _, _ = client
    data = io.BytesIO()
    Image.new("RGB", (2, 2)).save(data, format="PNG")
    r = c.post("/mini/api/support/tickets/create", data={"category": "payment", "message": "Payment issue"}, files={"images": ("first.png", data.getvalue(), "image/png")})
    assert r.status_code == 201, r.text
    assert len(r.json()["messages"][0]["attachments"]) == 1
    ticket = r.json()["id"]
    for query in ("alice", "101", str(ticket)):
        assert c.get("/admin/api/support/tickets", params={"search": query}).json()["total"] == 1
    a = f"/admin/api/support/tickets/{ticket}"
    assert c.post(a + "/claim").status_code == 200
    assert c.get(a).json()["assignee"] == "admin"
    assert c.delete(a + "/claim").status_code == 200
    assert c.post("/mini/api/support/tickets/create", data={"message": "test", "payment_id": "someone-else"}).status_code == 404


def test_android_shares_ticket_actions_and_visibility(client):
    c, _, _ = client
    ticket = create(c)
    a = f"/admin/api/support/tickets/{ticket}"
    u = f"/api/android/support/tickets/{ticket}"
    assert c.get(u).status_code == 200
    c.post(a + "/reply", data={"text": "Internal", "internal": "true"})
    assert len(c.get(u).json()["messages"]) == 1
    c.post(a + "/reply", data={"text": "Public"})
    assert c.get(u).json()["unread"]
    c.post(u + "/outcome", json={"action": "resolved"})
    assert c.get(u).json()["status"] == "closed"


def test_active_limit_includes_waiting_and_in_progress(client):
    c, _, _ = client
    for _ in range(5):
        ticket = create(c)
        c.post(f"/admin/api/support/tickets/{ticket}/reply", data={"text": "Waiting on customer"})
    response = c.post("/mini/api/support/tickets/create", data={"message": "Sixth request"})
    assert response.status_code == 429
