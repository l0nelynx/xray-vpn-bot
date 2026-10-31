"""Language-specific payment ordering persists and reaches every client."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from common_db.models import User, WebAppMenuNode
from common_db.repo.webapp_menu import build_tree, sort_menu_siblings


def _category(node_id, **values):
    return WebAppMenuNode(
        id=node_id, parent_id=None, text_ru=f"Категория {node_id}",
        text_en=f"Category {node_id}", action="buttons", sort_order=node_id,
        is_active=True, **values,
    )


def _invoice(node_id, parent_id=10, **values):
    defaults = dict(
        id=node_id, parent_id=parent_id, text_ru=f"Опция {node_id}",
        text_en=f"Option {node_id}", action="invoice", sort_order=node_id,
        sort_order_ru=node_id - 11, sort_order_en=13 - node_id, is_active=True,
        invoice_provider="platega", invoice_amount=100, invoice_currency="RUB",
        invoice_method="2", invoice_days=30,
        invoice_internal_squad_ids=["11111111-1111-4111-8111-111111111111"],
        invoice_external_squad_id="22222222-2222-4222-8222-222222222222",
        invoice_traffic_limit_bytes=0, invoice_traffic_limit_strategy="NO_RESET",
    )
    defaults.update(values)
    return WebAppMenuNode(**defaults)


@pytest.fixture
def constructor(session_factory, monkeypatch):
    from dashboard.backend.routers import webapp_menu as router

    monkeypatch.setattr(router, "async_session", session_factory)
    monkeypatch.setattr(router, "bump_cache_version", AsyncMock())

    async def seed():
        async with session_factory() as session:
            session.add_all([
                _category(10), _category(20), _invoice(11), _invoice(12), _invoice(13),
                _invoice(21, 20, sort_order_ru=0, sort_order_en=0),
                User(id=1, tg_id=101, language="ru"),
            ])
            await session.commit()

    asyncio.run(seed())
    return router


async def _orders(session_factory, parent_id=10):
    async with session_factory() as session:
        nodes = list((await session.scalars(select(WebAppMenuNode).where(
            WebAppMenuNode.parent_id == parent_id, WebAppMenuNode.action == "invoice",
        ))).all())
        output = []
        for lang in ("ru", "en"):
            ordered = sort_menu_siblings(nodes, lang)
            assert [getattr(node, f"sort_order_{lang}") for node in ordered] == list(range(len(nodes)))
            output.append([node.id for node in ordered])
        return tuple(output)


def test_positions_shift_independently_and_persist_after_reload(constructor, session_factory):
    router = constructor

    async def run():
        assert await _orders(session_factory) == ([11, 12, 13], [13, 12, 11])
        await router.update_node(11, router.WebAppMenuNodeUpdate(sort_order_en=0), "admin")
        assert await _orders(session_factory) == ([11, 12, 13], [11, 13, 12])
        await router.update_node(12, router.WebAppMenuNodeUpdate(sort_order_ru=0), "admin")
        assert await _orders(session_factory) == ([12, 11, 13], [11, 13, 12])
        tree = await router.get_tree("admin")
        option = next(node for node in tree[0]["children"] if node["id"] == 11)
        assert option["sort_order_ru"] == 1 and option["sort_order_en"] == 0
        # Values larger than the current list are clamped to its last position.
        await router.update_node(11, router.WebAppMenuNodeUpdate(sort_order_en=99), "admin")
        assert await _orders(session_factory) == ([12, 11, 13], [13, 12, 11])
        assert await _orders(session_factory, 20) == ([21], [21])

    asyncio.run(run())


def test_insert_move_delete_and_type_change_keep_dense_positions(constructor, session_factory):
    router = constructor

    async def run():
        created = await router.create_node(router.WebAppMenuNodeCreate(
            parent_id=10, text_ru="Копия", text_en="Copy", action="invoice", is_active=False,
            sort_order=100, sort_order_ru=1, sort_order_en=2,
        ), "admin")
        new_id = created.id
        assert await _orders(session_factory) == ([11, new_id, 12, 13], [13, 12, new_id, 11])
        await router.update_node(new_id, router.WebAppMenuNodeUpdate(parent_id=20), "admin")
        assert await _orders(session_factory) == ([11, 12, 13], [13, 12, 11])
        assert await _orders(session_factory, 20) == ([21, new_id], [21, new_id])
        await router.delete_node(12, "admin")
        assert await _orders(session_factory) == ([11, 13], [13, 11])
        category = await router.update_node(13, router.WebAppMenuNodeUpdate(action="buttons"), "admin")
        assert category.sort_order_ru is None and category.sort_order_en is None
        assert await _orders(session_factory) == ([11], [11])
        await router.update_node(new_id, router.WebAppMenuNodeUpdate(parent_id=None, sort_order_ru=0), "admin")
        assert await _orders(session_factory, None) == ([new_id], [new_id])

    asyncio.run(run())


def test_reorder_reparents_append_in_both_languages(constructor, session_factory):
    router = constructor

    async def run():
        await router.reorder(router.ReorderRequest(items=[{
            "id": 12, "parent_id": 20, "sort_order": 5,
        }]), "admin")
        assert await _orders(session_factory) == ([11, 13], [13, 11])
        assert await _orders(session_factory, 20) == ([21, 12], [21, 12])

    asyncio.run(run())


def test_localized_sort_preserves_categories_and_legacy_order():
    nodes = [_invoice(11), _category(15), _invoice(12), _invoice(13)]
    # Deliberately place a category between the invoice slots.
    nodes[1].sort_order = 11
    assert [node.id for node in sort_menu_siblings(nodes, "en")] == [13, 15, 12, 11]
    assert [node.id for node in sort_menu_siblings(nodes, "ru")] == [11, 15, 12, 13]
    for node in nodes:
        node.sort_order_ru = node.sort_order_en = None
    assert [node.id for node in sort_menu_siblings(nodes, "en")] == [11, 15, 12, 13]


@pytest.mark.parametrize("lang,expected", [("ru", [11, 12, 13]), ("en", [13, 12, 11])])
def test_order_reaches_bot_miniapp_web_and_android(constructor, session_factory, monkeypatch, lang, expected):
    from app.bot_constructor.handlers import payments as bot
    from miniapp.backend.android import payments_router as android
    from miniapp.backend.routers import menu as miniapp
    from miniapp.backend.web import web_router as web

    for module in (bot, android, miniapp, web):
        monkeypatch.setattr(module, "async_session", session_factory)
    monkeypatch.setattr(bot.rq, "get_user_language", AsyncMock(return_value=lang))
    monkeypatch.setattr(bot, "get_user_lang", AsyncMock(return_value=SimpleNamespace(
        btn_back="Back", btn_to_main="Main", msg_plan_not_found="Missing",
    )))
    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=101), answer=AsyncMock(),
        message=SimpleNamespace(edit_text=AsyncMock()),
    )

    async def run():
        async with session_factory() as session:
            user = await session.get(User, 1)
            user.language = lang
            await session.commit()
            nodes = list((await session.scalars(select(WebAppMenuNode))).all())
        shared = build_tree(nodes, lang=lang)
        assert [node["id"] for node in shared[0]["children"]] == expected
        tree = await miniapp.get_menu_tree(SimpleNamespace(tg_id=101))
        assert [node["id"] for node in tree["tree"][0]["children"]] == expected
        client_user = SimpleNamespace(id=1, language=lang)
        tree = await android.get_payments_menu(client_user)
        assert [node.id for node in tree.tree[0].children] == expected
        tree = await web.web_payments_menu(client_user)
        assert [node.id for node in tree.tree[0].children] == expected
        await bot._render_level(callback, 10)
        keyboard = callback.message.edit_text.call_args.kwargs["reply_markup"]
        ids = [int(row[0].callback_data.rsplit(":", 1)[-1]) for row in keyboard.inline_keyboard[:-2]]
        assert ids == expected
        first_label = keyboard.inline_keyboard[0][0].text
        assert first_label.startswith("Option" if lang == "en" else "Опция")

    asyncio.run(run())


def test_api_rejects_negative_positions():
    from dashboard.backend.schemas.webapp_menu import WebAppMenuNodeCreate, WebAppMenuNodeUpdate

    with pytest.raises(ValidationError):
        WebAppMenuNodeUpdate(sort_order_en=-1)
    with pytest.raises(ValidationError):
        WebAppMenuNodeCreate(text_ru="RU", text_en="EN", sort_order_ru=-1)
