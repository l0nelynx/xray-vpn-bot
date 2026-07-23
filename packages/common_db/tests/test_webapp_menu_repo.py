"""Tariff Constructor repository invariants shared by every client."""
from __future__ import annotations

from common_db.models import WebAppMenuNode
from common_db.repo.webapp_menu import build_tree, invoice_target, localized_text


def _node(node_id: int, **values) -> WebAppMenuNode:
    defaults = {
        "parent_id": None,
        "text_ru": f"RU {node_id}",
        "text_en": f"EN {node_id}",
        "action": "buttons",
        "sort_order": 0,
        "is_active": True,
    }
    defaults.update(values)
    return WebAppMenuNode(id=node_id, **defaults)


def _invoice(node_id: int, **values) -> WebAppMenuNode:
    defaults = {
        "action": "invoice",
        "invoice_provider": "crypto",
        "invoice_amount": 10,
        "invoice_currency": "USDT",
        "invoice_method": "default",
        "invoice_days": 30,
        "invoice_squad_id": "squad",
        "invoice_external_squad_id": "external",
    }
    defaults.update(values)
    return _node(node_id, **defaults)


def test_localization_uses_requested_language_then_ru_en_fallback() -> None:
    node = _node(1, text_ru="Русский", text_en="English")
    assert localized_text(node, "en") == "English"
    assert localized_text(node, "ru") == "Русский"
    node.text_en = ""
    assert localized_text(node, "en") == "Русский"
    node.text_ru = ""
    node.text_en = "English"
    assert localized_text(node, "ru") == "English"


def test_tree_sorts_and_prunes_inactive_or_empty_ancestors() -> None:
    nodes = [
        _node(1, text_ru="Root", sort_order=2),
        _invoice(2, parent_id=1, sort_order=3),
        _invoice(3, parent_id=1, sort_order=1),
        _node(4, text_ru="Inactive", is_active=False),
        _invoice(5, parent_id=4),
        _node(6, text_ru="Empty"),
    ]
    tree = build_tree(nodes, lang="ru")
    assert [item["id"] for item in tree] == [1]
    assert [item["id"] for item in tree[0]["children"]] == [3, 2]


def test_tree_prunes_cycles_and_client_specific_providers() -> None:
    nodes = [
        _node(1),
        _invoice(2, parent_id=1, invoice_provider="stars", invoice_currency="XTR"),
        _invoice(3, parent_id=1, invoice_provider="crypto"),
        _node(4, parent_id=5),
        _node(5, parent_id=4),
    ]
    web_tree = build_tree(nodes, lang="en", allowed_providers={"crypto"})
    assert [item["id"] for item in web_tree[0]["children"]] == [3]
    miniapp_tree = build_tree(
        nodes, lang="en", allowed_providers={"crypto", "stars"}
    )
    assert [item["id"] for item in miniapp_tree[0]["children"]] == [2, 3]
    assert all(item["id"] not in {4, 5} for item in miniapp_tree)


def test_invoice_validation_requires_complete_positive_delivery_snapshot() -> None:
    assert invoice_target(_invoice(1)) is not None
    assert invoice_target(_invoice(2, invoice_amount=0)) is None
    assert invoice_target(_invoice(3, invoice_days=0)) is None
    assert invoice_target(_invoice(4, invoice_squad_id=None)) is None
    assert invoice_target(_invoice(5, invoice_external_squad_id=None)) is None
    assert invoice_target(
        _invoice(6, invoice_provider="stars", invoice_currency="RUB")
    ) is None
    assert invoice_target(
        _invoice(
            7,
            invoice_provider="stars",
            invoice_currency="XTR",
            invoice_amount=10.5,
        )
    ) is None
    assert invoice_target(
        _invoice(
            8,
            invoice_provider="stars",
            invoice_currency="XTR",
            invoice_amount=10,
        )
    ) is not None
