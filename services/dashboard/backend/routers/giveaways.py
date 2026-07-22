"""Giveaways admin API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from common_db.repo import giveaways as giveaway_repo

from ..auth import get_current_user
from ..config import get_news_id
from ..database.session import async_session
from ..tasks.giveaways import enqueue_giveaway_broadcast
from ..telegram import tg_bot_deeplink, tg_bot_username, tg_send, tg_url

router = APIRouter(prefix="/api/giveaways", tags=["giveaways"])


class GiveawayConfigBody(BaseModel):
    distribution: list[str] = Field(default_factory=lambda: ["bot"])
    entry_condition: str = "click_only"
    ticket_sources: list[str] = Field(default_factory=list)
    chance_mode: str = "static"
    winner_selection: str = "random"


class GiveawayCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    channel_text: str = ""
    config: GiveawayConfigBody = Field(default_factory=GiveawayConfigBody)
    winner_count: int = Field(default=1, ge=1, le=100)
    starts_at: str | None = None
    ends_at: str | None = None


class GiveawayUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    channel_text: str | None = None
    config: GiveawayConfigBody | None = None
    winner_count: int | None = Field(default=None, ge=1, le=100)
    starts_at: str | None = None
    ends_at: str | None = None
    clear_starts_at: bool = False
    clear_ends_at: bool = False


async def _load_detail(giveaway_id: int) -> dict:
    async with async_session() as session:
        giveaway = await giveaway_repo.get_giveaway(session, giveaway_id)
        if giveaway is None:
            raise HTTPException(404, "giveaway not found")
        counts = await giveaway_repo.giveaway_summary_counts(session, giveaway.id)
        return giveaway_repo.serialize_giveaway(giveaway, counts)


@router.get("")
async def list_giveaways(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str = Query(""),
    _: str = Depends(get_current_user),
):
    async with async_session() as session:
        rows, total = await giveaway_repo.list_giveaways(
            session, status=status or None, page=page, per_page=per_page
        )
        items = []
        for g in rows:
            counts = await giveaway_repo.giveaway_summary_counts(session, g.id)
            items.append(giveaway_repo.serialize_giveaway(g, counts))
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.post("")
async def create_giveaway(
    body: GiveawayCreateRequest,
    user: str = Depends(get_current_user),
):
    async with async_session() as session:
        giveaway = await giveaway_repo.create_giveaway(
            session,
            title=body.title,
            channel_text=body.channel_text,
            config=body.config.model_dump(),
            winner_count=body.winner_count,
            starts_at=body.starts_at,
            ends_at=body.ends_at,
            created_by=user,
        )
        await session.commit()
        counts = await giveaway_repo.giveaway_summary_counts(session, giveaway.id)
        return giveaway_repo.serialize_giveaway(giveaway, counts)


@router.get("/{giveaway_id}")
async def get_giveaway(giveaway_id: int, _: str = Depends(get_current_user)):
    return await _load_detail(giveaway_id)


@router.patch("/{giveaway_id}")
async def update_giveaway(
    giveaway_id: int,
    body: GiveawayUpdateRequest,
    _: str = Depends(get_current_user),
):
    async with async_session() as session:
        giveaway = await giveaway_repo.get_giveaway(session, giveaway_id)
        if giveaway is None:
            raise HTTPException(404, "giveaway not found")
        try:
            await giveaway_repo.update_giveaway(
                session,
                giveaway,
                title=body.title,
                channel_text=body.channel_text,
                config=body.config.model_dump() if body.config else None,
                winner_count=body.winner_count,
                starts_at=body.starts_at,
                ends_at=body.ends_at,
                clear_starts_at=body.clear_starts_at,
                clear_ends_at=body.clear_ends_at,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        await session.commit()
        counts = await giveaway_repo.giveaway_summary_counts(session, giveaway.id)
        return giveaway_repo.serialize_giveaway(giveaway, counts)


@router.post("/{giveaway_id}/activate")
async def activate_giveaway(giveaway_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        giveaway = await giveaway_repo.get_giveaway(session, giveaway_id)
        if giveaway is None:
            raise HTTPException(404, "giveaway not found")
        try:
            await giveaway_repo.activate_giveaway(session, giveaway)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        await session.commit()
        counts = await giveaway_repo.giveaway_summary_counts(session, giveaway.id)
        return giveaway_repo.serialize_giveaway(giveaway, counts)


@router.post("/{giveaway_id}/close")
async def close_giveaway(giveaway_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        giveaway = await giveaway_repo.get_giveaway(session, giveaway_id)
        if giveaway is None:
            raise HTTPException(404, "giveaway not found")
        try:
            await giveaway_repo.close_giveaway(session, giveaway)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        await session.commit()
        counts = await giveaway_repo.giveaway_summary_counts(session, giveaway.id)
        return giveaway_repo.serialize_giveaway(giveaway, counts)


@router.post("/{giveaway_id}/broadcast")
async def broadcast_giveaway(
    giveaway_id: int,
    request: Request,
    _: str = Depends(get_current_user),
):
    async with async_session() as session:
        giveaway = await giveaway_repo.get_giveaway(session, giveaway_id)
        if giveaway is None:
            raise HTTPException(404, "giveaway not found")
    pool = getattr(request.app.state, "arq_pool", None)
    try:
        await enqueue_giveaway_broadcast(pool, giveaway_id)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"ok": True, "queued": True}


@router.post("/{giveaway_id}/channel-post")
async def channel_post_giveaway(giveaway_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        giveaway = await giveaway_repo.get_giveaway(session, giveaway_id)
        if giveaway is None:
            raise HTTPException(404, "giveaway not found")
        text = (giveaway.channel_text or giveaway.title or "").strip()
    if not text:
        raise HTTPException(400, "channel_text is required")

    news_id = get_news_id()
    if not news_id:
        raise HTTPException(503, "news_id not configured")

    reply_markup = None
    username = await tg_bot_username()
    if username:
        reply_markup = {
            "inline_keyboard": [[
                {
                    "text": "Участвовать",
                    "url": tg_bot_deeplink(username, f"gw_{giveaway_id}"),
                }
            ]]
        }

    ok = await tg_send(int(news_id), text, reply_markup)
    if not ok:
        raise HTTPException(502, "Failed to post to channel")
    return {"ok": True}


@router.get("/{giveaway_id}/participants")
async def list_participants(
    giveaway_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _: str = Depends(get_current_user),
):
    async with async_session() as session:
        giveaway = await giveaway_repo.get_giveaway(session, giveaway_id)
        if giveaway is None:
            raise HTTPException(404, "giveaway not found")
        items, total = await giveaway_repo.list_participants_paginated(
            session, giveaway_id, page=page, per_page=per_page
        )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.post("/{giveaway_id}/draw")
async def draw_giveaway(giveaway_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        giveaway = await giveaway_repo.get_giveaway(session, giveaway_id)
        if giveaway is None:
            raise HTTPException(404, "giveaway not found")
        try:
            winners = await giveaway_repo.draw_winners(session, giveaway)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        await session.commit()
    return {"winners": winners}


@router.get("/{giveaway_id}/winners")
async def get_winners(giveaway_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        giveaway = await giveaway_repo.get_giveaway(session, giveaway_id)
        if giveaway is None:
            raise HTTPException(404, "giveaway not found")
        winners = await giveaway_repo.get_winners(session, giveaway_id)
    return {"winners": winners}
