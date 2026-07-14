import logging
import re
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, delete, exists, or_

logger = logging.getLogger(__name__)

from ..auth import get_current_user
from ..config import get_bot_token, get_remnawave_url, get_remnawave_token
from ..database.models import User, Transaction, SupportTicket, Promo
from ..database.session import async_session

# Shared "paid user" predicate + count helpers — see
# packages/common_db/common_db/repo/users.py. Routes still own their
# sessions; the helpers just centralise the WHERE clause so dashboard
# and app can never disagree on what "paid" means.
from common_db.repo import users as _repo_users

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/count")
async def users_count(_: str = Depends(get_current_user)):
    now = datetime.now()
    async with async_session() as session:
        total = await _repo_users.count_users(session)
        paid = await _repo_users.count_paid_users(session, now=now)
        free = total - paid
        banned = await session.scalar(
            select(func.count()).select_from(User).where(User.is_banned == True)
        ) or 0
    return {"total": total, "paid": paid, "free": free, "banned": banned}


_USER_SORT_COLUMNS = {
    "id": User.id,
    "tg_id": User.tg_id,
    "username": User.username,
    "api_provider": User.api_provider,
}


@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort: str = Query("id"),
    order: str = Query("desc"),
    search: str = Query(""),
    filter: str = Query("all"),
    _: str = Depends(get_current_user),
):
    now = datetime.now()
    now_iso = now.isoformat(timespec='seconds')
    async with async_session() as session:
        # The is_paid flag and the paid/free filter both use the canonical
        # predicate from common_db.repo.users (Transaction.order_status
        # IN ('confirmed','delivered') AND expire_date > now).
        has_tx = exists(
            select(Transaction.user_id).where(
                Transaction.user_id == User.id,
                Transaction.order_status.in_(_repo_users.PAID_ORDER_STATUSES),
                Transaction.expire_date > now_iso,
            )
        ).correlate(User).label("is_paid")

        base = select(User, has_tx)

        if search:
            like = f"%{search}%"
            conds = [
                User.username.ilike(like),
                User.email.ilike(like),
                User.vless_uuid.ilike(like),
            ]
            if search.isdigit():
                conds.append(User.tg_id == int(search))
            base = base.where(or_(*conds))

        active_paid_sq = _repo_users.active_paid_user_ids_subquery(now)
        if filter == "paid":
            base = base.where(User.id.in_(active_paid_sq))
        elif filter == "free":
            base = base.where(~User.id.in_(active_paid_sq))
        elif filter == "banned":
            base = base.where(User.is_banned == True)
        elif filter == "vip":
            base = base.where(User.vip == 1)

        count_q = select(func.count()).select_from(base.subquery())
        total = await session.scalar(count_q) or 0

        if sort == "is_paid":
            sort_col = has_tx
        else:
            sort_col = _USER_SORT_COLUMNS.get(sort, User.id)
        base = base.order_by(
            sort_col.asc() if order == "asc" else sort_col.desc()
        )

        offset = (page - 1) * per_page
        result = await session.execute(base.offset(offset).limit(per_page))
        rows = result.all()

        users = []
        for user, is_paid in rows:
            users.append({
                "id": user.id,
                "tg_id": user.tg_id,
                "username": user.username,
                "vless_uuid": user.vless_uuid,
                "api_provider": user.api_provider,
                "is_banned": bool(user.is_banned),
                "is_paid": bool(is_paid),
                "email": user.email,
                "language": user.language,
                "vip": bool(user.vip),
            })

    return {"items": users, "total": total, "page": page, "per_page": per_page}


