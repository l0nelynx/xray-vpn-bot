"""Shared Tariff Constructor tree reads and invariants."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import WebAppMenuNode


@dataclass(frozen=True)
class InvoiceTarget:
    provider: str
    amount: float
    currency: str
    method: str | None
    days: int
    internal_squad_ids: tuple[str, ...]
    external_squad_id: str
    traffic_limit_bytes: int
    traffic_limit_strategy: str
    remnawave_description: str | None
    remnawave_tag: str | None

    @property
    def squad_id(self) -> str:
        """Compatibility target for legacy tariff_slug consumers."""
        return self.internal_squad_ids[0]


TRAFFIC_LIMIT_STRATEGIES = frozenset(
    {"NO_RESET", "DAY", "WEEK", "MONTH", "MONTH_ROLLING"}
)
REMANWAVE_TAG_RE = re.compile(r"^[A-Z0-9_]+$")


def localized_text(node: WebAppMenuNode, lang: str) -> str:
    if lang == "en":
        return (node.text_en or node.text_ru).strip()
    return (node.text_ru or node.text_en).strip()


def invoice_target(
    node: WebAppMenuNode,
    *,
    allowed_providers: set[str] | None = None,
) -> InvoiceTarget | None:
    if node.action != "invoice":
        return None
    provider = (node.invoice_provider or "").strip().lower()
    currency = (node.invoice_currency or "").strip().upper()
    internal_squad_ids = tuple(
        dict.fromkeys(
            str(value).strip()
            for value in (getattr(node, "invoice_internal_squad_ids", None) or [])
            if str(value).strip()
        )
    )
    external_id = (node.invoice_external_squad_id or "").strip()
    traffic_limit_bytes = int(getattr(node, "invoice_traffic_limit_bytes", None) or 0)
    traffic_limit_strategy = (
        getattr(node, "invoice_traffic_limit_strategy", None) or "NO_RESET"
    ).strip().upper()
    description = (
        getattr(node, "invoice_remnawave_description", None) or ""
    ).strip() or None
    tag = (
        getattr(node, "invoice_remnawave_tag", None) or ""
    ).strip().upper() or None
    try:
        valid_squad_ids = all(uuid.UUID(value) for value in internal_squad_ids)
        valid_external_id = bool(uuid.UUID(external_id))
    except (ValueError, TypeError, AttributeError):
        valid_squad_ids = False
        valid_external_id = False
    amount = float(node.invoice_amount or 0)
    days = int(node.invoice_days or 0)
    if (
        not provider
        or not currency
        or amount <= 0
        or days <= 0
        or not internal_squad_ids
        or not external_id
        or not valid_squad_ids
        or not valid_external_id
        or traffic_limit_bytes < 0
        or traffic_limit_bytes % (1024**3) != 0
        or traffic_limit_strategy not in TRAFFIC_LIMIT_STRATEGIES
        or (traffic_limit_bytes == 0 and traffic_limit_strategy != "NO_RESET")
        or (tag is not None and (len(tag) > 16 or REMANWAVE_TAG_RE.fullmatch(tag) is None))
        or (allowed_providers is not None and provider not in allowed_providers)
    ):
        return None
    if provider == "stars" and (currency != "XTR" or not amount.is_integer()):
        return None
    return InvoiceTarget(
        provider=provider,
        amount=amount,
        currency=currency,
        method=node.invoice_method,
        days=days,
        internal_squad_ids=internal_squad_ids,
        external_squad_id=external_id,
        traffic_limit_bytes=traffic_limit_bytes,
        traffic_limit_strategy=traffic_limit_strategy,
        remnawave_description=description,
        remnawave_tag=tag,
    )


async def list_nodes(session: AsyncSession) -> list[WebAppMenuNode]:
    result = await session.execute(
        select(WebAppMenuNode).order_by(
            WebAppMenuNode.sort_order,
            WebAppMenuNode.id,
        )
    )
    return list(result.scalars().all())


def build_tree(
    nodes: Iterable[WebAppMenuNode],
    *,
    lang: str,
    active_only: bool = True,
    allowed_providers: set[str] | None = None,
    invoice_validator: Callable[[InvoiceTarget], bool] | None = None,
) -> list[dict]:
    rows = list(nodes)
    by_parent: dict[int | None, list[WebAppMenuNode]] = {}
    for node in rows:
        by_parent.setdefault(node.parent_id, []).append(node)
    for children in by_parent.values():
        children.sort(key=lambda n: (n.sort_order, n.id))

    def walk(parent_id: int | None, ancestors: frozenset[int]) -> list[dict]:
        output: list[dict] = []
        for node in by_parent.get(parent_id, []):
            if node.id in ancestors or (active_only and not node.is_active):
                continue
            target = invoice_target(node, allowed_providers=allowed_providers)
            if target is not None and invoice_validator is not None:
                if not invoice_validator(target):
                    target = None
            children = walk(node.id, ancestors | {node.id})
            if node.action == "invoice" and target is None:
                continue
            if node.action == "buttons" and not children:
                continue
            output.append(
                {
                    "id": node.id,
                    "parent_id": node.parent_id,
                    "text": localized_text(node, lang),
                    "text_ru": node.text_ru,
                    "text_en": node.text_en,
                    "action": node.action,
                    "sort_order": node.sort_order,
                    "is_active": bool(node.is_active),
                    "invoice": (
                        {
                            "provider": target.provider,
                            "amount": target.amount,
                            "currency": target.currency,
                            "method": target.method,
                            "days": target.days,
                            # Compatibility for existing clients. New server-side
                            # payment paths use the explicit target fields.
                            "tariff_slug": (
                                f"sid:{target.squad_id}:esid:{target.external_squad_id}"
                            ),
                        }
                        if target
                        else None
                    ),
                    "children": children,
                }
            )
        return output

    return walk(None, frozenset())


async def get_active_node(
    session: AsyncSession,
    node_id: int,
) -> WebAppMenuNode | None:
    """Return a node only when it and every ancestor are active and acyclic."""
    node = await session.get(WebAppMenuNode, node_id)
    if node is None or not node.is_active:
        return None
    seen = {node.id}
    parent_id = node.parent_id
    while parent_id is not None:
        if parent_id in seen:
            return None
        seen.add(parent_id)
        parent = await session.get(WebAppMenuNode, parent_id)
        if parent is None or not parent.is_active or parent.action != "buttons":
            return None
        parent_id = parent.parent_id
    return node
