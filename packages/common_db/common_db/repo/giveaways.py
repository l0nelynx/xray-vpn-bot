"""Giveaway business logic — shared across dashboard, bot, miniapp."""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Giveaway, GiveawayParticipant, GiveawayTicket, GiveawayWinner, User
from ..models.giveaways import (
    CHANCE_DYNAMIC,
    CHANCE_STATIC,
    ENTRY_CHANNEL_SUB,
    ENTRY_CLICK_ONLY,
    GIVEAWAY_STATUS_ACTIVE,
    GIVEAWAY_STATUS_CLOSED,
    GIVEAWAY_STATUS_DRAFT,
    GIVEAWAY_STATUS_DRAWN,
    TICKET_SOURCE_INVITEE_PURCHASE,
    TICKET_SOURCE_INVITEE_REF,
    TICKET_SOURCE_JOIN,
    WINNER_MOST_TICKETS,
    WINNER_RANDOM,
)


def _now_naive_utc() -> datetime:
    """Current UTC as naive datetime (matches stored starts_at/ends_at)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _now_iso() -> str:
    return _now_naive_utc().isoformat(timespec="seconds")


def _parse_window_dt(raw: str) -> datetime:
    """Parse ISO window bound; normalize aware values to naive UTC."""
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def parse_config(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def default_config() -> dict[str, Any]:
    return {
        "distribution": ["bot"],
        "entry_condition": ENTRY_CLICK_ONLY,
        "ticket_sources": [],
        "chance_mode": CHANCE_STATIC,
        "winner_selection": WINNER_RANDOM,
    }


def normalize_config(data: dict[str, Any] | None) -> dict[str, Any]:
    base = default_config()
    if not data:
        return base
    dist = data.get("distribution") or base["distribution"]
    if isinstance(dist, str):
        dist = [dist]
    entry = data.get("entry_condition", base["entry_condition"])
    if entry not in (ENTRY_CLICK_ONLY, ENTRY_CHANNEL_SUB):
        entry = ENTRY_CLICK_ONLY
    sources = data.get("ticket_sources") or []
    if isinstance(sources, str):
        sources = [sources]
    sources = [
        s
        for s in sources
        if s in (TICKET_SOURCE_INVITEE_REF, TICKET_SOURCE_INVITEE_PURCHASE)
    ]
    chance = data.get("chance_mode", base["chance_mode"])
    if chance not in (CHANCE_STATIC, CHANCE_DYNAMIC):
        chance = CHANCE_STATIC
    if chance == CHANCE_STATIC:
        sources = []
    winner_sel = data.get("winner_selection", base["winner_selection"])
    if winner_sel not in (WINNER_RANDOM, WINNER_MOST_TICKETS):
        winner_sel = WINNER_RANDOM
    return {
        "distribution": dist,
        "entry_condition": entry,
        "ticket_sources": sources,
        "chance_mode": chance,
        "winner_selection": winner_sel,
    }


def _is_in_window(giveaway: Giveaway, now: datetime | None = None) -> bool:
    """True if ``now`` (UTC naive) is within optional starts_at/ends_at bounds."""
    now = now or _now_naive_utc()
    if now.tzinfo is not None:
        now = now.astimezone(timezone.utc).replace(tzinfo=None)
    if giveaway.starts_at:
        try:
            if now < _parse_window_dt(giveaway.starts_at):
                return False
        except ValueError:
            pass
    if giveaway.ends_at:
        try:
            if now > _parse_window_dt(giveaway.ends_at):
                return False
        except ValueError:
            pass
    return True


async def get_giveaway(session: AsyncSession, giveaway_id: int) -> Giveaway | None:
    return await session.get(Giveaway, giveaway_id)


async def list_giveaways(
    session: AsyncSession,
    *,
    status: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Giveaway], int]:
    page = max(1, page)
    per_page = max(1, min(per_page, 100))
    base = select(Giveaway)
    if status:
        base = base.where(Giveaway.status == status)
    total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = await session.execute(
        base.order_by(Giveaway.id.desc()).offset((page - 1) * per_page).limit(per_page)
    )
    return list(rows.scalars().all()), total


async def create_giveaway(
    session: AsyncSession,
    *,
    title: str,
    channel_text: str,
    config: dict[str, Any],
    winner_count: int,
    starts_at: str | None,
    ends_at: str | None,
    created_by: str = "",
) -> Giveaway:
    g = Giveaway(
        title=title.strip(),
        channel_text=channel_text,
        config_json=json.dumps(normalize_config(config)),
        winner_count=max(1, winner_count),
        starts_at=starts_at,
        ends_at=ends_at,
        status=GIVEAWAY_STATUS_DRAFT,
        created_at=_now_iso(),
        created_by=created_by,
    )
    session.add(g)
    await session.flush()
    return g


async def update_giveaway(
    session: AsyncSession,
    giveaway: Giveaway,
    *,
    title: str | None = None,
    channel_text: str | None = None,
    config: dict[str, Any] | None = None,
    winner_count: int | None = None,
    starts_at: str | None = None,
    ends_at: str | None = None,
    clear_starts_at: bool = False,
    clear_ends_at: bool = False,
) -> Giveaway:
    is_draft = giveaway.status == GIVEAWAY_STATUS_DRAFT
    is_active = giveaway.status == GIVEAWAY_STATUS_ACTIVE
    if not is_draft and not is_active:
        raise ValueError("only draft or active giveaways can be edited")
    if not is_draft and any(
        v is not None for v in (title, channel_text, config, winner_count)
    ):
        raise ValueError("active giveaways can only change starts_at/ends_at")
    if is_draft:
        if title is not None:
            giveaway.title = title.strip()
        if channel_text is not None:
            giveaway.channel_text = channel_text
        if config is not None:
            giveaway.config_json = json.dumps(normalize_config(config))
        if winner_count is not None:
            giveaway.winner_count = max(1, winner_count)
    if clear_starts_at:
        giveaway.starts_at = None
    elif starts_at is not None:
        giveaway.starts_at = starts_at or None
    if clear_ends_at:
        giveaway.ends_at = None
    elif ends_at is not None:
        giveaway.ends_at = ends_at or None
    await session.flush()
    return giveaway


async def activate_giveaway(session: AsyncSession, giveaway: Giveaway) -> Giveaway:
    if giveaway.status != GIVEAWAY_STATUS_DRAFT:
        raise ValueError("giveaway is not draft")
    giveaway.status = GIVEAWAY_STATUS_ACTIVE
    await session.flush()
    return giveaway


async def close_giveaway(session: AsyncSession, giveaway: Giveaway) -> Giveaway:
    if giveaway.status != GIVEAWAY_STATUS_ACTIVE:
        raise ValueError("giveaway is not active")
    giveaway.status = GIVEAWAY_STATUS_CLOSED
    await session.flush()
    return giveaway


async def list_active_giveaways(session: AsyncSession) -> list[Giveaway]:
    result = await session.execute(
        select(Giveaway).where(Giveaway.status == GIVEAWAY_STATUS_ACTIVE)
    )
    now = _now_naive_utc()
    return [g for g in result.scalars().all() if _is_in_window(g, now)]


async def is_participant(
    session: AsyncSession, giveaway_id: int, tg_id: int
) -> bool:
    return bool(
        await session.scalar(
            select(func.count())
            .select_from(GiveawayParticipant)
            .where(
                GiveawayParticipant.giveaway_id == giveaway_id,
                GiveawayParticipant.tg_id == tg_id,
            )
        )
    )


async def count_tickets(
    session: AsyncSession, giveaway_id: int, participant_tg_id: int
) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(GiveawayTicket)
            .where(
                GiveawayTicket.giveaway_id == giveaway_id,
                GiveawayTicket.participant_tg_id == participant_tg_id,
            )
        )
        or 0
    )


async def _grant_ticket(
    session: AsyncSession,
    *,
    giveaway_id: int,
    participant_tg_id: int,
    source: str,
    source_tg_id: int | None = None,
) -> bool:
    exists = await session.scalar(
        select(func.count())
        .select_from(GiveawayTicket)
        .where(
            GiveawayTicket.giveaway_id == giveaway_id,
            GiveawayTicket.participant_tg_id == participant_tg_id,
            GiveawayTicket.source == source,
            GiveawayTicket.source_tg_id == source_tg_id
            if source_tg_id is not None
            else GiveawayTicket.source_tg_id.is_(None),
        )
    )
    if exists:
        return False
    session.add(
        GiveawayTicket(
            giveaway_id=giveaway_id,
            participant_tg_id=participant_tg_id,
            source=source,
            source_tg_id=source_tg_id,
            created_at=_now_iso(),
        )
    )
    await session.flush()
    return True


@dataclass(frozen=True, slots=True)
class JoinResult:
    ok: bool
    reason: str
    already_joined: bool = False
    tickets: int = 0


async def join_participant(
    session: AsyncSession,
    giveaway_id: int,
    tg_id: int,
    *,
    channel_sub_ok: bool = True,
) -> JoinResult:
    """Register participant and grant entry ticket(s)."""
    if tg_id <= 0:
        return JoinResult(False, "invalid_user")

    giveaway = await get_giveaway(session, giveaway_id)
    if giveaway is None:
        return JoinResult(False, "not_found")
    if giveaway.status != GIVEAWAY_STATUS_ACTIVE:
        return JoinResult(False, "not_active")
    if not _is_in_window(giveaway):
        return JoinResult(False, "outside_window")

    config = normalize_config(parse_config(giveaway.config_json))
    if config["entry_condition"] == ENTRY_CHANNEL_SUB and not channel_sub_ok:
        return JoinResult(False, "channel_sub_required")

    if await is_participant(session, giveaway_id, tg_id):
        tickets = await count_tickets(session, giveaway_id, tg_id)
        return JoinResult(True, "already_joined", already_joined=True, tickets=tickets)

    session.add(
        GiveawayParticipant(
            giveaway_id=giveaway_id,
            tg_id=tg_id,
            joined_at=_now_iso(),
        )
    )
    try:
        await session.flush()
    except Exception:
        tickets = await count_tickets(session, giveaway_id, tg_id)
        if tickets > 0 or await is_participant(session, giveaway_id, tg_id):
            return JoinResult(True, "already_joined", already_joined=True, tickets=tickets)
        raise

    if config["chance_mode"] == CHANCE_STATIC or config["chance_mode"] == CHANCE_DYNAMIC:
        await _grant_ticket(
            session,
            giveaway_id=giveaway_id,
            participant_tg_id=tg_id,
            source=TICKET_SOURCE_JOIN,
            source_tg_id=None,
        )

    tickets = await count_tickets(session, giveaway_id, tg_id)
    return JoinResult(True, "joined", tickets=tickets)


async def try_grant_invitee_ticket(
    session: AsyncSession,
    *,
    referrer_tg_id: int,
    invitee_tg_id: int,
    source: str,
) -> int:
    """Grant ticket to referrer for invitee action across active giveaways."""
    if referrer_tg_id <= 0 or invitee_tg_id <= 0:
        return 0
    if source not in (TICKET_SOURCE_INVITEE_REF, TICKET_SOURCE_INVITEE_PURCHASE):
        return 0

    granted = 0
    for giveaway in await list_active_giveaways(session):
        config = normalize_config(parse_config(giveaway.config_json))
        if config["chance_mode"] != CHANCE_DYNAMIC:
            continue
        if source not in config["ticket_sources"]:
            continue
        if not await is_participant(session, giveaway.id, referrer_tg_id):
            continue
        if await _grant_ticket(
            session,
            giveaway_id=giveaway.id,
            participant_tg_id=referrer_tg_id,
            source=source,
            source_tg_id=invitee_tg_id,
        ):
            granted += 1
    return granted


async def list_participants_paginated(
    session: AsyncSession,
    giveaway_id: int,
    *,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[dict], int]:
    page = max(1, page)
    per_page = max(1, min(per_page, 100))
    ticket_sq = (
        select(func.count())
        .select_from(GiveawayTicket)
        .where(
            GiveawayTicket.giveaway_id == giveaway_id,
            GiveawayTicket.participant_tg_id == GiveawayParticipant.tg_id,
        )
        .correlate(GiveawayParticipant)
        .scalar_subquery()
        .label("ticket_count")
    )
    base = (
        select(GiveawayParticipant, User.username, ticket_sq)
        .outerjoin(User, GiveawayParticipant.tg_id == User.tg_id)
        .where(GiveawayParticipant.giveaway_id == giveaway_id)
    )
    total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = await session.execute(
        base.order_by(ticket_sq.desc(), GiveawayParticipant.joined_at)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    items = [
        {
            "tg_id": p.tg_id,
            "username": username,
            "joined_at": p.joined_at,
            "ticket_count": ticket_count or 0,
        }
        for p, username, ticket_count in rows.all()
    ]
    return items, total


async def giveaway_summary_counts(session: AsyncSession, giveaway_id: int) -> dict:
    participants = (
        await session.scalar(
            select(func.count())
            .select_from(GiveawayParticipant)
            .where(GiveawayParticipant.giveaway_id == giveaway_id)
        )
        or 0
    )
    tickets = (
        await session.scalar(
            select(func.count())
            .select_from(GiveawayTicket)
            .where(GiveawayTicket.giveaway_id == giveaway_id)
        )
        or 0
    )
    return {"participants": participants, "tickets": tickets}


def _weighted_random_winners(
    entries: list[tuple[int, int]], winner_count: int
) -> list[tuple[int, int]]:
    """entries: (tg_id, ticket_count). Returns winners with ticket counts."""
    pool: list[tuple[int, int]] = [(tg, tc) for tg, tc in entries if tc > 0]
    if not pool:
        return []
    winners: list[tuple[int, int]] = []
    remaining = list(pool)
    while remaining and len(winners) < winner_count:
        weights = [tc for _, tc in remaining]
        pick_idx = random.choices(range(len(remaining)), weights=weights, k=1)[0]
        winners.append(remaining.pop(pick_idx))
    return winners


def _most_tickets_winners(
    entries: list[tuple[int, int]], winner_count: int
) -> list[tuple[int, int]]:
    if not entries:
        return []
    max_tickets = max(tc for _, tc in entries)
    top = [(tg, tc) for tg, tc in entries if tc == max_tickets]
    if len(top) <= winner_count:
        rest = sorted(
            [(tg, tc) for tg, tc in entries if tc < max_tickets],
            key=lambda x: (-x[1], x[0]),
        )
        result = list(top)
        for item in rest:
            if len(result) >= winner_count:
                break
            result.append(item)
        return result[:winner_count]
    return random.sample(top, winner_count)


async def draw_winners(session: AsyncSession, giveaway: Giveaway) -> list[dict]:
    if giveaway.status not in (GIVEAWAY_STATUS_ACTIVE, GIVEAWAY_STATUS_CLOSED):
        raise ValueError("giveaway cannot be drawn")
    if giveaway.status == GIVEAWAY_STATUS_ACTIVE:
        giveaway.status = GIVEAWAY_STATUS_CLOSED
        await session.flush()

    existing = await session.scalar(
        select(func.count())
        .select_from(GiveawayWinner)
        .where(GiveawayWinner.giveaway_id == giveaway.id)
    )
    if existing:
        raise ValueError("already drawn")

    rows = await session.execute(
        select(
            GiveawayParticipant.tg_id,
            func.count(GiveawayTicket.id),
        )
        .outerjoin(
            GiveawayTicket,
            (GiveawayTicket.giveaway_id == GiveawayParticipant.giveaway_id)
            & (GiveawayTicket.participant_tg_id == GiveawayParticipant.tg_id),
        )
        .where(GiveawayParticipant.giveaway_id == giveaway.id)
        .group_by(GiveawayParticipant.tg_id)
    )
    entries = [(int(tg_id), int(ticket_count or 0)) for tg_id, ticket_count in rows.all()]

    config = normalize_config(parse_config(giveaway.config_json))
    if config["winner_selection"] == WINNER_MOST_TICKETS:
        picked = _most_tickets_winners(entries, giveaway.winner_count)
    else:
        picked = _weighted_random_winners(entries, giveaway.winner_count)

    result: list[dict] = []
    for rank, (tg_id, tickets) in enumerate(picked, start=1):
        session.add(
            GiveawayWinner(
                giveaway_id=giveaway.id,
                tg_id=tg_id,
                rank=rank,
                tickets=tickets,
            )
        )
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        result.append(
            {
                "rank": rank,
                "tg_id": tg_id,
                "username": user.username if user else None,
                "tickets": tickets,
            }
        )

    giveaway.status = GIVEAWAY_STATUS_DRAWN
    giveaway.drawn_at = _now_iso()
    await session.flush()
    return result


async def get_winners(session: AsyncSession, giveaway_id: int) -> list[dict]:
    rows = await session.execute(
        select(GiveawayWinner, User.username)
        .outerjoin(User, GiveawayWinner.tg_id == User.tg_id)
        .where(GiveawayWinner.giveaway_id == giveaway_id)
        .order_by(GiveawayWinner.rank)
    )
    return [
        {
            "rank": w.rank,
            "tg_id": w.tg_id,
            "username": username,
            "tickets": w.tickets,
        }
        for w, username in rows.all()
    ]


def serialize_giveaway(giveaway: Giveaway, counts: dict | None = None) -> dict:
    return {
        "id": giveaway.id,
        "title": giveaway.title,
        "channel_text": giveaway.channel_text,
        "status": giveaway.status,
        "config": normalize_config(parse_config(giveaway.config_json)),
        "winner_count": giveaway.winner_count,
        "starts_at": giveaway.starts_at,
        "ends_at": giveaway.ends_at,
        "drawn_at": giveaway.drawn_at,
        "created_at": giveaway.created_at,
        "created_by": giveaway.created_by,
        "participants": (counts or {}).get("participants", 0),
        "tickets": (counts or {}).get("tickets", 0),
    }


__all__ = [
    "JoinResult",
    "activate_giveaway",
    "close_giveaway",
    "count_tickets",
    "create_giveaway",
    "default_config",
    "draw_winners",
    "get_giveaway",
    "get_winners",
    "giveaway_summary_counts",
    "join_participant",
    "list_active_giveaways",
    "list_giveaways",
    "list_participants_paginated",
    "normalize_config",
    "parse_config",
    "serialize_giveaway",
    "try_grant_invitee_ticket",
    "update_giveaway",
]