@router.post("/backfill-rw-ids")
async def backfill_rw_ids(_: str = Depends(get_current_user)):
    """Temporary bulk backfill: map local vless_uuid -> Remnawave panel id."""
    rw_url = get_remnawave_url()
    rw_token = get_remnawave_token()
    if not rw_url or not rw_token:
        raise HTTPException(status_code=503, detail="Remnawave not configured")

    from remnawave_client import configure

    rw = configure(base_url=rw_url, token=rw_token, free_squad_id="")

    async with async_session() as session:
        result = await session.execute(
            select(User.id, User.vless_uuid).where(
                User.vless_uuid.isnot(None),
                User.vless_uuid != "",
                User.rw_id.is_(None),
            )
        )
        candidates = list(result.all())

    local_candidates = len(candidates)
    if not local_candidates:
        return {
            "local_candidates": 0,
            "updated": 0,
            "not_found_on_panel": 0,
            "errors": 0,
        }

    try:
        panel_users = await rw.get_all_users_for_crm()
    except Exception as exc:
        logger.exception("backfill_rw_ids: Remnawave fetch failed")
        raise HTTPException(status_code=502, detail=f"Remnawave fetch failed: {exc}") from exc

    uuid_to_rw_id: dict[str, int] = {}
    for panel_user in panel_users:
        panel_uuid = panel_user.get("uuid")
        panel_rw_id = panel_user.get("rw_id")
        if panel_uuid and panel_rw_id is not None:
            uuid_to_rw_id[str(panel_uuid).lower()] = int(panel_rw_id)

    updated = 0
    not_found_on_panel = 0
    errors = 0

    async with async_session() as session:
        for user_id, vless_uuid in candidates:
            rw_id = uuid_to_rw_id.get((vless_uuid or "").lower())
            if rw_id is None:
                not_found_on_panel += 1
                continue
            try:
                user = await session.get(User, user_id)
                if user is None:
                    errors += 1
                    continue
                user.rw_id = rw_id
                updated += 1
            except Exception:
                logger.exception("backfill_rw_ids: failed for user id=%s", user_id)
                errors += 1
        await session.commit()

    return {
        "local_candidates": local_candidates,
        "updated": updated,
        "not_found_on_panel": not_found_on_panel,
        "errors": errors,
    }


