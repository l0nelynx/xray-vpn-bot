from __future__ import annotations

import pytest
from fastapi import HTTPException

from common_db.models import WebAppMenuNode
from dashboard.backend.routers.webapp_menu import _normalize_node, _validate_node


INTERNAL_A = "11111111-1111-4111-8111-111111111111"
INTERNAL_B = "22222222-2222-4222-8222-222222222222"
EXTERNAL = "33333333-3333-4333-8333-333333333333"


def _invoice(**overrides) -> WebAppMenuNode:
    values = {
        "id": 1,
        "parent_id": None,
        "text_ru": "Месяц",
        "text_en": "Month",
        "action": "invoice",
        "sort_order": 0,
        "is_active": True,
        "invoice_provider": "crypto",
        "invoice_amount": 10,
        "invoice_currency": "USDT",
        "invoice_method": "default",
        "invoice_days": 30,
        "invoice_internal_squad_ids": [INTERNAL_A, INTERNAL_A, INTERNAL_B],
        "invoice_external_squad_id": f" {EXTERNAL} ",
        "invoice_traffic_limit_bytes": 50 * 1024**3,
        "invoice_traffic_limit_strategy": "month_rolling",
        "invoice_remnawave_description": " Premium user ",
        "invoice_remnawave_tag": " premium_50 ",
    }
    values.update(overrides)
    return WebAppMenuNode(**values)


def test_normalize_and_validate_complete_delivery_fields() -> None:
    node = _invoice()
    _normalize_node(node)
    _validate_node(node)
    assert node.invoice_internal_squad_ids == [INTERNAL_A, INTERNAL_B]
    assert node.invoice_external_squad_id == EXTERNAL
    assert node.invoice_traffic_limit_strategy == "MONTH_ROLLING"
    assert node.invoice_remnawave_description == "Premium user"
    assert node.invoice_remnawave_tag == "PREMIUM_50"


def test_zero_limit_forces_no_reset() -> None:
    node = _invoice(
        invoice_traffic_limit_bytes=0,
        invoice_traffic_limit_strategy="MONTH",
    )
    _normalize_node(node)
    _validate_node(node)
    assert node.invoice_traffic_limit_strategy == "NO_RESET"


def test_incomplete_active_invoice_is_rejected_but_hidden_draft_is_allowed() -> None:
    node = _invoice(invoice_internal_squad_ids=[])
    _normalize_node(node)
    with pytest.raises(HTTPException):
        _validate_node(node)
    node.is_active = False
    _validate_node(node)
