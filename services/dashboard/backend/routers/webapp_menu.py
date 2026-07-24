from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Depends, HTTPException
from payments import PaymentError, get_provider
from sqlalchemy import func, select

from common_db.repo.webapp_menu import invoice_target
from remnawave_client import configure

from ..auth import get_current_user
from ..cache_utils import bump_cache_version
from ..config import get_remnawave_token, get_remnawave_url
from ..database.models import WebAppMenuNode
from ..database.session import async_session
from ..schemas.webapp_menu import (
    ReorderRequest,
    WebAppMenuNodeCreate,
    WebAppMenuNodeSchema,
    WebAppMenuNodeUpdate,
)

router = APIRouter(prefix="/api/webapp-menu", tags=["webapp-menu"])
_SQUAD_CACHE_TTL_SECONDS = 30.0
_squad_cache: tuple[float, dict] | None = None


def _rw_client():
    return configure(
        base_url=get_remnawave_url(),
        token=get_remnawave_token(),
        free_squad_id="",
    )


def _node_fields(node: WebAppMenuNode) -> dict:
    return {
        "id": node.id,
        "parent_id": node.parent_id,
        "text_ru": node.text_ru,
        "text_en": node.text_en,
        "action": node.action,
        "sort_order": node.sort_order,
        "is_active": bool(node.is_active),
        "invoice_provider": node.invoice_provider,
        "invoice_amount": node.invoice_amount,
        "invoice_currency": node.invoice_currency,
        "invoice_method": node.invoice_method,
        "invoice_days": node.invoice_days,
        "invoice_internal_squad_ids": node.invoice_internal_squad_ids,
        "invoice_external_squad_id": node.invoice_external_squad_id,
        "invoice_traffic_limit_bytes": node.invoice_traffic_limit_bytes,
        "invoice_traffic_limit_strategy": node.invoice_traffic_limit_strategy,
        "invoice_remnawave_description": node.invoice_remnawave_description,
        "invoice_remnawave_tag": node.invoice_remnawave_tag,
    }


def _normalize_node(node: WebAppMenuNode) -> None:
    if node.action != "invoice":
        return
    node.invoice_internal_squad_ids = list(
        dict.fromkeys(
            value.strip()
            for value in (node.invoice_internal_squad_ids or [])
            if value and value.strip()
        )
    )
    node.invoice_external_squad_id = (
        (node.invoice_external_squad_id or "").strip() or None
    )
    node.invoice_traffic_limit_bytes = int(node.invoice_traffic_limit_bytes or 0)
    node.invoice_traffic_limit_strategy = (
        node.invoice_traffic_limit_strategy or "NO_RESET"
    ).strip().upper()
    if node.invoice_traffic_limit_bytes == 0:
        node.invoice_traffic_limit_strategy = "NO_RESET"
    node.invoice_remnawave_description = (
        (node.invoice_remnawave_description or "").strip() or None
    )
    node.invoice_remnawave_tag = (
        (node.invoice_remnawave_tag or "").strip().upper() or None
    )


def _needs_attention(node: WebAppMenuNode) -> bool:
    if not node.text_ru.strip() or not node.text_en.strip():
        return True
    if node.action != "invoice":
        return False
    target = invoice_target(node)
    if target is None:
        return True
    try:
        provider = get_provider(target.provider)
    except PaymentError:
        return True
    methods = {value for value, _ in provider.methods}
    method = target.method or "default"
    return not provider.supports(target.currency) or method not in methods


def _serialize_tree(nodes: list[WebAppMenuNode], parent_id: int | None) -> list[dict]:
    children = sorted(
        (n for n in nodes if n.parent_id == parent_id),
        key=lambda n: (n.sort_order, n.id),
    )
    return [
        {
            **_node_fields(n),
            "needs_attention": _needs_attention(n),
            "children": _serialize_tree(nodes, n.id),
        }
        for n in children
    ]


def _validate_node(node: WebAppMenuNode) -> None:
    if not (node.text_ru or "").strip() or not (node.text_en or "").strip():
        raise HTTPException(400, "RU and EN button text are required")
    if node.action not in {"buttons", "invoice"}:
        raise HTTPException(400, "Node action must be buttons or invoice")
    if node.action == "buttons":
        return
    if not node.is_active:
        return
    target = invoice_target(node)
    if target is None:
        raise HTTPException(
            400,
            "Active invoice requires valid payment, traffic and Remnawave delivery fields",
        )
    try:
        provider = get_provider(target.provider)
    except PaymentError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not provider.supports(target.currency):
        raise HTTPException(400, f"{provider.name} does not support {target.currency}")
    valid_methods = {value for value, _ in provider.methods}
    if (target.method or "default") not in valid_methods:
        raise HTTPException(400, f"Unsupported method for {provider.name}")


async def _validate_parent(session, node: WebAppMenuNode) -> None:
    if node.parent_id is None:
        return
    parent = await session.get(WebAppMenuNode, node.parent_id)
    if parent is None:
        raise HTTPException(404, "Parent node not found")
    if parent.action != "buttons":
        raise HTTPException(400, "Parent must be a buttons node")
    seen = {node.id}
    current = parent
    while current is not None:
        if current.id in seen:
            raise HTTPException(400, "Menu tree cannot contain a cycle")
        seen.add(current.id)
        current = (
            await session.get(WebAppMenuNode, current.parent_id)
            if current.parent_id is not None
            else None
        )


