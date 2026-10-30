"""Every payment surface must pass the stored payer identity to the gateway."""
from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request

from common_db.models import User
from payments.base import Invoice


@pytest.mark.parametrize(("surface", "email", "tg_id"), [
    (surface, email, 5512345678)
    for surface in ("bot", "miniapp", "web", "android")
    for email in (None, "buyer@gmail.com")
] + [
    ("web", "buyer@gmail.com", None),
    ("android", "buyer@gmail.com", None),
])
def test_invoice_uses_database_user_identity(with_app_db, monkeypatch, surface, email, tg_id):
    user = SimpleNamespace(id=42, tg_id=tg_id, email=email, language="ru")
    invoice_data = {
        "provider": "platega", "amount": 500, "currency": "RUB", "method": "2",
        "days": 30, "tariff_slug": "test-plan", "squad_id": "squad",
        "internal_squad_ids": ["squad"], "external_squad_id": None,
        "traffic_limit_bytes": 0, "traffic_limit_strategy": "NO_RESET",
        "remnawave_description": None, "remnawave_tag": None,
    }
    create_invoice = AsyncMock(return_value=Invoice(
        provider="platega", invoice_id="gateway-id", url="https://pay.platega.io/test",
        amount=500, currency="RUB",
    ))
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})

    async def run():
        async with with_app_db() as session:
            session.add(User(id=user.id, tg_id=user.tg_id, email=user.email))
            await session.commit()

        if surface == "bot":
            from app.bot_constructor.handlers import payments as module

            monkeypatch.setattr(module, "async_session", with_app_db)
            monkeypatch.setattr(module, "get_active_node", AsyncMock(
                return_value=SimpleNamespace(id=1, parent_id=None),
            ))
            monkeypatch.setattr(module, "_target_for_bot", lambda node: SimpleNamespace(**invoice_data))
            monkeypatch.setattr(module, "localized_text", lambda *args: "VPN")
            monkeypatch.setattr(module, "get_user_lang", AsyncMock(return_value=SimpleNamespace(
                btn_open="Open", btn_back="Back", btn_to_main="Main",
                msg_pay_link="{link}",
            )))
            monkeypatch.setattr(module.rq, "get_user_language", AsyncMock(return_value="ru"))
            monkeypatch.setattr(module.rq, "create_transaction", AsyncMock(return_value=object()))
            callback = SimpleNamespace(
                from_user=SimpleNamespace(id=user.tg_id, username="buyer"),
                answer=AsyncMock(), message=SimpleNamespace(edit_text=AsyncMock()),
            )
            endpoint = lambda: module._create_payment(callback, 1)
        elif surface == "miniapp":
            from miniapp.backend.routers import payments as module
            from miniapp.backend.schemas.payments import InvoiceCreateRequest

            monkeypatch.setattr(module, "load_menu_node", AsyncMock(return_value={"text": "VPN"}))
            monkeypatch.setattr(module, "invoice_from_node", lambda node: invoice_data)
            endpoint = lambda: inspect.unwrap(module.create_payment_invoice)(
                request=request, body=InvoiceCreateRequest(node_id=1),
                tg=SimpleNamespace(tg_id=user.tg_id, username="buyer"),
            )
        elif surface == "android":
            from miniapp.backend.android import payments_router as module

            monkeypatch.setattr(module, "_load_node", AsyncMock(return_value={}))
            monkeypatch.setattr(module, "_node_payload", lambda node: invoice_data)
            endpoint = lambda: inspect.unwrap(module.create_payment_invoice)(
                request=request, body=module.AndroidInvoiceRequest(node_id=1), user=user,
            )
        else:
            from miniapp.backend.web import web_router as module

            monkeypatch.setattr(module, "_load_node", AsyncMock(return_value={}))
            monkeypatch.setattr(module, "_node_payload", lambda node, **kw: invoice_data)
            endpoint = lambda: inspect.unwrap(module.web_invoice)(
                request=request, body=module.WebInvoiceRequest(node_id=1), user=user,
            )

        monkeypatch.setattr(module, "async_session", with_app_db)
        monkeypatch.setattr(module, "create_invoice", create_invoice)
        monkeypatch.setattr(module, "notify_log", AsyncMock())
        if surface != "bot":
            monkeypatch.setattr(module, "_purchase_target_rw_id", AsyncMock(return_value=None))
        await endpoint()

    asyncio.run(run())
    create_invoice.assert_awaited_once()
    provider, invoice_request = create_invoice.call_args.args
    assert provider == "platega"
    assert invoice_request.user_id == user.id
    assert invoice_request.user_email == user.email
    assert invoice_request.user_tg_id == (user.tg_id or -user.id)
