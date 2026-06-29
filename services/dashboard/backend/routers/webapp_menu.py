from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ..auth import get_current_user
from ..cache_utils import bump_cache_version
from ..database.models import WebAppMenuNode
from ..database.session import async_session
from ..schemas.webapp_menu import (
    ReorderRequest,
    WebAppMenuNodeCreate,
    WebAppMenuNodeSchema,
    WebAppMenuNodeUpdate,
)

router = APIRouter(prefix="/api/webapp-menu", tags=["webapp-menu"])


def _serialize_tree(nodes: list[WebAppMenuNode], parent_id: int | None) -> list[dict]:
    children = [n for n in nodes if n.parent_id == parent_id]
    children.sort(key=lambda n: (n.sort_order, n.id))
    return [
        {
            "id": n.id,
            "parent_id": n.parent_id,
            "text": n.text,
            "action": n.action,
            "sort_order": n.sort_order,
            "is_active": bool(n.is_active),
            "invoice_provider": n.invoice_provider,
            "invoice_amount": n.invoice_amount,
            "invoice_currency": n.invoice_currency,
            "invoice_method": n.invoice_method,
            "invoice_days": n.invoice_days,
            "invoice_tariff_slug": n.invoice_tariff_slug,
            "children": _serialize_tree(nodes, n.id),
        }
        for n in children
    ]


@router.get("/tree", response_model=list[WebAppMenuNodeSchema])
async def get_tree(_: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(select(WebAppMenuNode))
        nodes = result.scalars().all()
        return _serialize_tree(nodes, None)


@router.post("/nodes", response_model=WebAppMenuNodeSchema)
async def create_node(body: WebAppMenuNodeCreate, _: str = Depends(get_current_user)):
    if body.parent_id is not None:
        async with async_session() as session:
            parent = await session.get(WebAppMenuNode, body.parent_id)
            if parent is None:
                raise HTTPException(404, "Parent node not found")
            if parent.action != "buttons":
                raise HTTPException(400, "Parent must have action='buttons'")

    async with async_session() as session:
        node = WebAppMenuNode(
            parent_id=body.parent_id,
            text=body.text,
            action=body.action,
            sort_order=body.sort_order,
            is_active=body.is_active,
            invoice_provider=body.invoice_provider,
            invoice_amount=body.invoice_amount,
            invoice_currency=body.invoice_currency,
            invoice_method=body.invoice_method,
            invoice_days=body.invoice_days,
            invoice_tariff_slug=body.invoice_tariff_slug,
        )
        session.add(node)
        await session.commit()
        await session.refresh(node)

    await bump_cache_version()
    return WebAppMenuNodeSchema(
        id=node.id,
        parent_id=node.parent_id,
        text=node.text,
        action=node.action,
        sort_order=node.sort_order,
        is_active=node.is_active,
        invoice_provider=node.invoice_provider,
        invoice_amount=node.invoice_amount,
        invoice_currency=node.invoice_currency,
        invoice_method=node.invoice_method,
        invoice_days=node.invoice_days,
        invoice_tariff_slug=node.invoice_tariff_slug,
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
        if not node:
            raise HTTPException(404, "Node not found")

        for field in (
            "text", "action", "sort_order", "is_active", "parent_id",
            "invoice_provider", "invoice_amount", "invoice_currency",
            "invoice_method", "invoice_days", "invoice_tariff_slug",
        ):
            value = getattr(body, field)
            if value is not None:
                setattr(node, field, value)

        await session.commit()
        await session.refresh(node)

    await bump_cache_version()
    return WebAppMenuNodeSchema(
        id=node.id,
        parent_id=node.parent_id,
        text=node.text,
        action=node.action,
        sort_order=node.sort_order,
        is_active=node.is_active,
        invoice_provider=node.invoice_provider,
        invoice_amount=node.invoice_amount,
        invoice_currency=node.invoice_currency,
        invoice_method=node.invoice_method,
        invoice_days=node.invoice_days,
        invoice_tariff_slug=node.invoice_tariff_slug,
        children=[],
    )


@router.delete("/nodes/{node_id}")
async def delete_node(node_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        node = await session.get(WebAppMenuNode, node_id)
        if not node:
            raise HTTPException(404, "Node not found")
        await session.delete(node)
        await session.commit()
    await bump_cache_version()
    return {"ok": True}


@router.put("/reorder")
async def reorder(body: ReorderRequest, _: str = Depends(get_current_user)):
    async with async_session() as session:
        for item in body.items:
            node = await session.get(WebAppMenuNode, item.id)
            if not node:
                continue
            node.sort_order = item.sort_order
            if item.parent_id is not None or item.parent_id is None:
                node.parent_id = item.parent_id
        await session.commit()
    await bump_cache_version()
    return {"ok": True}