@router.get("/tree", response_model=list[WebAppMenuNodeSchema])
async def get_tree(_: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(select(WebAppMenuNode))
        return _serialize_tree(list(result.scalars().all()), None)


@router.get("/remnawave-squads")
async def get_remnawave_squads(
    refresh: bool = False,
    _: str = Depends(get_current_user),
):
    global _squad_cache
    now = time.monotonic()
    if not refresh and _squad_cache and now - _squad_cache[0] < _SQUAD_CACHE_TTL_SECONDS:
        return _squad_cache[1]
    client = _rw_client()
    try:
        internal, external = await asyncio.gather(
            client.get_internal_squads(strict=True),
            client.get_external_squads(strict=True),
        )
    except Exception as exc:
        raise HTTPException(502, "Unable to load squads from Remnawave") from exc
    payload = {
        "internal": sorted(internal, key=lambda item: (item["name"], item["uuid"])),
        "external": sorted(external, key=lambda item: (item["name"], item["uuid"])),
    }
    _squad_cache = (now, payload)
    return payload


@router.post("/nodes", response_model=WebAppMenuNodeSchema)
async def create_node(body: WebAppMenuNodeCreate, _: str = Depends(get_current_user)):
    async with async_session() as session:
        node = WebAppMenuNode(**body.model_dump())
        _normalize_node(node)
        session.add(node)
        await session.flush()
        await _validate_parent(session, node)
        _validate_node(node)
        await session.commit()
        await session.refresh(node)
    await bump_cache_version()
    return WebAppMenuNodeSchema(
        **_node_fields(node),
        needs_attention=_needs_attention(node),
        children=[],
    )


@router.put("/nodes/{node_id}", response_model=WebAppMenuNodeSchema)
async def update_node(
    node_id: int,
    body: WebAppMenuNodeUpdate,
    _: str = Depends(get_current_user),
):
    async with async_session() as session:
        node = await session.get(WebAppMenuNode, node_id)
        if node is None:
            raise HTTPException(404, "Node not found")
        values = body.model_dump(exclude_unset=True)
        old_parent_id = node.parent_id
        for field, value in values.items():
            setattr(node, field, value)
        _normalize_node(node)
        if "parent_id" in values and node.parent_id != old_parent_id and "sort_order" not in values:
            max_sort = await session.scalar(
                select(func.max(WebAppMenuNode.sort_order)).where(
                    WebAppMenuNode.parent_id == node.parent_id
                )
            )
            node.sort_order = int(-1 if max_sort is None else max_sort) + 1
        if node.action == "invoice":
            child = await session.scalar(
                select(WebAppMenuNode.id).where(WebAppMenuNode.parent_id == node.id)
            )
            if child is not None:
                raise HTTPException(400, "A node with children cannot become an invoice")
        else:
            for field in (
                "invoice_provider",
                "invoice_amount",
                "invoice_currency",
                "invoice_method",
                "invoice_days",
                "invoice_internal_squad_ids",
                "invoice_external_squad_id",
                "invoice_traffic_limit_bytes",
                "invoice_traffic_limit_strategy",
                "invoice_remnawave_description",
                "invoice_remnawave_tag",
            ):
                setattr(node, field, None)
        await _validate_parent(session, node)
        _validate_node(node)
        await session.commit()
        await session.refresh(node)
        response = WebAppMenuNodeSchema(
            **_node_fields(node),
            needs_attention=_needs_attention(node),
            children=[],
        )
    await bump_cache_version()
    return response


@router.delete("/nodes/{node_id}")
async def delete_node(node_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        node = await session.get(WebAppMenuNode, node_id)
        if node is None:
            raise HTTPException(404, "Node not found")
        await session.delete(node)
        await session.commit()
    await bump_cache_version()
    return {"ok": True}


@router.put("/reorder")
async def reorder(body: ReorderRequest, _: str = Depends(get_current_user)):
    ids = [item.id for item in body.items]
    if len(ids) != len(set(ids)):
        raise HTTPException(400, "Duplicate node in reorder request")
    async with async_session() as session:
        result = await session.execute(select(WebAppMenuNode))
        nodes = {node.id: node for node in result.scalars().all()}
        if any(node_id not in nodes for node_id in ids):
            raise HTTPException(404, "Node not found")
        proposed = {node.id: node.parent_id for node in nodes.values()}
        for item in body.items:
            if item.parent_id is not None:
                parent = nodes.get(item.parent_id)
                if parent is None:
                    raise HTTPException(404, "Parent node not found")
                if parent.action != "buttons":
                    raise HTTPException(400, "Parent must be a buttons node")
            proposed[item.id] = item.parent_id
        for node_id in ids:
            seen = {node_id}
            parent_id = proposed[node_id]
            while parent_id is not None:
                if parent_id in seen:
                    raise HTTPException(400, "Menu tree cannot contain a cycle")
                seen.add(parent_id)
                parent_id = proposed.get(parent_id)
        for item in body.items:
            node = nodes[item.id]
            node.parent_id = item.parent_id
            node.sort_order = item.sort_order
        await session.commit()
    await bump_cache_version()
    return {"ok": True}