@router.get("/{tg_id}")
async def get_user(tg_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        tx_count = await session.scalar(
            select(func.count()).select_from(Transaction).where(Transaction.user_id == user.id)
        ) or 0
        total_spent = await session.scalar(
            select(func.sum(Transaction.amount)).where(Transaction.user_id == user.id)
        ) or 0

        # The user's own promo/referral code (one row per owner tg_id), if any.
        promo_code = await session.scalar(
            select(Promo.promo_code).where(Promo.tg_id == user.tg_id)
        )
        # How many support tickets this user has opened.
        tickets_count = await session.scalar(
            select(func.count()).select_from(SupportTicket).where(SupportTicket.user_id == user.id)
        ) or 0

        return {
            "id": user.id,
            "tg_id": user.tg_id,
            "username": user.username,
            "vless_uuid": user.vless_uuid,
            "api_provider": user.api_provider,
            "email": user.email,
            "is_banned": bool(user.is_banned),
            "language": user.language,
            "vip": bool(user.vip),
            "transactions_count": tx_count,
            "total_spent": float(total_spent),
            "promo_code": promo_code,
            "tickets_count": tickets_count,
        }


class UpdateIdentifiersRequest(BaseModel):
    tg_id: int | None = None
    username: str | None = None
    vless_uuid: str | None = None


@router.patch("/{tg_id}/identifiers")
async def update_identifiers(
    tg_id: int,
    body: UpdateIdentifiersRequest,
    _: str = Depends(get_current_user),
):
    """Edit a user's tg_id / username / vless_uuid. Empty string clears the
    field (sets NULL); a missing field is left unchanged."""
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if body.username is not None:
            user.username = body.username.strip().lstrip("@") or None
        if body.vless_uuid is not None:
            user.vless_uuid = body.vless_uuid.strip() or None
        if body.tg_id is not None and body.tg_id != tg_id:
            clash = await _repo_users.get_user_by_tg_id(session, body.tg_id)
            if clash and clash.id != user.id:
                raise HTTPException(status_code=409, detail="tg_id already in use by another user")
            user.tg_id = body.tg_id

        await session.commit()
        return {
            "ok": True,
            "tg_id": user.tg_id,
            "username": user.username,
            "vless_uuid": user.vless_uuid,
        }


@router.get("/{tg_id}/transactions")
async def get_user_transactions(tg_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        result = await session.execute(
            select(Transaction)
            .where(Transaction.user_id == user.id)
            .order_by(Transaction.created_at.desc())
        )
        transactions = result.scalars().all()

        return [
            {
                "transaction_id": t.transaction_id,
                "payment_method": t.payment_method,
                "amount": t.amount,
                "created_at": t.created_at,
                "order_status": t.order_status,
                "delivery_status": t.delivery_status,
                "days_ordered": t.days_ordered,
                "expire_date": t.expire_date,
            }
            for t in transactions
        ]


@router.post("/{tg_id}/ban")
async def ban_user(tg_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.is_banned = True
        await session.commit()
    return {"ok": True, "message": f"User {tg_id} banned"}


@router.post("/{tg_id}/unban")
async def unban_user(tg_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.is_banned = False
        await session.commit()
    return {"ok": True, "message": f"User {tg_id} unbanned"}


@router.post("/{tg_id}/vip")
async def set_vip(tg_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.vip = 1
        await session.commit()
    return {"ok": True, "message": f"User {tg_id} VIP enabled"}


@router.post("/{tg_id}/unvip")
async def unset_vip(tg_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.vip = 0
        await session.commit()
    return {"ok": True, "message": f"User {tg_id} VIP disabled"}


@router.delete("/{tg_id}")
async def delete_user(tg_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        await session.execute(delete(Transaction).where(Transaction.user_id == user.id))
        await session.execute(delete(User).where(User.id == user.id))
        await session.commit()
    return {"ok": True, "message": f"User {tg_id} deleted"}


class SendMessageRequest(BaseModel):
    text: str


@router.post("/{tg_id}/send-message")
async def send_message(tg_id: int, body: SendMessageRequest, _: str = Depends(get_current_user)):
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Text is required")
    token = get_bot_token()
    if not token:
        raise HTTPException(status_code=503, detail="Bot token not configured")
    payload = {
        "chat_id": tg_id,
        "text": f"Сообщение от администратора:\n\n{body.text}",
        "parse_mode": "HTML",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload)
    if r.status_code != 200:
        detail = r.json().get("description", "Telegram error")
        raise HTTPException(status_code=502, detail=detail)
    return {"ok": True}


class UpdateEmailRequest(BaseModel):
    email: str


@router.patch("/{tg_id}/email")
async def update_email(tg_id: int, body: UpdateEmailRequest, _: str = Depends(get_current_user)):
    email = body.email.strip().lower()
    if not re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    async with async_session() as session:
        user = await _repo_users.get_user_by_tg_id(session, tg_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.email = email
        await session.commit()

    rw_uuid = None
    try:
        from remnawave_client import configure
        rw = configure(base_url=get_remnawave_url(), token=get_remnawave_token(), free_squad_id="")
        rw_user = await rw.get_user_by_email(email)
        if rw_user and rw_user.get("uuid"):
            rw_uuid = str(rw_user["uuid"])
            async with async_session() as session:
                user = await _repo_users.get_user_by_tg_id(session, tg_id)
                if user:
                    user.vless_uuid = rw_uuid
                    user.api_provider = "remnawave"
                    rw_id = rw_user.get("rw_id")
                    if rw_id is not None:
                        user.rw_id = rw_id
                    await session.commit()
    except Exception as exc:
        logger.warning("RW email lookup failed for %s: %s", email, exc)

    return {"ok": True, "email": email, "rw_uuid": rw_uuid}
